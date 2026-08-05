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

"""Translate pointer dragging into incremental Contextual Toolbar movement."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPaintEvent, QPainter
from PySide6.QtWidgets import QWidget
from qfluentwidgets import themeColor  # type: ignore[import-untyped]

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
)

from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)

_PILL_WIDTH = 8
_PILL_HEIGHT = CANVAS_CHROME_CONTROL_HEIGHT


class ContextualToolbarDragHandle(QWidget):
    """Expose one permanent drag affordance without stealing page interaction."""

    dragged = Signal(QPoint)

    def __init__(self, parent: QWidget) -> None:
        """Create the canonical move handle and its localized description."""
        super().__init__(parent)
        self.setObjectName("ContextualToolbarDragHandle")
        self.setFixedSize(_PILL_WIDTH, _PILL_HEIGHT)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        set_localized_tooltip(self, "Move Contextual Toolbar")
        set_localized_accessible_name(self, "Move Contextual Toolbar")
        self._last_global_position: QPoint | None = None

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint one vertical pill using the live application accent color."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(themeColor())
        pill = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        radius = pill.width() / 2.0
        painter.drawRoundedRect(pill, radius, radius)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Capture the initial global pointer position for a left-button drag."""
        if event.button() is Qt.MouseButton.LeftButton:
            self._last_global_position = event.globalPosition().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Publish incremental movement while the left button remains held."""
        previous = self._last_global_position
        if previous is not None and event.buttons() & Qt.MouseButton.LeftButton:
            current = event.globalPosition().toPoint()
            self._last_global_position = current
            self.dragged.emit(current - previous)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Release pointer ownership at the end of a left-button drag."""
        if event.button() is Qt.MouseButton.LeftButton:
            self._last_global_position = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


__all__ = ["ContextualToolbarDragHandle"]
