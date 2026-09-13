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

"""Render lightweight indeterminate progress without animation object graphs."""

from __future__ import annotations

from PySide6.QtCore import QBasicTimer, QRectF, QTimerEvent, Qt
from PySide6.QtGui import QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget
from qfluentwidgets import themeColor  # type: ignore[import-untyped]

_FRAME_INTERVAL_MS = 80
_FRAME_STEP_DEGREES = 24
_ARC_SPAN_DEGREES = 105


class BusyRing(QWidget):
    """Paint one bounded busy indicator using a single value-type timer."""

    def __init__(self, parent: QWidget | None = None, *, start: bool = True) -> None:
        """Initialize a transparent ring without allocating Qt animations."""

        super().__init__(parent)
        self._timer = QBasicTimer()
        self._angle_degrees = 0
        self._stroke_width = 6
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(80, 80)
        if start:
            self.start()

    def start(self) -> None:
        """Start repainting only while the indicator is active."""

        if not self._timer.isActive():
            self._timer.start(_FRAME_INTERVAL_MS, self)
        self.show()

    def stop(self) -> None:
        """Stop repainting and restore the initial frame."""

        self._timer.stop()
        self._angle_degrees = 0
        self.update()

    def setStrokeWidth(self, width: int) -> None:  # noqa: N802
        """Set the painted ring thickness used by existing progress surfaces."""

        if width <= 0:
            raise ValueError("Busy ring stroke width must be positive.")
        self._stroke_width = width
        self.update()

    def timerEvent(self, event: QTimerEvent) -> None:  # noqa: N802
        """Advance the visible phase for this ring's own basic timer."""

        if event.timerId() != self._timer.timerId():
            super().timerEvent(event)
            return
        self._angle_degrees = (self._angle_degrees + _FRAME_STEP_DEGREES) % 360
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint a theme-colored clockwise arc inside the widget bounds."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(
            themeColor(),
            self._stroke_width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        inset = self._stroke_width / 2
        bounds = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        painter.drawArc(
            bounds,
            -self._angle_degrees * 16,
            -_ARC_SPAN_DEGREES * 16,
        )


__all__ = ["BusyRing"]
