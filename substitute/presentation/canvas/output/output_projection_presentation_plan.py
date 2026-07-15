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

"""Resolve one deterministic visible mode for an Output projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_resolution import (
    reconcile_output_compare_state,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)


class OutputProjectionMode(str, Enum):
    """Name the single visible presentation selected for a projection."""

    COMPARE = "compare"
    SCENE_OVERVIEW = "scene_overview"
    SOURCE_GRID = "source_grid"
    IMAGE = "image"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class OutputProjectionPresentationPlan:
    """Describe the complete route choice before mutating the Output widget."""

    mode: OutputProjectionMode
    projection: OutputCanvasProjection
    compare_state: OutputCompareState
    scene_groups: Mapping[str, OutputCanvasSceneGroup]
    source_groups: Mapping[str, OutputCanvasSourceGroup]
    active_image_id: UUID | None = None
    active_image_entry: tuple[str, OutputCanvasImageItem] | None = None


def resolve_output_projection_presentation(
    projection: OutputCanvasProjection,
    *,
    scene_groups: Mapping[str, OutputCanvasSceneGroup],
) -> OutputProjectionPresentationPlan:
    """Resolve exactly one compare, scene, source-grid, image, or empty mode."""

    compare_state = reconcile_output_compare_state(
        projection,
        projection.compare_state,
    )
    source_groups = OutputCanvasRouteModel.visible_source_groups_by_key(
        projection,
        scene_groups_by_key=scene_groups,
        active_scene_overview=projection.active_scene_overview,
        active_scene_key=projection.active_scene_key,
        scene_count=projection.scene_count,
    )
    if compare_state.enabled:
        mode = OutputProjectionMode.COMPARE
    elif projection.scene_count > 1 and projection.active_scene_overview:
        mode = OutputProjectionMode.SCENE_OVERVIEW
    elif (
        projection.active_set_index == 0
        and projection.active_source_key in source_groups
    ):
        mode = OutputProjectionMode.SOURCE_GRID
    else:
        active_entry = (
            OutputCanvasRouteModel.output_item_for_image_id(
                source_groups,
                projection.active_uuid,
            )
            if projection.active_uuid is not None
            else None
        )
        mode = (
            OutputProjectionMode.IMAGE
            if projection.active_uuid is not None and active_entry is not None
            else OutputProjectionMode.EMPTY
        )
        return OutputProjectionPresentationPlan(
            mode=mode,
            projection=projection,
            compare_state=compare_state,
            scene_groups=scene_groups,
            source_groups=source_groups,
            active_image_id=projection.active_uuid,
            active_image_entry=active_entry,
        )
    return OutputProjectionPresentationPlan(
        mode=mode,
        projection=projection,
        compare_state=compare_state,
        scene_groups=scene_groups,
        source_groups=source_groups,
    )


__all__ = [
    "OutputProjectionMode",
    "OutputProjectionPresentationPlan",
    "resolve_output_projection_presentation",
]
