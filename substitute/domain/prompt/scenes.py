#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Parse text-authored prompt scenes without presentation dependencies."""

from __future__ import annotations

from dataclasses import dataclass
import re

from substitute.domain.prompt.models import SourceRange

_WHITESPACE_RE = re.compile(r"\s+")
PROMPT_SCENE_MARKER = "**"


@dataclass(frozen=True, slots=True)
class PromptSceneMarker:
    """Identify one scene marker line in prompt source text."""

    title: str
    normalized_key: str
    marker_range: SourceRange
    title_range: SourceRange
    line_range: SourceRange
    duplicate: bool = False


@dataclass(frozen=True, slots=True)
class PromptSceneBlock:
    """Represent scene-local prompt text following a marker."""

    marker: PromptSceneMarker
    content_range: SourceRange
    text: str


@dataclass(frozen=True, slots=True)
class PromptSceneDocument:
    """Describe universal and scene-specific prompt text."""

    source_text: str
    universal_range: SourceRange
    universal_text: str
    scenes: tuple[PromptSceneBlock, ...]

    @property
    def has_scenes(self) -> bool:
        """Return whether this prompt contains at least one valid scene marker."""

        return bool(self.scenes)

    def first_scene_for_key(self, normalized_key: str) -> PromptSceneBlock | None:
        """Return the first non-duplicate scene block for one normalized key."""

        for scene in self.scenes:
            if (
                scene.marker.normalized_key == normalized_key
                and not scene.marker.duplicate
            ):
                return scene
        return None


@dataclass(frozen=True, slots=True)
class _SceneMarkerCandidate:
    """Track one parsed scene marker before duplicate state is assigned."""

    title: str
    normalized_key: str
    marker_range: SourceRange
    title_range: SourceRange
    line_range: SourceRange
    content_start: int


def parse_prompt_scene_document(text: str) -> PromptSceneDocument:
    """Return scene structure parsed from one prompt text snapshot."""

    candidates = _scene_marker_candidates(text)
    if not candidates:
        full_range = SourceRange(0, len(text))
        return PromptSceneDocument(
            source_text=text,
            universal_range=full_range,
            universal_text=text,
            scenes=(),
        )

    universal_range = SourceRange(0, candidates[0].line_range.start)
    seen_keys: set[str] = set()
    scenes: list[PromptSceneBlock] = []
    for index, candidate in enumerate(candidates):
        content_end = (
            candidates[index + 1].line_range.start
            if index + 1 < len(candidates)
            else len(text)
        )
        duplicate = candidate.normalized_key in seen_keys
        seen_keys.add(candidate.normalized_key)
        marker = PromptSceneMarker(
            title=candidate.title,
            normalized_key=candidate.normalized_key,
            marker_range=candidate.marker_range,
            title_range=candidate.title_range,
            line_range=candidate.line_range,
            duplicate=duplicate,
        )
        content_range = SourceRange(candidate.content_start, content_end)
        scenes.append(
            PromptSceneBlock(
                marker=marker,
                content_range=content_range,
                text=content_range.slice(text),
            )
        )
    return PromptSceneDocument(
        source_text=text,
        universal_range=universal_range,
        universal_text=universal_range.slice(text),
        scenes=tuple(scenes),
    )


def normalize_scene_title(title: str) -> str:
    """Return the comparison key for one user-authored scene title."""

    return _WHITESPACE_RE.sub(" ", title.strip()).casefold()


def materialize_scene_prompt(
    *,
    universal_text: str,
    scene_text: str,
) -> str:
    """Join universal and scene-local prompt text for one generation field."""

    universal = universal_text.strip()
    scene = scene_text.strip()
    if universal and scene:
        return f"{universal}\n\n{scene}"
    if universal:
        return universal
    return scene


def scene_block_at_source_position(
    document: PromptSceneDocument,
    source_position: int,
) -> PromptSceneBlock | None:
    """Return the scene block containing one source position."""

    if not document.scenes:
        return None
    position = max(0, min(source_position, len(document.source_text)))
    for index, scene in enumerate(document.scenes):
        scene_start = scene.marker.line_range.start
        scene_end = scene.content_range.end
        if scene_start <= position < scene_end:
            return scene
        is_final_scene = index == len(document.scenes) - 1
        if is_final_scene and scene_start <= position <= scene_end:
            return scene
    return None


def _scene_marker_candidates(text: str) -> tuple[_SceneMarkerCandidate, ...]:
    """Return valid scene marker lines found in one source string."""

    candidates: list[_SceneMarkerCandidate] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        line_start = offset
        line_end = offset + len(line)
        content_end = line_end - _line_break_length(line)
        line_content = text[line_start:content_end]
        candidate = _parse_marker_line(
            text=text,
            line_start=line_start,
            content_end=content_end,
            line_end=line_end,
            line_content=line_content,
        )
        if candidate is not None:
            candidates.append(candidate)
        offset = line_end
    if offset < len(text):
        line_content = text[offset:]
        candidate = _parse_marker_line(
            text=text,
            line_start=offset,
            content_end=len(text),
            line_end=len(text),
            line_content=line_content,
        )
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def _parse_marker_line(
    *,
    text: str,
    line_start: int,
    content_end: int,
    line_end: int,
    line_content: str,
) -> _SceneMarkerCandidate | None:
    """Return a marker candidate when one source line declares a scene."""

    leading_width = len(line_content) - len(line_content.lstrip(" \t"))
    marker_start = line_start + leading_width
    marker_end = marker_start + len(PROMPT_SCENE_MARKER)
    if marker_end > content_end:
        return None
    if text[marker_start:marker_end] != PROMPT_SCENE_MARKER:
        return None
    raw_title = text[marker_end:content_end]
    if not raw_title.strip():
        return None
    title_left_trim = len(raw_title) - len(raw_title.lstrip())
    title_right_trim = len(raw_title.rstrip())
    title_start = marker_end + title_left_trim
    title_end = marker_end + title_right_trim
    title = text[title_start:title_end]
    normalized_key = normalize_scene_title(title)
    if not normalized_key:
        return None
    return _SceneMarkerCandidate(
        title=title,
        normalized_key=normalized_key,
        marker_range=SourceRange(marker_start, marker_end),
        title_range=SourceRange(title_start, title_end),
        line_range=SourceRange(line_start, content_end),
        content_start=line_end,
    )


def _line_break_length(line: str) -> int:
    """Return the number of trailing newline characters in one split line."""

    if line.endswith("\r\n"):
        return 2
    if line.endswith("\n") or line.endswith("\r"):
        return 1
    return 0


__all__ = [
    "PROMPT_SCENE_MARKER",
    "PromptSceneBlock",
    "PromptSceneDocument",
    "PromptSceneMarker",
    "materialize_scene_prompt",
    "normalize_scene_title",
    "parse_prompt_scene_document",
    "scene_block_at_source_position",
]
