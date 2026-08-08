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

"""Render theme-aware synthetic-canvas anchor choices."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ToolButton, isDarkTheme, themeColor  # type: ignore[import-untyped]

from substitute.domain.workflow import SyntheticCanvasAnchor

_SELECTED_DOT_RADIUS = 6.0
_UNSELECTED_CENTER_DOT_RADIUS = 3.0
_DISABLED_OPACITY = 0.38
_PRESSED_OPACITY = 0.63


class SyntheticCanvasAnchorButton(ToolButton):  # type: ignore[misc]
    """Paint an anchor arrow or a moving accent selection dot over Fluent chrome."""

    def __init__(
        self,
        anchor: SyntheticCanvasAnchor,
        symbol: str,
        parent: QWidget | None = None,
    ) -> None:
        """Store the unchecked positional glyph and enable exclusive selection."""

        super().__init__(parent)
        self._anchor = anchor
        self._symbol = symbol
        self.setCheckable(True)

    @property
    def anchor(self) -> SyntheticCanvasAnchor:
        """Return the semantic anchor represented by this button."""

        return self._anchor

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint live-theme chrome followed by selected or unselected content."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(_DISABLED_OPACITY)
        elif self.isDown():
            painter.setOpacity(_PRESSED_OPACITY)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(themeColor()))
            painter.drawEllipse(
                QPointF(self.rect().center()),
                _SELECTED_DOT_RADIUS,
                _SELECTED_DOT_RADIUS,
            )
            return
        if self._anchor is SyntheticCanvasAnchor.CENTER:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(
                QPointF(self.rect().center()),
                _UNSELECTED_CENTER_DOT_RADIUS,
                _UNSELECTED_CENTER_DOT_RADIUS,
            )
            return
        foreground = QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)
        painter.setPen(foreground)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._symbol)


__all__ = ["SyntheticCanvasAnchorButton"]
