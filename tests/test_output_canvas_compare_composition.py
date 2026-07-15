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

"""Verify Output compare feature composition helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
    OutputRouteProjectorPort,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.presentation.canvas.output.composition.compare import (
    output_compare_controller_for_host,
    output_compare_rendering_controller_for_host,
)
from substitute.presentation.canvas.output.composition.navigation import (
    OutputCanvasPickerHost,
    output_canvas_picker_controller_for,
)
from substitute.presentation.canvas.output.output_canvas_compare_rendering_controller import (
    OutputCanvasCompareRenderingController,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPickerItem
from tests.support.output_canvas.composition_fakes import (
    _CompareRenderer,
    _Host,
    _Presenter,
    _compare_controller,
    _image_item,
)


def test_output_canvas_composition_builds_compare_controller_for_host() -> None:
    """Compare-controller composition should wire Output host state adapters."""

    syncs: list[str] = []
    source_groups = (
        OutputCanvasSourceGroup("txt", "Text", {1: _image_item()}),
        OutputCanvasSourceGroup("up", "Upscale", {1: _image_item()}),
    )
    host = _Host(
        _output_projection=OutputCanvasProjection(
            sources=source_groups,
            active_source_key="txt",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        ),
        _visible_compare_state=OutputCompareState(
            enabled=True,
            base=OutputCompareSelection(None, 1, "txt"),
        ),
    )
    controller = output_compare_controller_for_host(
        host,
        output_compare_presenter=lambda: _Presenter(),
        sync_compare_projection=lambda _projection, _state: syncs.append("projection"),
        sync_compare_rendering=lambda: syncs.append("rendering"),
        update_tabbar_container=lambda: syncs.append("tabbar"),
        sync_scene_selector_button=lambda: syncs.append("scene"),
        sync_set_selector_button=lambda: syncs.append("set"),
        sync_source_selector_button=lambda: syncs.append("source"),
        sync_comparison_nav_buttons=lambda: syncs.append("nav"),
        source_selector_width_for_text=lambda text: len(text) + 10,
        source_selector_min_width=44,
    )

    controller.set_compare_source("base", "up")

    assert host.active_source_key == "up"
    assert host._visible_compare_state.base == OutputCompareSelection(None, 1, "up")
    assert host.activeOutputCompareChanged.calls == [(host._visible_compare_state,)]
    assert syncs == ["scene", "set", "source", "nav", "rendering", "tabbar"]
    assert controller.compare_source_button("comparison") == "comparison-source-button"
    assert (
        controller.compare_source_picker_row_width(
            (CanvasNavPickerItem("up", "Upscale"),)
        )
        == 44
    )


def test_output_canvas_composition_builds_compare_rendering_controller_for_host() -> (
    None
):
    """Compare-rendering composition should wire Output host route adapters."""

    projection = OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
    )
    projector = object()
    bound_routes: list[CanvasRouteIdentity] = []
    host = SimpleNamespace(
        _output_projection=projection,
        _visible_compare_state=OutputCompareState(enabled=True),
        _route_projector=projector,
        active_scene_overview=False,
        active_scene_key="scene-a",
        active_source_key="source-a",
        active_set_index=0,
    )

    controller = output_compare_rendering_controller_for_host(
        host,
        route_projector=cast(OutputRouteProjectorPort, projector),
        output_compare_presenter=lambda: _CompareRenderer(),
        bind_output_route_projector=bound_routes.append,
    )

    assert isinstance(controller, OutputCanvasCompareRenderingController)
    assert controller.output_projection() is projection
    assert controller.visible_compare_state() is host._visible_compare_state
    assert controller.route_projector() is projector
    assert controller.route_blocked() is True
    clear_route = controller.clear_route_identity()
    assert clear_route.route_kind == "source_grid"
    assert clear_route.route_key == "scene:scene-a;source:source-a;set:0"
    controller.bind_output_route_projector(clear_route)
    assert bound_routes == [clear_route]


def test_output_canvas_picker_composition_wires_compare_source_picker() -> None:
    """Picker composition should route compare source changes through controller."""

    host = _Host(
        _output_projection=OutputCanvasProjection(
            sources=(),
            active_source_key="txt",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        )
    )
    compare_source_sets: list[tuple[str, str]] = []
    controller = output_canvas_picker_controller_for(
        cast(OutputCanvasPickerHost, host),
        visible_compare_state=lambda: OutputCompareState(enabled=True),
        visible_source_groups_by_key=dict,
        scene_groups_by_key=dict,
        scene_picker_row_width=lambda _items: 91,
        source_picker_row_width=lambda _items: 123,
        compare_controller=lambda: _compare_controller(
            compare_source_sets=compare_source_sets
        ),
        update_tabbar_container=lambda: None,
    )

    controller.show_source_picker()

    assert host._source_picker.calls
    _anchor, _items, _active_key, _row_width, callback = host._source_picker.calls[0]
    callback("up")

    assert compare_source_sets == [("base", "up")]
