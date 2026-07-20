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

"""Verify Output interaction feature composition helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareState,
)
from substitute.presentation.canvas.output.composition.assets import (
    output_canvas_asset_lookup,
)
from substitute.presentation.canvas.output.composition.context_menu import (
    output_context_menu_controller_for_host,
)
from substitute.presentation.canvas.output.composition.interaction import (
    output_interaction_controller_for_host,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    GridPoint,
)
from substitute.domain.workflow import ImageMeta
from tests.support.output_canvas.composition_fakes import (
    _ContextAction,
    _ContextMenu,
    _ContextToggleAction,
    _Projector,
    _Signal,
    _image_item,
    _render_context_menu,
)


def test_output_canvas_composition_builds_interaction_controller_for_host() -> None:
    """Interaction-controller composition should wire Output host pointer state."""

    host = SimpleNamespace(_grid_click_press_pos=None)
    control_modes: list[object] = []
    controller = output_interaction_controller_for_host(
        host,
        set_control_mode=control_modes.append,
        cursor_control_mode="cursor",
        panzoom_control_mode="panzoom",
    )
    point = cast(GridPoint, object())

    controller.set_press_position(point)
    controller.set_grid_interaction_locked(True)
    controller.set_grid_interaction_locked(False)

    assert host._grid_click_press_pos is point
    assert controller.press_position() is point
    assert control_modes == ["cursor", "panzoom"]


def test_output_canvas_composition_builds_context_menu_controller_for_host() -> None:
    """Context-menu composition should wire Output host state adapters."""

    item = _image_item()
    comparison_item = _image_item(set_index=2)
    payload = object()
    opened: list[list[tuple[object, ImageMeta]]] = []
    compare_calls: list[bool] = []
    dock_signal = _Signal()
    menus: list[_ContextMenu] = []
    projection = OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                "txt",
                "Text",
                {1: item, 2: comparison_item},
            ),
        ),
        active_source_key="txt",
        active_set_index=1,
        active_uuid=item.image_id,
        set_count=2,
    )
    session = bind_output_canvas_session(
        create_canvas_session_boundary(),
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={
            item.image_id: item.image_meta,
            comparison_item.image_id: comparison_item.image_meta,
        },
    )
    host = SimpleNamespace(
        pane=SimpleNamespace(currentImage="image"),
        _asset_lookup=output_canvas_asset_lookup(
            payload_lookup=lambda image_id: (
                payload if image_id == item.image_id else None
            ),
            metadata_lookup=lambda image_id: (
                item.image_meta if image_id == item.image_id else None
            ),
            preview_image_cache=lambda: {},
        ),
        _compare_controller=SimpleNamespace(
            set_compare_mode_enabled=compare_calls.append,
        ),
        _route_projector=_Projector(item.image_id),
        _output_projection=projection,
        _output_session=session,
        _visible_compare_state=OutputCompareState(),
        active_scene_overview=False,
        active_set_index=1,
        _open_single_external_editor=None,
        _open_all_external_editor=opened.append,
        _canvas_detached=True,
        dockActionRequested=dock_signal,
    )
    controller = output_context_menu_controller_for_host(
        host,
        asset_lookup=host._asset_lookup,
        compare_mode_controller=host._compare_controller.set_compare_mode_enabled,
        output_route_projector=host._route_projector,
        open_single_external_editor=lambda: host._open_single_external_editor,
        open_all_external_editor=lambda: host._open_all_external_editor,
        reveal_asset=lambda: None,
        menu_renderer=lambda _parent, model: _render_context_menu(menus, model),
        compare_enabled_icon=lambda: "compare-enabled",
        compare_disabled_icon=lambda: "compare-disabled",
        copy_icon=lambda: "copy",
        open_external_icon=lambda: "photo",
        open_all_external_icon=lambda: "image-multiple",
        reveal_asset_icon=lambda: "folder-open",
        dock_action_icon=lambda: "dock",
        menu_animation_type=lambda: "drop-down",
        map_to_global=lambda pos: ("global", pos),
        current_image=lambda: host.pane.currentImage,
        clipboard_set_image=lambda _image: None,
    )

    controller.show_context_menu("local")
    toggle = menus[0].entries[0]
    dock_action = menus[0].entries[-1]

    assert isinstance(toggle, _ContextToggleAction)
    toggle.trigger()
    controller.open_all_external()
    assert isinstance(dock_action, _ContextAction)
    dock_action.triggered()

    assert compare_calls == [True]
    assert opened == [[(payload, item.image_meta)]]
    assert dock_signal.calls == [()]
    assert menus[0].exec_calls == [(("global", "local"), {"aniType": "drop-down"})]
