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

"""Define immutable Output canvas projection values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from substitute.domain.generation import OutputResultPosition
from substitute.domain.workflow import ImageMeta, OutputCompareState


@dataclass(frozen=True)
class OutputCanvasImageItem:
    """Describe one selectable output image in a source/set grid."""

    image_id: UUID
    image_meta: ImageMeta
    set_index: int
    position: OutputResultPosition | None = None


@dataclass(frozen=True)
class OutputCanvasSourceGroup:
    """Describe one output-producing source rendered as an output tab."""

    source_key: str
    label: str
    images_by_set: Mapping[int, OutputCanvasImageItem]
    label_is_default: bool = False

    def first_item(self) -> OutputCanvasImageItem | None:
        """Return the first concrete item owned by this CubeOutput source."""

        if not self.images_by_set:
            return None
        return self.images_by_set[min(self.images_by_set)]


@dataclass(frozen=True)
class OutputCanvasSceneGroup:
    """Describe one prompt scene grouping rendered above source and batch."""

    scene_run_id: str
    scene_key: str
    title: str
    order: int
    sources: tuple[OutputCanvasSourceGroup, ...]
    preview_image_id: UUID | None = None
    primary_image_id: UUID | None = None
    representative_source_key: str | None = None
    representative_set_index: int | None = None
    status: str = "completed"
    title_is_default: bool = False


@dataclass(frozen=True)
class OutputCanvasProjection:
    """Describe the output canvas selector state for one workflow."""

    sources: tuple[OutputCanvasSourceGroup, ...]
    active_source_key: str | None
    active_set_index: int
    active_uuid: UUID | None
    set_count: int
    scene_groups: tuple[OutputCanvasSceneGroup, ...] = ()
    active_scene_key: str | None = None
    active_scene_overview: bool = False
    scene_count: int = 0
    compare_state: OutputCompareState = OutputCompareState()

    def source_for_key(self, source_key: str) -> OutputCanvasSourceGroup | None:
        """Return source group for a stable source key when available."""

        for source in self.sources:
            if source.source_key == source_key:
                return source
        return None

    def item_for(
        self,
        *,
        source_key: str,
        set_index: int,
    ) -> OutputCanvasImageItem | None:
        """Return the exact item for a CubeOutput source/set selection."""

        source = self.source_for_key(source_key)
        if source is None:
            return None
        return source.images_by_set.get(set_index)

    def first_item_for_set(self, set_index: int) -> OutputCanvasImageItem | None:
        """Return the first source item for one set index when available."""

        for source in self.sources:
            item = source.images_by_set.get(set_index)
            if item is not None:
                return item
        return None


__all__ = [
    "OutputCanvasImageItem",
    "OutputCanvasProjection",
    "OutputCanvasSceneGroup",
    "OutputCanvasSourceGroup",
]
