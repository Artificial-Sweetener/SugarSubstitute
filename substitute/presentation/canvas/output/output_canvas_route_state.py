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

"""Read visible Output route state through one typed host adapter."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_revision_cache,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)


@dataclass(frozen=True, slots=True)
class OutputRouteStateSnapshot:
    """Capture projection and transient fields used by visible route selectors."""

    projection: OutputCanvasProjection | None
    preview_scene_groups: dict[str, OutputCanvasSceneGroup]
    active_scene_overview: bool
    active_scene_key: str | None
    scene_count: int


def output_route_state_snapshot(host: object) -> OutputRouteStateSnapshot:
    """Read one host through the sole Output route-state adaptation boundary."""

    projection = getattr(host, "_output_projection", None)
    scene_key = getattr(host, "active_scene_key", None)
    return OutputRouteStateSnapshot(
        projection=(
            projection if isinstance(projection, OutputCanvasProjection) else None
        ),
        preview_scene_groups=dict(
            output_revision_cache(host).preview_scene_groups_by_key
        ),
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
        active_scene_key=scene_key if isinstance(scene_key, str) else None,
        scene_count=int(getattr(host, "scene_count", 0)),
    )


def output_scene_groups_by_key(
    state: OutputRouteStateSnapshot,
) -> dict[str, OutputCanvasSceneGroup]:
    """Return projection scenes with revision-scoped preview overlays."""

    return OutputCanvasRouteModel.scene_groups_by_key(
        state.projection,
        preview_scene_groups_by_key=state.preview_scene_groups,
    )


def visible_output_source_groups_by_key(
    state: OutputRouteStateSnapshot,
) -> dict[str, OutputCanvasSourceGroup]:
    """Return source selector rows visible for one typed route snapshot."""

    return OutputCanvasRouteModel.visible_source_groups_by_key(
        state.projection,
        scene_groups_by_key=output_scene_groups_by_key(state),
        active_scene_overview=state.active_scene_overview,
        active_scene_key=state.active_scene_key,
        scene_count=state.scene_count,
    )


__all__ = [
    "OutputRouteStateSnapshot",
    "output_route_state_snapshot",
    "output_scene_groups_by_key",
    "visible_output_source_groups_by_key",
]
