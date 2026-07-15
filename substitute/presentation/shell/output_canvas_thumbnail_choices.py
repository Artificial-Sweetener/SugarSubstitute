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

"""Describe output-canvas images available for model thumbnail assignment."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)


@dataclass(frozen=True, slots=True)
class OutputCanvasThumbnailChoice:
    """Describe one final output image that can become a model thumbnail."""

    image_id: UUID
    scene_key: str
    scene_title: str
    scene_order: int
    source_key: str
    source_label: str
    set_index: int
    width: int | None = None
    height: int | None = None


class OutputCanvasThumbnailChoiceProvider(Protocol):
    """Return thumbnail-selectable images from the active output canvas."""

    def choices(self) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return selectable final-output images in deterministic display order."""

    def active_choice(self) -> OutputCanvasThumbnailChoice | None:
        """Return the active concrete output image when one is selected."""


class ProjectionOutputCanvasThumbnailChoiceProvider:
    """Build thumbnail choices from the active output canvas projection."""

    def __init__(
        self,
        projection: Callable[[], OutputCanvasProjection | None],
    ) -> None:
        """Store the projection lookup used when a context menu opens."""

        self._projection = projection

    def choices(self) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return selectable final-output images in deterministic display order."""

        projection = self._projection()
        if projection is None:
            return ()
        if _projection_has_meaningful_scenes(projection):
            return _deduplicated_choices(
                tuple(
                    choice
                    for scene in projection.scene_groups
                    for source in scene.sources
                    for choice in _source_choices(
                        source,
                        scene_key=scene.scene_key,
                        scene_title=scene.title,
                        scene_order=scene.order,
                    )
                )
            )
        return _deduplicated_choices(
            tuple(
                choice
                for source in projection.sources
                for choice in _source_choices(
                    source,
                    scene_key="",
                    scene_title="",
                    scene_order=0,
                )
            )
        )

    def active_choice(self) -> OutputCanvasThumbnailChoice | None:
        """Return the active concrete output image when one is selected."""

        projection = self._projection()
        if projection is None or projection.active_uuid is None:
            return None
        for choice in self.choices():
            if choice.image_id == projection.active_uuid:
                return choice
        return None


def _source_choices(
    source: OutputCanvasSourceGroup,
    *,
    scene_key: str,
    scene_title: str,
    scene_order: int,
) -> tuple[OutputCanvasThumbnailChoice, ...]:
    """Return choices for one source in batch order."""

    return tuple(
        OutputCanvasThumbnailChoice(
            image_id=item.image_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            source_key=source.source_key,
            source_label=source.label,
            set_index=item.set_index,
            width=item.image_meta.width,
            height=item.image_meta.height,
        )
        for _set_index, item in sorted(source.images_by_set.items())
    )


def _deduplicated_choices(
    choices: tuple[OutputCanvasThumbnailChoice, ...],
) -> tuple[OutputCanvasThumbnailChoice, ...]:
    """Return choices deduplicated by image id while preserving order."""

    seen: set[UUID] = set()
    deduplicated: list[OutputCanvasThumbnailChoice] = []
    for choice in choices:
        if choice.image_id in seen:
            continue
        seen.add(choice.image_id)
        deduplicated.append(choice)
    return tuple(deduplicated)


def _projection_has_meaningful_scenes(projection: OutputCanvasProjection) -> bool:
    """Return whether a projection has user-meaningful scene groups."""

    scene_keys = {
        scene.scene_key for scene in projection.scene_groups if scene.scene_key
    }
    if len(scene_keys) > 1:
        return True
    if not scene_keys:
        return False
    return any(
        scene.title.strip() and scene.title.strip() != "Scene"
        for scene in projection.scene_groups
    )


__all__ = [
    "OutputCanvasThumbnailChoice",
    "OutputCanvasThumbnailChoiceProvider",
    "ProjectionOutputCanvasThumbnailChoiceProvider",
]
