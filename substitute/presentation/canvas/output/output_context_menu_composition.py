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

"""Compose Output's established and grid-target context menus at the shell boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from cutecanvas import CanvasContentReference

from substitute.presentation.canvas.output.output_canvas_context_menu import (
    OutputCanvasContextMenu,
)
from substitute.presentation.canvas.output.output_context_menu_router import (
    OutputContextMenuRouter,
)
from substitute.presentation.canvas.output.output_grid_context_menu import (
    OutputGridContextMenu,
)

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas


def compose_output_context_menu(
    host: OutputCanvas,
    *,
    request_copy: Callable[[CanvasContentReference], None],
) -> OutputContextMenuRouter:
    """Connect one Output host's document actions to CuteCanvas context requests."""

    document = host.document
    route_projector = host.route_projector
    workspace = host.workspace
    output_menu = OutputCanvasContextMenu(
        parent=host,
        current_image_id=route_projector.current_image_id_for_event,
        content_reference_for=document.content_reference_for,
        image_payload=document.image_payload,
        image_metadata=host.final_output_metadata,
        projection=lambda: host._output_projection,
        image_is_authorized=route_projector.is_image_allowed_for_transfer,
        compare_enabled=lambda: host.visible_compare_state.enabled,
        set_compare_enabled=host.set_compare_mode_enabled,
        active_scene_overview=lambda: host.active_scene_overview,
        active_set_index=lambda: host.active_set_index,
        request_copy=request_copy,
        open_single_editor=host.single_external_editor,
        open_all_editor=host.all_external_editor,
        reveal_asset=host.output_asset_revealer,
        canvas_detached=lambda: host.canvas_detached,
        request_dock_action=host.dockActionRequested.emit,
    )
    router = OutputContextMenuRouter(
        presentation_kind=lambda: workspace.session.presentation.kind,
        output_menu=output_menu,
        grid_menu=OutputGridContextMenu(
            parent=host,
            request_copy=request_copy,
            image_id_for_reference=document.image_id_for_content_reference,
            image_payload=document.image_payload,
            image_metadata=host.final_output_metadata,
            image_is_authorized=route_projector.is_image_allowed_for_transfer,
            open_single_editor=host.single_external_editor,
            reveal_asset=host.output_asset_revealer,
            canvas_detached=lambda: host.canvas_detached,
            request_dock_action=host.dockActionRequested.emit,
        ),
    )
    host.install_transfer_context_handler(router.show)
    return router


__all__ = ["compose_output_context_menu"]
