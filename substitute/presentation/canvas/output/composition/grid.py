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

"""Compose Output grid route and event collaborators."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    OutputRouteProjectorPort,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    GridPoint,
    OutputCanvasInteractionController,
)
from substitute.presentation.canvas.output.output_canvas_grid_event_controller import (
    OutputCanvasGridEventController,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
    visible_output_source_groups_by_key,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_item,
    activate_output_scene,
)
from substitute.presentation.canvas.output.output_source_grid_composer import (
    OutputSourceGridComposer,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    OutputSceneOverviewComposer,
    OutputSceneOverviewPreview,
)


def output_source_grid_composer(
    payload_lookup: Callable[[UUID], object | None],
    *,
    scene_builder: OutputGridSceneBuilder,
    viewport_extent: Callable[[], CanvasViewportExtent],
) -> OutputSourceGridComposer:
    """Return the composer that selects and builds source-grid route plans."""

    return OutputSourceGridComposer(
        payload_lookup,
        scene_builder=scene_builder,
        viewport_extent=viewport_extent,
    )


def output_grid_event_controller_for_host(
    host: object,
    *,
    route_projector: OutputRouteProjectorPort,
    interaction_controller: OutputCanvasInteractionController,
    watched_is_pane: Callable[[object], bool],
    is_mouse_event: Callable[[object], bool],
    event_type: Callable[[object], object],
    event_is_left_button: Callable[[object], bool],
    event_position: Callable[[object], GridPoint],
    drag_distance: Callable[[], int],
    press_type: object,
    release_type: object,
    update_tabbar_container: Callable[[], None],
) -> OutputCanvasGridEventController:
    """Return the grid event controller wired to an Output canvas host."""

    return OutputCanvasGridEventController(
        interaction_controller=interaction_controller,
        watched_is_pane=watched_is_pane,
        is_mouse_event=is_mouse_event,
        event_type=event_type,
        event_is_left_button=event_is_left_button,
        event_position=event_position,
        drag_distance=drag_distance,
        hit_at=route_projector.hit_test_scene,
        active_scene_overview=lambda: bool(
            getattr(host, "active_scene_overview", False)
        ),
        active_set_index=lambda: int(getattr(host, "active_set_index", 0)),
        active_source_key=lambda: cast(
            str | None,
            getattr(host, "active_source_key", None),
        ),
        source_groups_by_key=lambda: visible_output_source_groups_by_key(
            output_route_state_snapshot(host)
        ),
        activate_scene=lambda scene_key: activate_output_scene(
            host,
            scene_key,
            scene_groups_by_key=output_scene_groups_by_key(
                output_route_state_snapshot(host)
            ),
            update_tabbar_container=update_tabbar_container,
        ),
        activate_item=lambda source_key, item: activate_output_item(
            host,
            source_key,
            item,
            update_tabbar_container=update_tabbar_container,
        ),
        emit_scene_changed=lambda scene_key, overview: getattr(
            host,
            "activeOutputSceneChanged",
        ).emit(scene_key, overview),
        emit_grid_changed=lambda source_key: getattr(
            host,
            "activeOutputGridChanged",
        ).emit(source_key),
        press_type=press_type,
        release_type=release_type,
    )


def output_scene_overview_composer(
    *,
    payload_lookup: Callable[[UUID], object | None],
    preview_lookup: Callable[
        [OutputCanvasSceneGroup], OutputSceneOverviewPreview | None
    ],
    scene_builder: OutputGridSceneBuilder,
    viewport_extent: Callable[[], CanvasViewportExtent],
) -> OutputSceneOverviewComposer:
    """Return the composer that builds scene-overview route requests."""

    return OutputSceneOverviewComposer(
        payload_lookup=payload_lookup,
        preview_lookup=preview_lookup,
        scene_builder=scene_builder,
        viewport_extent=viewport_extent,
    )
