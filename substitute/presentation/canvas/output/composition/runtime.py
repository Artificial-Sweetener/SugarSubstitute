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

"""Assemble the typed lifetime bundle for an Output canvas host."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.canvas.output.composition.core_runtime import (
    compose_output_core_runtime,
)
from substitute.presentation.canvas.output.composition.compare import (
    output_compare_controller_for_host,
    output_compare_material_gap_overlay,
    output_compare_presenter,
    output_compare_rendering_controller_for_host,
)
from substitute.presentation.canvas.output.composition.grid_runtime import (
    compose_output_grid_runtime,
    current_output_viewport_extent,
)
from substitute.presentation.canvas.output.composition.qt_interaction import (
    compose_output_qt_interaction,
)
from substitute.presentation.canvas.output.composition.qt_navigation import (
    compose_output_navigation_runtime,
    source_selector_width_for_text,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    visible_output_compare_state,
)
from substitute.presentation.canvas.output.output_compare_projection_presenter import (
    OutputCompareProjectionCallbacks,
    OutputCompareProjectionPresenter,
    sync_output_comparison_navigation_buttons,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    sync_output_scene_selector_button,
    sync_output_set_selector_button,
    sync_output_source_selector_button,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_canvas_projection_controller import (
    OutputCanvasProjectionController,
)
from substitute.presentation.canvas.output.output_projection_presenter import (
    OutputProjectionChromeCallbacks,
    OutputProjectionPresenter,
)
from substitute.presentation.canvas.output.composition.runtime_types import (
    OutputCanvasRuntime,
    OutputCompareRuntime,
    OutputCoreRuntime,
    OutputGridRuntime,
    OutputInteractionRuntime,
    OutputNavigationRuntime,
    OutputPreviewRuntime,
    OutputProjectionRuntime,
)

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas

_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28


def compose_output_canvas_runtime(
    host: OutputCanvas,
    *,
    final_output_payload_lookup: Callable[[UUID], object | None] | None,
    final_output_metadata_lookup: Callable[[UUID], OutputImageMeta | None] | None,
    route_session_boundary: CanvasRouteSessionBoundaryPort | None,
) -> OutputCanvasRuntime:
    """Compose every Output feature exactly once around an initialized Qt host."""

    core = compose_output_core_runtime(
        host,
        final_output_payload_lookup=final_output_payload_lookup,
        final_output_metadata_lookup=final_output_metadata_lookup,
        route_session_boundary=route_session_boundary,
    )
    asset_lookup = core.runtime.asset_lookup
    route_presenter = core.runtime.route_presenter
    route_projector = core.runtime.route_projector
    route_binding = core.route_binding
    image_routes = core.image_routes
    grid = compose_output_grid_runtime(
        host,
        asset_lookup=asset_lookup,
        route_presenter=route_presenter,
        route_projector=route_projector,
    )
    grid_reflow = grid.reflow
    compare_presenter = output_compare_presenter(route_projector)
    compare_rendering_controller = output_compare_rendering_controller_for_host(
        host,
        route_projector=route_projector,
        output_compare_presenter=lambda: compare_presenter,
        bind_output_route_projector=lambda route: (
            host._runtime.projection.controller.bind_output_route_projector(route)
        ),
    )
    compare_controller = output_compare_controller_for_host(
        host,
        output_compare_presenter=lambda: compare_presenter,
        sync_compare_projection=lambda projection, state: (
            host._runtime.projection.controller.sync_compare_projection(
                projection,
                state,
            )
        ),
        sync_compare_rendering=(
            lambda: compare_rendering_controller.sync_compare_rendering()
        ),
        update_tabbar_container=lambda: update_output_tabbar_container(host),
        sync_scene_selector_button=lambda: sync_output_scene_selector_button(host),
        sync_set_selector_button=lambda: sync_output_set_selector_button(host),
        sync_source_selector_button=lambda: sync_output_source_selector_button(host),
        sync_comparison_nav_buttons=(
            lambda: sync_output_comparison_navigation_buttons(host)
        ),
        source_selector_width_for_text=lambda text: source_selector_width_for_text(
            host, text
        ),
        source_selector_min_width=_SOURCE_SELECTOR_MIN_WIDTH,
    )
    host._projection_workflow_id = ""
    compare_material_gap_overlay = output_compare_material_gap_overlay(
        pane=host.pane,
        compare_enabled=lambda: visible_output_compare_state(host).enabled,
    )
    comparison_changed = getattr(host.pane, "comparisonChanged", None)
    connect_comparison_changed = getattr(comparison_changed, "connect", None)
    if callable(connect_comparison_changed):
        connect_comparison_changed(
            lambda state: compare_controller.on_pane_comparison_changed(state)
        )
    qt_interaction = compose_output_qt_interaction(
        host,
        asset_lookup=asset_lookup,
        route_projector=route_projector,
        compare_controller=compare_controller,
    )
    interaction_controller = qt_interaction.pointer

    navigation_runtime = compose_output_navigation_runtime(
        host,
        compare_controller=compare_controller,
    )
    source_tabs_controller = navigation_runtime.source_tabs
    compare_projection_presenter = OutputCompareProjectionPresenter(
        view=host,
        compare_controller=compare_controller,
        source_tabs=source_tabs_controller,
        interaction=interaction_controller,
        rendering=compare_rendering_controller,
        callbacks=OutputCompareProjectionCallbacks(
            sync_scene_selector=lambda: sync_output_scene_selector_button(host),
            sync_set_selector=lambda: sync_output_set_selector_button(host),
            sync_source_selector=lambda: sync_output_source_selector_button(host),
            sync_comparison_navigation=lambda: (
                sync_output_comparison_navigation_buttons(host)
            ),
            update_tabbar=lambda: update_output_tabbar_container(host),
        ),
    )
    projection_presenter = OutputProjectionPresenter(
        view=host,
        route_binding=route_binding,
        image_routes=image_routes,
        compare_route_presenter=compare_presenter,
        compare_projection_presenter=compare_projection_presenter,
        source_tabs=source_tabs_controller,
        interaction=interaction_controller,
        present_current_grid=lambda: grid_reflow.present_current_grid(
            current_output_viewport_extent(host)
        ),
        cancel_grid=grid_reflow.cancel,
        chrome=OutputProjectionChromeCallbacks(
            sync_scene_selector=lambda: sync_output_scene_selector_button(host),
            sync_set_selector=lambda: sync_output_set_selector_button(host),
            sync_source_selector=lambda: sync_output_source_selector_button(host),
            update_tabbar=lambda: update_output_tabbar_container(host),
        ),
    )
    projection_controller = OutputCanvasProjectionController(
        route_binding=route_binding,
        image_routes=image_routes,
        presenter=projection_presenter,
        compare_presenter=compare_projection_presenter,
    )
    runtime = OutputCanvasRuntime(
        core=core.runtime,
        grid=OutputGridRuntime(
            source_composer=grid.source_composer,
            scene_composer=grid.scene_composer,
            route_application=grid.route_application,
            reflow=grid_reflow,
            event_controller=qt_interaction.grid_events,
        ),
        preview=core.preview,
        compare=OutputCompareRuntime(
            presenter=compare_presenter,
            controller=compare_controller,
            rendering_controller=compare_rendering_controller,
            material_gap_overlay=compare_material_gap_overlay,
        ),
        navigation=navigation_runtime,
        interaction=OutputInteractionRuntime(
            pointer=interaction_controller,
            context_menu=qt_interaction.context_menu,
        ),
        projection=OutputProjectionRuntime(controller=projection_controller),
    )
    return runtime


__all__ = [
    "OutputCanvasRuntime",
    "OutputCompareRuntime",
    "OutputCoreRuntime",
    "OutputGridRuntime",
    "OutputInteractionRuntime",
    "OutputNavigationRuntime",
    "OutputPreviewRuntime",
    "OutputProjectionRuntime",
    "compose_output_canvas_runtime",
]
