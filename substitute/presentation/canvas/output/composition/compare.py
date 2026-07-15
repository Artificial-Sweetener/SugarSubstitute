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

"""Compose Output comparison collaborators."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
    OutputRouteProjectorPort,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.presentation.canvas.output.output_canvas_compare_rendering_controller import (
    OutputCanvasCompareRenderingController,
    OutputCompareRenderer,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresenter,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
    OutputCompareStatePresenter,
    store_visible_output_compare_state,
    visible_output_compare_state,
)
from substitute.presentation.canvas.output.output_compare_material_gap import (
    OutputCompareMaterialGapOverlay,
)

from .projection import (
    _active_scene_key_for,
    _active_source_key_for,
    _compare_clear_route_identity,
    _output_projection_for,
)


def output_compare_controller_for_host(
    host: object,
    *,
    output_compare_presenter: Callable[[], OutputCompareStatePresenter],
    sync_compare_projection: Callable[
        [OutputCanvasProjection, OutputCompareState],
        None,
    ],
    sync_compare_rendering: Callable[[], None],
    update_tabbar_container: Callable[[], None],
    sync_scene_selector_button: Callable[[], None],
    sync_set_selector_button: Callable[[], None],
    sync_source_selector_button: Callable[[], None],
    sync_comparison_nav_buttons: Callable[[], None],
    source_selector_width_for_text: Callable[[str], int],
    source_selector_min_width: int,
) -> OutputCompareController:
    """Return the compare controller wired to an Output canvas host."""

    return OutputCompareController(
        output_projection=lambda: _output_projection_for(host),
        visible_compare_state=lambda: visible_output_compare_state(host),
        output_compare_presenter=output_compare_presenter,
        set_visible_compare_state=lambda state: store_visible_output_compare_state(
            host,
            state,
        ),
        emit_compare_changed=getattr(
            getattr(host, "activeOutputCompareChanged", None),
            "emit",
            lambda _state: None,
        ),
        sync_compare_projection=sync_compare_projection,
        sync_compare_rendering=sync_compare_rendering,
        update_tabbar_container=update_tabbar_container,
        active_source_key=lambda: _active_source_key_for(host),
        active_set_index=lambda: int(getattr(host, "active_set_index", 0)),
        scene_count=lambda: int(getattr(host, "scene_count", 0)),
        active_scene_key=lambda: _active_scene_key_for(host),
        set_active_source_key=lambda source_key: setattr(
            host,
            "active_source_key",
            source_key,
        ),
        set_active_set_index=lambda set_index: setattr(
            host,
            "active_set_index",
            set_index,
        ),
        set_active_scene_key=lambda scene_key: setattr(
            host,
            "active_scene_key",
            scene_key,
        ),
        sync_scene_selector_button=sync_scene_selector_button,
        sync_set_selector_button=sync_set_selector_button,
        sync_source_selector_button=sync_source_selector_button,
        sync_comparison_nav_buttons=sync_comparison_nav_buttons,
        set_count_for_sources=OutputCanvasRouteModel.set_count_for_sources,
        base_scene_button=lambda: getattr(host, "scene_selector_button"),
        comparison_scene_button=lambda: getattr(
            host,
            "comparison_scene_selector_button",
        ),
        base_set_button=lambda: getattr(host, "set_selector_button"),
        comparison_set_button=lambda: getattr(
            host,
            "comparison_set_selector_button",
        ),
        base_source_button=lambda: getattr(host, "source_selector_button"),
        comparison_source_button=lambda: getattr(
            host,
            "comparison_source_selector_button",
        ),
        source_selector_width_for_text=source_selector_width_for_text,
        source_selector_min_width=source_selector_min_width,
    )


def output_compare_rendering_controller_for_host(
    host: object,
    *,
    route_projector: OutputRouteProjectorPort,
    output_compare_presenter: Callable[[], OutputCompareRenderer],
    bind_output_route_projector: Callable[[CanvasRouteIdentity], None],
) -> OutputCanvasCompareRenderingController:
    """Return the compare-rendering controller wired to an Output canvas host."""

    return OutputCanvasCompareRenderingController(
        visible_compare_state=lambda: visible_output_compare_state(host),
        output_projection=lambda: _output_projection_for(host),
        output_compare_presenter=output_compare_presenter,
        route_blocked=lambda: bool(
            getattr(host, "active_scene_overview", False)
            or int(getattr(host, "active_set_index", 0)) == 0
        ),
        set_visible_compare_state=lambda state: store_visible_output_compare_state(
            host,
            state,
        ),
        emit_compare_changed=getattr(
            getattr(host, "activeOutputCompareChanged", None),
            "emit",
            lambda _state: None,
        ),
        clear_route_identity=lambda: _compare_clear_route_identity(host),
        bind_output_route_projector=bind_output_route_projector,
        route_projector=lambda: route_projector,
    )


def output_compare_presenter(
    route_projector: OutputRouteProjectorPort,
) -> OutputComparePresenter:
    """Return the presenter that applies compare state through a route projector."""

    return OutputComparePresenter(route_projector)


def output_compare_material_gap_overlay(
    *,
    pane: object,
    compare_enabled: Callable[[], bool],
) -> OutputCompareMaterialGapOverlay:
    """Return the overlay that clears the QPane compare material gap."""

    return OutputCompareMaterialGapOverlay(
        pane=pane,
        compare_enabled=compare_enabled,
    )
