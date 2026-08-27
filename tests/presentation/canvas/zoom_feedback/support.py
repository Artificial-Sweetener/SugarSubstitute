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

"""Provide drawing and pointer-event support for zoom-feedback tests."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget


def image(size: QSize) -> QImage:
    """Return an opaque image for mounted rendering."""

    result = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(QColor("cornflowerblue"))
    return result


def wheel_event(target: QWidget, position: QPointF) -> QWheelEvent:
    """Return one local wheel event with a valid global position."""

    return QWheelEvent(
        position,
        QPointF(target.mapToGlobal(position.toPoint())),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def double_click_event(target: QWidget, position: QPointF) -> QMouseEvent:
    """Return one positioned primary-button double-click event."""

    global_position = QPointF(target.mapToGlobal(position.toPoint()))
    return QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        position,
        global_position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def mouse_move_event(target: QWidget, position: QPointF) -> QMouseEvent:
    """Return one buttonless local mouse movement."""

    return QMouseEvent(
        QEvent.Type.MouseMove,
        position,
        QPointF(target.mapToGlobal(position.toPoint())),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


class RecordingPainter:
    """Record visible badge geometry and material assignments."""

    def __init__(self) -> None:
        """Initialize deterministic painter observations."""

        self.texts: list[str] = []
        self.rounded_bounds: list[QRectF] = []
        self.brushes: list[QColor] = []
        self.pens: list[QPen] = []
        self.text_colors: list[QColor] = []
        self._opacity = 1.0

    def save(self) -> None:
        """Accept painter-state saves."""

    def restore(self) -> None:
        """Accept painter-state restores."""

    def opacity(self) -> float:
        """Return the recorded opacity."""

        return self._opacity

    def setOpacity(self, opacity: float) -> None:  # noqa: N802
        """Record painter opacity."""

        self._opacity = opacity

    def setRenderHint(self, *_args: object) -> None:  # noqa: N802
        """Accept render-hint updates."""

    def setFont(self, *_args: object) -> None:  # noqa: N802
        """Accept font updates."""

    def setBrush(self, brush: QColor) -> None:  # noqa: N802
        """Record one fill color."""

        self.brushes.append(QColor(brush))

    def setPen(self, pen: object) -> None:  # noqa: N802
        """Record border pens and text colors."""

        if isinstance(pen, QPen):
            self.pens.append(QPen(pen))
        elif isinstance(pen, QColor):
            self.text_colors.append(QColor(pen))

    def drawRoundedRect(self, bounds: QRectF, *_args: object) -> None:  # noqa: N802
        """Record one badge rectangle."""

        self.rounded_bounds.append(QRectF(bounds))

    def drawText(self, _bounds: object, _alignment: object, text: str) -> None:  # noqa: N802
        """Record one badge label."""

        self.texts.append(text)


__all__ = [
    "RecordingPainter",
    "double_click_event",
    "image",
    "mouse_move_event",
    "wheel_event",
]
