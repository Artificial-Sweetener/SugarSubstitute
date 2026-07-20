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

"""Compose Qt-specific Output pointer and context-menu adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QImage, QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets import MenuAnimationType
from qpane import QPane

from substitute.presentation.canvas.output.composition.context_menu import (
    output_context_menu_controller_for_host,
)
from substitute.presentation.canvas.output.composition.grid import (
    output_grid_event_controller_for_host,
)
from substitute.presentation.canvas.output.composition.interaction import (
    output_interaction_controller_for_host,
)
from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.output.output_canvas_context_menu_controller import (
    OutputCanvasContextMenuController,
)
from substitute.presentation.canvas.output.output_canvas_grid_event_controller import (
    OutputCanvasGridEventController,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    GridPoint,
    OutputCanvasInteractionController,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
)
from substitute.presentation.canvas.qpane.canvas_route_projector import (
    OutputRouteProjector,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.widgets.menu_icons import transparent_menu_icon
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas


@dataclass(frozen=True, slots=True)
class OutputQtInteractionComposition:
    """Group Qt interaction collaborators composed as one platform concern."""

    pointer: OutputCanvasInteractionController
    context_menu: OutputCanvasContextMenuController
    grid_events: OutputCanvasGridEventController


def compose_output_qt_interaction(
    host: OutputCanvas,
    *,
    asset_lookup: OutputCanvasAssetLookup,
    route_projector: OutputRouteProjector,
    compare_controller: OutputCompareController,
) -> OutputQtInteractionComposition:
    """Compose pointer, grid-event, and context-menu Qt adapters."""

    pointer = output_interaction_controller_for_host(
        host,
        set_control_mode=host.pane.setControlMode,
        cursor_control_mode=QPane.CONTROL_MODE_CURSOR,
        panzoom_control_mode=QPane.CONTROL_MODE_PANZOOM,
    )
    grid_events = output_grid_event_controller_for_host(
        host,
        route_projector=route_projector,
        interaction_controller=pointer,
        watched_is_pane=lambda watched: watched is host.pane,
        is_mouse_event=lambda event: isinstance(event, QMouseEvent),
        event_type=lambda event: cast(QMouseEvent, event).type(),
        event_is_left_button=lambda event: (
            cast(QMouseEvent, event).button() == Qt.MouseButton.LeftButton
        ),
        event_position=lambda event: cast(
            GridPoint, cast(QMouseEvent, event).position().toPoint()
        ),
        drag_distance=QApplication.startDragDistance,
        press_type=QEvent.Type.MouseButtonPress,
        release_type=QEvent.Type.MouseButtonRelease,
        update_tabbar_container=lambda: update_output_tabbar_container(host),
    )
    context_menu = output_context_menu_controller_for_host(
        host,
        asset_lookup=asset_lookup,
        compare_mode_controller=compare_controller.set_compare_mode_enabled,
        output_route_projector=route_projector,
        open_single_external_editor=lambda: host._open_single_external_editor,
        open_all_external_editor=lambda: host._open_all_external_editor,
        reveal_asset=lambda: host._reveal_output_asset,
        menu_renderer=lambda parent, model: QFluentMenuRenderer(
            parent=cast(QWidget, parent)
        ).render(model),
        compare_enabled_icon=lambda: FIF.ACCEPT.icon(),
        compare_disabled_icon=transparent_menu_icon,
        copy_icon=lambda: FIF.COPY,
        open_external_icon=lambda: FIF.PHOTO,
        open_all_external_icon=lambda: AppIcon.IMAGE_MULTIPLE_20_REGULAR,
        reveal_asset_icon=lambda: AppIcon.FOLDER_OPEN_20_REGULAR,
        dock_action_icon=lambda: (
            FIF.FULL_SCREEN if not host._canvas_detached else FIF.BACK_TO_WINDOW
        ),
        menu_animation_type=lambda: MenuAnimationType.DROP_DOWN,
        map_to_global=lambda pos: host.pane.mapToGlobal(pos),
        current_image=lambda: host.pane.currentImage,
        clipboard_set_image=lambda image: _set_clipboard_image(image),
    )
    host.pane.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    host.pane.customContextMenuRequested.connect(
        lambda position: context_menu.show_context_menu(position)
    )
    return OutputQtInteractionComposition(pointer, context_menu, grid_events)


def _set_clipboard_image(image: object) -> None:
    """Copy a QImage payload while rejecting invalid adapter values."""

    if isinstance(image, QImage):
        QGuiApplication.clipboard().setImage(image)


__all__ = ["OutputQtInteractionComposition", "compose_output_qt_interaction"]
