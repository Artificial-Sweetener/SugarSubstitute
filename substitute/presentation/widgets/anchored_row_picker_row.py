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

"""Render selectable rows for anchored canvas picker flyouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import QPushButton, QWidget
from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
)

AnchoredRowPickerTextMode = Literal[
    "anchor_center",
    "anchor_left",
    "row_center",
    "row_left",
]

ANCHORED_ROW_PICKER_HORIZONTAL_TEXT_PADDING = 12


@dataclass(frozen=True, slots=True)
class AnchoredRowPickerItem:
    """Describe one visible row in an anchored row picker."""

    key: str
    label: str
    enabled: bool = True


class AnchoredRowPickerRow(QPushButton):
    """Render one selectable anchored picker row with explicit text geometry."""

    selected = Signal(str)

    def __init__(
        self,
        item: AnchoredRowPickerItem,
        *,
        active: bool,
        row_size: QSize,
        anchor_slot_width: int,
        active_text_mode: AnchoredRowPickerTextMode,
        inactive_text_mode: AnchoredRowPickerTextMode,
        horizontal_text_padding: int = ANCHORED_ROW_PICKER_HORIZONTAL_TEXT_PADDING,
        parent: QWidget | None = None,
    ) -> None:
        """Create a fixed-size picker row with explicit text painting."""

        super().__init__(item.label, parent)
        self.item = item
        self._active = active
        self._anchor_slot_width = anchor_slot_width
        self._active_text_mode = active_text_mode
        self._inactive_text_mode = inactive_text_mode
        self._horizontal_text_padding = horizontal_text_padding
        self.setProperty("active", active)
        self.setFixedSize(row_size)
        self.setEnabled(item.enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        setFont(self, 14)
        self.clicked.connect(lambda: self._emit_if_enabled())
        self._apply_theme_styles()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit selection directly so popup row clicks do not depend on focus."""

        if (
            self.item.enabled
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.selected.emit(self.item.key)
            return
        super().mouseReleaseEvent(event)

    def set_active(self, active: bool) -> None:
        """Update active state and repaint."""

        self._active = active
        self.setProperty("active", active)
        self._apply_theme_styles()
        self.update()

    def text_rect_for_paint(self) -> QRect:
        """Return the text rect used by explicit row painting."""

        mode = self._current_text_mode()
        if mode in ("anchor_center", "anchor_left"):
            width = min(self._anchor_slot_width, self.width())
            base_rect = QRect(0, 0, width, self.height())
        else:
            base_rect = self.rect()
        if mode in ("anchor_left", "row_left"):
            return base_rect.adjusted(
                self._horizontal_text_padding,
                0,
                -self._horizontal_text_padding,
                0,
            )
        return base_rect

    def text_alignment_for_paint(self) -> Qt.AlignmentFlag:
        """Return the text alignment used by explicit row painting."""

        mode = self._current_text_mode()
        if mode in ("anchor_center", "row_center"):
            return Qt.AlignmentFlag.AlignCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def paintEvent(self, event: object) -> None:
        """Paint row fill and text from explicit alignment modes."""

        del event
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing,
        )
        fill = self._fill_color()
        if fill is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(self.rect(), 5, 5)
        painter.setFont(self.font())
        painter.setPen(self._text_color())
        painter.drawText(
            self.text_rect_for_paint(),
            self.text_alignment_for_paint(),
            self.item.label,
        )

    def _emit_if_enabled(self) -> None:
        """Emit the row key when the item is enabled."""

        if self.item.enabled:
            self.selected.emit(self.item.key)

    def _current_text_mode(self) -> AnchoredRowPickerTextMode:
        """Return the active or inactive text mode for this row."""

        return self._active_text_mode if self._active else self._inactive_text_mode

    def _apply_theme_styles(self) -> None:
        """Apply qfluent-compatible base row states."""

        self.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                padding: 0px;
            }
            """
        )

    def _fill_color(self) -> QColor | None:
        """Return the current hover or active fill color."""

        if self._active:
            return QColor(255, 255, 255, 31) if isDarkTheme() else QColor(0, 0, 0, 20)
        if self.underMouse():
            return QColor(255, 255, 255, 20) if isDarkTheme() else QColor(0, 0, 0, 15)
        return None

    def _text_color(self) -> QColor:
        """Return the current row text color."""

        if not self.isEnabled():
            return QColor(255, 255, 255, 92) if isDarkTheme() else QColor(0, 0, 0, 92)
        return QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)


__all__ = [
    "ANCHORED_ROW_PICKER_HORIZONTAL_TEXT_PADDING",
    "AnchoredRowPickerItem",
    "AnchoredRowPickerRow",
    "AnchoredRowPickerTextMode",
]
