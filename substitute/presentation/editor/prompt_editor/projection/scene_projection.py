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

"""Plan canonical scene tokens and classify source-local topology edits."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor import parse_prompt_scene_projection_document
from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptDocumentSemantics,
)
from substitute.domain.prompt import parse_prompt_scene_document

from .model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)


@dataclass(frozen=True, slots=True)
class PromptSceneProjectionStructureItem:
    """Describe one scene token shape derived directly from prompt source."""

    line_start: int
    line_end: int
    title_start: int
    title_end: int
    title: str
    normalized_key: str
    duplicate: bool


class PromptSceneProjectionPlanner:
    """Own canonical scene-token construction and local topology decisions."""

    def __init__(self, document_semantics: PromptDocumentSemantics) -> None:
        """Store the replaceable document capability owner used by projection."""

        self._document_semantics = document_semantics

    def build_tokens(
        self,
        source_text: str,
        *,
        scene_error_keys: frozenset[str],
    ) -> tuple[PromptProjectionToken, ...]:
        """Build every scene token supported by the active document semantics."""

        return tuple(
            PromptProjectionToken(
                token_id=f"scene:{index}:{item.line_start}",
                kind=PromptProjectionTokenKind.SCENE,
                source_start=item.line_start,
                source_end=item.line_end,
                display_text=item.title,
                value_text=item.normalized_key,
                style_variant=(
                    "scene_error"
                    if item.duplicate or item.normalized_key in scene_error_keys
                    else "scene_title"
                ),
                exists=(
                    not item.duplicate and item.normalized_key not in scene_error_keys
                ),
                content_start=item.title_start,
                content_end=item.title_end,
                navigation_mode=PromptProjectionTokenNavigationMode.TEXT_CONTENT,
            )
            for index, item in enumerate(self.structure(source_text))
        )

    def structure(
        self,
        source_text: str,
    ) -> tuple[PromptSceneProjectionStructureItem, ...]:
        """Return scene-derived geometry identity for one source snapshot."""

        if not self._document_semantics.scenes_enabled:
            return ()
        document = parse_prompt_scene_projection_document(source_text)
        return tuple(
            PromptSceneProjectionStructureItem(
                line_start=scene.marker.line_range.start,
                line_end=scene.marker.line_range.end,
                title_start=scene.marker.title_range.start,
                title_end=scene.marker.title_range.end,
                title=scene.marker.title,
                normalized_key=scene.marker.normalized_key,
                duplicate=scene.marker.duplicate,
            )
            for scene in document.scenes
        )

    def edit_requires_canonical_rebuild(
        self,
        previous_source_text: str,
        next_source_text: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one edit creates or destroys a scene marker locally."""

        if not self._document_semantics.scenes_enabled:
            return False
        if not 0 <= start <= end <= len(previous_source_text):
            return True
        replacement_length = len(next_source_text) - (
            len(previous_source_text) - (end - start)
        )
        if replacement_length < 0:
            return True
        if (
            previous_source_text[:start]
            + next_source_text[start : start + replacement_length]
            + previous_source_text[end:]
            != next_source_text
        ):
            return True
        return _affected_scene_count(
            previous_source_text,
            start=start,
            end=end,
        ) != _affected_scene_count(
            next_source_text,
            start=start,
            end=start + replacement_length,
        )


def _affected_scene_count(source_text: str, *, start: int, end: int) -> int:
    """Count markers only on source lines touched by one contiguous edit."""

    line_start = source_text.rfind("\n", 0, start) + 1
    line_end = source_text.find("\n", end)
    if line_end < 0:
        line_end = len(source_text)
    else:
        line_end += 1
    return len(parse_prompt_scene_document(source_text[line_start:line_end]).scenes)


__all__ = [
    "PromptSceneProjectionPlanner",
    "PromptSceneProjectionStructureItem",
]
