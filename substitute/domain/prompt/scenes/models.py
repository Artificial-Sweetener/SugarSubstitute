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

"""Define immutable scene structure parsed from prompt source."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.prompt.document.ranges import SourceRange


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


__all__ = ["PromptSceneBlock", "PromptSceneDocument", "PromptSceneMarker"]
