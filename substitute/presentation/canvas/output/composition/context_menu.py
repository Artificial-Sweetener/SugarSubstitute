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

"""Compose Output context-menu collaborators."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.canvas.output.output_canvas_context_menu_controller import (
    OutputCanvasContextMenuController,
    OutputContextMenu,
    OutputCurrentImageProjector,
)
from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    visible_output_compare_state,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.widgets.menu_model import MenuModel

from .projection import _allowed_output_image_ids_for, _output_projection_for


def output_context_menu_controller_for_host(
    host: object,
    *,
    asset_lookup: OutputCanvasAssetLookup,
    compare_mode_controller: Callable[[bool], None],
    output_route_projector: OutputCurrentImageProjector,
    open_single_external_editor: Callable[
        [], Callable[[object, OutputImageMeta], bool] | None
    ],
    open_all_external_editor: Callable[
        [], Callable[[list[tuple[object, OutputImageMeta]]], bool] | None
    ],
    reveal_asset: Callable[[], Callable[[OutputImageMeta], bool] | None],
    menu_renderer: Callable[[object, MenuModel], OutputContextMenu],
    compare_enabled_icon: Callable[[], object],
    compare_disabled_icon: Callable[[], object],
    copy_icon: Callable[[], object],
    open_external_icon: Callable[[], object],
    open_all_external_icon: Callable[[], object],
    reveal_asset_icon: Callable[[], object],
    dock_action_icon: Callable[[], object],
    menu_animation_type: Callable[[], object],
    map_to_global: Callable[[object], object],
    current_image: Callable[[], object | None],
    clipboard_set_image: Callable[[object], None],
) -> OutputCanvasContextMenuController:
    """Return the context-menu controller wired to an Output canvas host."""

    return OutputCanvasContextMenuController(
        pane=lambda: getattr(host, "pane"),
        action_parent=lambda: host,
        visible_compare_state=lambda: visible_output_compare_state(host),
        active_scene_overview=lambda: bool(
            getattr(host, "active_scene_overview", False)
        ),
        active_set_index=lambda: int(getattr(host, "active_set_index", 0)),
        output_projection=lambda: _output_projection_for(host),
        set_compare_mode_enabled=compare_mode_controller,
        menu_renderer=menu_renderer,
        compare_enabled_icon=compare_enabled_icon,
        compare_disabled_icon=compare_disabled_icon,
        copy_icon=copy_icon,
        open_external_icon=open_external_icon,
        open_all_external_icon=open_all_external_icon,
        reveal_asset_icon=reveal_asset_icon,
        dock_action_icon=dock_action_icon,
        menu_animation_type=menu_animation_type,
        map_to_global=map_to_global,
        current_image=current_image,
        clipboard_set_image=clipboard_set_image,
        output_route_projector=lambda: output_route_projector,
        final_output_payload=asset_lookup.final_output_payload,
        final_output_metadata=asset_lookup.final_output_metadata,
        open_single_external_editor=open_single_external_editor,
        open_all_external_editor=open_all_external_editor,
        reveal_asset=reveal_asset,
        allowed_image_ids=lambda: _allowed_output_image_ids_for(host),
        dock_action_text=lambda: str(getattr(host, "_dock_action_text", "")),
        request_dock_action=lambda: getattr(host, "dockActionRequested").emit(),
    )
