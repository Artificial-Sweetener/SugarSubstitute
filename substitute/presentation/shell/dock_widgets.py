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

"""Provide shell dock widget subclasses."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDockWidget, QWidget


class ClosableDockWidget(QDockWidget):
    """Hide dock content when closed while still notifying shell listeners."""

    closed = Signal()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Emit the close signal and collapse the dock instead of destroying it."""

        self.closed.emit()
        event.ignore()
        self.hide()


def handle_dock_closed(
    shell: object,
    dock_widget: QDockWidget,
    content_widget: QWidget,
) -> None:
    """Re-dock floating widgets instead of allowing them to close permanently."""

    _ = content_widget
    if dock_widget.isFloating():
        dock_widget.setFloating(False)
        add_dock_widget = getattr(shell, "addDockWidget")
        add_dock_widget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)

    dock_widget.show()


__all__ = ["ClosableDockWidget", "handle_dock_closed"]
