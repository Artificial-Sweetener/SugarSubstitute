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

"""Render shared empty cube-card placeholders for stack surfaces."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget
from qfluentwidgets.common.icon import (  # type: ignore[import-untyped]
    FluentIcon,
    drawIcon,
)
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh


class CubePlaceholderCard(QFrame):
    """Render a reusable cube-card-sized empty placeholder surface."""

    activated = Signal()

    _BORDER_RADIUS = 5.0
    _PLUS_ICON_SIZE = 18.0

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        plus_visible: bool = False,
        interactive: bool = False,
    ) -> None:
        """Create a cube-card placeholder with optional add affordance."""

        super().__init__(parent)
        self._plus_visible = plus_visible
        self._interactive = interactive
        self._compact = False
        self._compact_progress = 0.0
        self._hovered = False
        self._pressed = False
        self._press_pos: QPoint | None = None
        self._border_color = QColor()
        self._hover_fill_color = QColor()
        self._pressed_fill_color = QColor()

        self.setObjectName("cubePlaceholderCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if interactive else Qt.FocusPolicy.NoFocus
        )
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if interactive
            else Qt.CursorShape.ArrowCursor
        )
        if interactive:
            self.setAccessibleName("Add cube")
        self._apply_theme_styles()
        self._apply_compact_progress_width()
        connect_theme_refresh(self, self._apply_theme_styles)

    def setCompact(self, compact: bool) -> None:
        """Apply compact or expanded cube-card width."""

        if self._compact == compact and self._compact_progress == float(compact):
            return
        self._compact = compact
        self.setCompactProgress(1.0 if compact else 0.0)

    def isCompact(self) -> bool:
        """Return whether the placeholder is in compact card mode."""

        return self._compact

    def setCompactProgress(self, progress: float) -> None:
        """Set transition progress and resize to the matching card width."""

        clamped = max(0.0, min(1.0, float(progress)))
        if clamped == self._compact_progress:
            return
        if 0.0 < clamped < 1.0 and abs(clamped - self._compact_progress) < 0.0001:
            return
        self._compact_progress = clamped
        self._apply_compact_progress_width()
        self.update()

    def compact_progress(self) -> float:
        """Return current compact transition progress."""

        return self._compact_progress

    def setPlusVisible(self, visible: bool) -> None:
        """Show or hide the centered add icon."""

        if self._plus_visible == visible:
            return
        self._plus_visible = visible
        self.update()

    def isPlusVisible(self) -> bool:
        """Return whether the centered add icon is visible."""

        return self._plus_visible

    def sizeHint(self) -> QSize:  # noqa: N802
        """Return the current fixed cube-placeholder size hint."""

        return QSize(self._current_width(), CUBE_ITEM_HEIGHT)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Track hover state for the optional interactive affordance."""

        if self._interactive:
            self._hovered = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear transient interaction state after the pointer leaves."""

        if self._interactive:
            self._hovered = False
            self._pressed = False
            self._press_pos = None
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Record a possible activation click for interactive placeholders."""

        if self._interactive and event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._press_pos = event.position().toPoint()
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Emit activation when a left click completes inside the placeholder."""

        if (
            self._interactive
            and event.button() == Qt.MouseButton.LeftButton
            and self._press_pos is not None
        ):
            should_activate = self.rect().contains(event.position().toPoint())
            self._pressed = False
            self._press_pos = None
            self.update()
            if should_activate:
                self.activated.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: object) -> None:
        """Paint the empty rounded card outline and optional plus icon."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        fill_color = self._current_fill_color()
        if fill_color.alpha() > 0:
            painter.setBrush(fill_color)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(self._border_color)
        pen.setWidthF(1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, self._BORDER_RADIUS, self._BORDER_RADIUS)

        if self._plus_visible:
            self._draw_plus_icon(painter)

    def _apply_compact_progress_width(self) -> None:
        """Resize the placeholder to the current compact-transition width."""

        self.setFixedSize(self._current_width(), CUBE_ITEM_HEIGHT)

    def _current_width(self) -> int:
        """Return the width implied by current compact-transition progress."""

        delta = CUBE_ITEM_EXPANDED_WIDTH - CUBE_ITEM_COMPACT_WIDTH
        return round(CUBE_ITEM_EXPANDED_WIDTH - (delta * self._compact_progress))

    def _current_fill_color(self) -> QColor:
        """Return hover or press fill for the current interaction state."""

        if not self._interactive:
            return QColor(0, 0, 0, 0)
        if self._pressed:
            return QColor(self._pressed_fill_color)
        if self._hovered or self.hasFocus():
            return QColor(self._hover_fill_color)
        return QColor(0, 0, 0, 0)

    def _draw_plus_icon(self, painter: QPainter) -> None:
        """Draw the centered plus affordance."""

        icon_size = self._PLUS_ICON_SIZE
        rect = QRectF(
            (self.width() - icon_size) / 2,
            (self.height() - icon_size) / 2,
            icon_size,
            icon_size,
        )
        painter.save()
        painter.setOpacity(0.86 if self._interactive else 0.68)
        drawIcon(FluentIcon.ADD, painter, rect)
        painter.restore()

    def _apply_theme_styles(self) -> None:
        """Refresh theme-dependent placeholder colors."""

        if isDarkTheme():
            self._border_color = QColor(255, 255, 255, 84)
            self._hover_fill_color = QColor(255, 255, 255, 14)
            self._pressed_fill_color = QColor(255, 255, 255, 22)
        else:
            self._border_color = QColor(0, 0, 0, 72)
            self._hover_fill_color = QColor(0, 0, 0, 8)
            self._pressed_fill_color = QColor(0, 0, 0, 14)
        self.update()


__all__ = ["CubePlaceholderCard"]
