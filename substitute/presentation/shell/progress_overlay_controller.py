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

"""Position the shell progress overlay against live toolbar geometry."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint

from substitute.shared.startup_trace import trace_mark


class ProgressOverlayController:
    """Own shell progress overlay placement and width fallback policy."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose progress overlay should be positioned."""

        self._shell = shell

    def position_progress_overlay(self) -> None:
        """Align the workflow progress bar bottom edge with the menu bar bottom."""

        trace_mark(
            "main_window.position_progress_overlay.start",
            menu_width=self._shell.menu_bar.width(),
            menu_height=self._shell.menu_bar.height(),
        )
        menu_top_left = self._shell.menu_bar.mapTo(self._shell, QPoint(0, 0))
        menu_bottom_edge = self._shell.menu_bar.mapTo(
            self._shell,
            QPoint(0, self._shell.menu_bar.height()),
        )
        workflow_bar_height = self._shell.workflowOverlayBar.height()
        overlay_height = self._shell.progressOverlay.height()
        overlay_y = menu_bottom_edge.y() - workflow_bar_height
        overlay_width = self.progress_overlay_width()
        self._shell.progressOverlay.setGeometry(
            menu_top_left.x(),
            overlay_y,
            overlay_width,
            overlay_height,
        )
        trace_mark(
            "main_window.position_progress_overlay.end",
            overlay_y=overlay_y,
            overlay_height=overlay_height,
            overlay_width=overlay_width,
        )

    def progress_overlay_width(self) -> int:
        """Return the widest reliable toolbar overlay width after layout changes."""

        width = int(self._shell.menu_bar.width())
        central_widget_getter = getattr(self._shell, "centralWidget", None)
        central_widget = (
            central_widget_getter() if callable(central_widget_getter) else None
        )
        if central_widget is not None and central_widget.width() > 0:
            return max(width, int(central_widget.width()))
        window_width_getter = getattr(self._shell, "width", None)
        if not callable(window_width_getter):
            return width
        return max(width, int(window_width_getter()))


def progress_overlay_controller_for(shell: Any) -> ProgressOverlayController:
    """Return the composed progress overlay controller for a shell."""

    controller = getattr(shell, "progress_overlay_controller", None)
    if isinstance(controller, ProgressOverlayController):
        return controller
    controller = ProgressOverlayController(shell)
    setattr(shell, "progress_overlay_controller", controller)
    return controller


__all__ = [
    "ProgressOverlayController",
    "progress_overlay_controller_for",
]
