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

"""Provide a Fluent-hosted curve editor for native Comfy CURVE values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy

from PySide6.QtCore import QPointF, QRectF, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)

from sugarsubstitute_shared.localization import app_text
from substitute.presentation.dialogs import LocalizedMessageBoxBase
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPushButton,
    LocalizedSubtitleLabel,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh

_DEFAULT_CURVE: dict[str, object] = {
    "points": [[0.0, 0.0], [1.0, 1.0]],
    "interpolation": "monotone_cubic",
}


def _normalized_curve(value: object) -> dict[str, object]:
    """Return a valid, ordered Comfy curve mapping."""

    source = value if isinstance(value, Mapping) else {}
    raw_points = source.get("points")
    points: list[list[float]] = []
    if isinstance(raw_points, Sequence) and not isinstance(raw_points, str | bytes):
        for raw_point in raw_points:
            if (
                not isinstance(raw_point, Sequence)
                or isinstance(raw_point, str | bytes)
                or len(raw_point) < 2
            ):
                continue
            raw_x, raw_y = raw_point[0], raw_point[1]
            if (
                not isinstance(raw_x, int | float)
                or isinstance(raw_x, bool)
                or not isinstance(raw_y, int | float)
                or isinstance(raw_y, bool)
            ):
                continue
            points.append(
                [
                    max(0.0, min(1.0, float(raw_x))),
                    max(0.0, min(1.0, float(raw_y))),
                ]
            )
    if len(points) < 2:
        points = [[0.0, 0.0], [1.0, 1.0]]
    points.sort(key=lambda point: point[0])
    points[0][0] = 0.0
    points[-1][0] = 1.0
    interpolation = source.get("interpolation", "monotone_cubic")
    return {
        "points": points,
        "interpolation": interpolation
        if isinstance(interpolation, str) and interpolation
        else "monotone_cubic",
    }


class CurveCanvas(QWidget):
    """Paint and edit normalized curve points where Fluent has no equivalent."""

    valueChanged = Signal(object)
    _MARGIN = 14.0
    _HIT_RADIUS = 9.0

    def __init__(self, value: object, parent: QWidget) -> None:
        """Initialize a theme-aware interactive curve canvas."""

        super().__init__(parent)
        self._value = _normalized_curve(value)
        self._dragged_index: int | None = None
        self.setMinimumSize(420, 240)
        self.setMouseTracking(True)
        connect_theme_refresh(self, self.update)

    def value(self) -> dict[str, object]:
        """Return a detached curve mapping."""

        return deepcopy(self._value)

    def setValue(self, value: object) -> None:  # noqa: N802
        """Replace the current curve and repaint it."""

        self._value = _normalized_curve(value)
        self.update()

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        """Paint Fluent-aware grid, curve, and control points."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot_rect()
        background = QColor(255, 255, 255, 14) if isDarkTheme() else QColor(0, 0, 0, 8)
        border = QColor(255, 255, 255, 46) if isDarkTheme() else QColor(0, 0, 0, 42)
        grid = QColor(255, 255, 255, 22) if isDarkTheme() else QColor(0, 0, 0, 20)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(background)
        painter.drawRoundedRect(plot, 6.0, 6.0)
        painter.setPen(QPen(grid, 1.0))
        for index in range(1, 4):
            fraction = index / 4.0
            x = plot.left() + plot.width() * fraction
            y = plot.top() + plot.height() * fraction
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        point_positions = [self._point_to_canvas(point) for point in self._points()]
        if point_positions:
            path = QPainterPath(point_positions[0])
            for point in point_positions[1:]:
                path.lineTo(point)
            accent = QColor(themeColor())
            painter.setPen(QPen(accent, 2.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.setBrush(accent)
            painter.setPen(QPen(QColor("#ffffff"), 1.2))
            for point in point_positions:
                painter.drawEllipse(point, 5.0, 5.0)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Select, add, or remove a point from the curve."""

        position = event.position()
        nearest = self._nearest_point_index(position)
        if event.button() == Qt.MouseButton.RightButton:
            if nearest is not None and nearest not in {0, len(self._points()) - 1}:
                self._points().pop(nearest)
                self._publish_change()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if nearest is None:
            normalized = self._canvas_to_point(position)
            self._points().append(normalized)
            self._points().sort(key=lambda point: point[0])
            nearest = self._points().index(normalized)
            self._publish_change()
        self._dragged_index = nearest

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Move the selected point while preserving endpoint x coordinates."""

        if self._dragged_index is None:
            return
        points = self._points()
        index = self._dragged_index
        point = self._canvas_to_point(event.position())
        if index == 0:
            point[0] = 0.0
        elif index == len(points) - 1:
            point[0] = 1.0
        else:
            point[0] = max(points[index - 1][0], min(points[index + 1][0], point[0]))
        points[index] = point
        self._publish_change()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:  # noqa: N802
        """Finish the current point drag."""

        self._dragged_index = None

    def _points(self) -> list[list[float]]:
        """Return the normalized mutable point collection."""

        points = self._value["points"]
        if not isinstance(points, list):
            raise TypeError("Normalized curve points must be a list")
        return points

    def _plot_rect(self) -> QRectF:
        """Return the drawable area inside the canvas margin."""

        return QRectF(self.rect()).adjusted(
            self._MARGIN,
            self._MARGIN,
            -self._MARGIN,
            -self._MARGIN,
        )

    def _point_to_canvas(self, point: Sequence[float]) -> QPointF:
        """Map one normalized curve point into canvas coordinates."""

        plot = self._plot_rect()
        return QPointF(
            plot.left() + point[0] * plot.width(),
            plot.bottom() - point[1] * plot.height(),
        )

    def _canvas_to_point(self, position: QPointF) -> list[float]:
        """Map a canvas position to a clamped normalized curve point."""

        plot = self._plot_rect()
        x = (position.x() - plot.left()) / max(1.0, plot.width())
        y = (plot.bottom() - position.y()) / max(1.0, plot.height())
        return [max(0.0, min(1.0, x)), max(0.0, min(1.0, y))]

    def _nearest_point_index(self, position: QPointF) -> int | None:
        """Return the index of a point inside the interaction radius."""

        best: tuple[float, int] | None = None
        for index, point in enumerate(self._points()):
            distance = (self._point_to_canvas(point) - position).manhattanLength()
            if distance <= self._HIT_RADIUS and (best is None or distance < best[0]):
                best = (distance, index)
        return best[1] if best is not None else None

    def _publish_change(self) -> None:
        """Repaint and emit the complete semantic curve value."""

        self.update()
        self.valueChanged.emit(self.value())


class _CurveDialog(LocalizedMessageBoxBase):
    """Host the custom curve canvas inside QFluent's modal chrome."""

    def __init__(self, value: object, parent: QWidget) -> None:
        """Build the curve editor, instructions, and Fluent reset action."""

        super().__init__(parent)
        title = LocalizedSubtitleLabel(app_text("Curve"), self)
        instructions = LocalizedCaptionLabel(
            app_text("Click to add, drag to move, and right-click to remove a point."),
            self,
        )
        self.canvas = CurveCanvas(value, self)
        reset_button = LocalizedPushButton(app_text("Reset"), self)
        reset_button.clicked.connect(lambda: self.canvas.setValue(_DEFAULT_CURVE))
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(reset_button)
        self.viewLayout.addWidget(title)
        self.viewLayout.addWidget(instructions)
        self.viewLayout.addWidget(self.canvas)
        self.viewLayout.addLayout(action_row)
        self.widget.setMinimumWidth(500)


class CurveField(LocalizedPushButton):
    """Open a full curve canvas without forcing tall masonry rows."""

    valueChanged = Signal(object)

    def __init__(self, value: object, parent: QWidget | None = None) -> None:
        """Initialize the compact field from one Comfy curve mapping."""

        super().__init__(parent)
        self._value = _normalized_curve(value)
        self.clicked.connect(self._open_editor)
        self._refresh_text()

    def value(self) -> dict[str, object]:
        """Return a detached Comfy curve mapping."""

        return deepcopy(self._value)

    def setValue(self, value: object) -> None:  # noqa: N802
        """Apply a curve without emitting an application state change."""

        blocker = QSignalBlocker(self)
        self._value = _normalized_curve(value)
        self._refresh_text()
        del blocker

    def _open_editor(self) -> None:
        """Commit the edited curve only when the Fluent dialog is accepted."""

        dialog = _CurveDialog(self._value, self.window())
        if not dialog.exec():
            return
        self._value = dialog.canvas.value()
        self._refresh_text()
        self.valueChanged.emit(self.value())

    def _refresh_text(self) -> None:
        """Summarize point count on the compact field button."""

        points = self._value.get("points", [])
        point_count = len(points) if isinstance(points, list) else 0
        self.setText(app_text("Edit curve (%1 points)", point_count))


__all__ = ["CurveCanvas", "CurveField"]
