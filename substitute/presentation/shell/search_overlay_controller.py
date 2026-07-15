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

"""Coordinate the floating editor search overlay."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QPoint, Qt

from substitute.shared.logging.logger import get_logger, log_info
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("presentation.shell.search_overlay_controller")


class SearchOverlayController:
    """Own floating search-box placement and shortcut handling."""

    def __init__(self, shell: Any) -> None:
        """Store the shell that owns the search box and active editor panel."""

        self._shell = shell

    def position_search_box(self) -> None:
        """Center the floating search box over the active editor panel surface."""

        active_panel = self._shell.active_editor_panel
        trace_mark(
            "main_window.position_search_box.start",
            active_editor_panel_present=active_panel is not None,
        )
        if active_panel is None:
            trace_mark(
                "main_window.position_search_box.skip",
                reason="no_active_editor_panel",
            )
            return
        editor_top_left = active_panel.mapTo(self._shell, QPoint(0, 0))
        editor_width = active_panel.width()
        box_width = self._shell.contextSearchBox.width()
        if box_width == 0:
            self._shell.contextSearchBox.adjustSize()
            box_width = self._shell.contextSearchBox.width()
        x = editor_top_left.x() + (editor_width - box_width) // 2
        y = editor_top_left.y() + 16
        self._shell.contextSearchBox.move(x, y)
        self._shell.contextSearchBox.raise_()
        trace_mark(
            "main_window.position_search_box.end",
            x=x,
            y=y,
            editor_width=editor_width,
            box_width=box_width,
        )

    def handle_event_filter_event(self, event: Any) -> bool | None:
        """Handle search overlay keyboard events or return no decision."""

        if event.type() != QEvent.Type.KeyPress:
            return None

        search_box = self._shell.contextSearchBox
        search_bar = search_box.searchLineEdit()

        if event.key() == Qt.Key.Key_Escape and self._shell.focusWidget() is search_bar:
            search_box.hide()
            self._focus_active_search_match()
            log_info(
                _LOGGER,
                "floating search overlay closed from keyboard",
                reason="escape",
            )
            return True

        if (
            event.key() == Qt.Key.Key_F
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            if not search_box.isVisible():
                search_box.show()
                search_box.adjustSize()
            self.position_search_box()
            search_bar.setFocus()
            search_bar.selectAll()
            log_info(
                _LOGGER,
                "floating search overlay focused from keyboard",
                shortcut="ctrl_f",
            )
            return True

        return None

    def _focus_active_search_match(self) -> None:
        """Restore focus to the active editor search match when possible."""

        active_panel = self._shell.active_editor_panel
        if active_panel is None:
            return
        focus_current_search_match = getattr(
            active_panel,
            "focus_current_search_match",
            None,
        )
        if callable(focus_current_search_match):
            focus_current_search_match()
            return
        active_panel.setFocus()


def search_overlay_controller_for(shell: Any) -> SearchOverlayController:
    """Return the composed search overlay controller for a shell."""

    controller = getattr(shell, "search_overlay_controller", None)
    if isinstance(controller, SearchOverlayController):
        return controller
    controller = SearchOverlayController(shell)
    setattr(shell, "search_overlay_controller", controller)
    return controller


__all__ = [
    "SearchOverlayController",
    "search_overlay_controller_for",
]
