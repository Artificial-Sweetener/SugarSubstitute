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

"""Measure and paint prompt autocomplete suggestion rows."""

from __future__ import annotations

from typing import Final, cast

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QResizeEvent,
)
from PySide6.QtWidgets import QWidget
from qfluentwidgets.common.font import getFont  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from substitute.presentation.widgets.fluent_popup_frame import (
    fluent_menu_hover_fill,
    fluent_menu_selected_fill,
)

from .autocomplete_contracts import PromptAutocompleteRowRenderState

AUTOCOMPLETE_ROW_HEIGHT: Final[int] = 33
_SOURCE_LABEL_MAX_WIDTH: Final[int] = 160
_ROW_HORIZONTAL_MARGIN: Final[int] = 16
_ROW_COLUMN_GAP: Final[int] = 8


def format_prompt_autocomplete_popularity(popularity: int | None) -> str:
    """Return human-readable popularity text for one autocomplete suggestion."""

    if popularity is None or popularity <= 0:
        return ""
    return f"{popularity:,}"


class PromptAutocompleteRow(QWidget):
    """Render one prompt autocomplete suggestion row."""

    clicked = Signal(int)

    def __init__(
        self,
        row_state: PromptAutocompleteRowRenderState,
        parent: QWidget | None = None,
    ) -> None:
        """Build the row-owned text metrics and interactive paint state."""

        super().__init__(parent)
        self._index = row_state.index
        self._full_tag_text = row_state.title
        self._full_secondary_text = row_state.source_label or row_state.detail or ""
        self._rendered_tag_text = ""
        self._rendered_secondary_text = ""
        self._tag_font = cast(QFont, getFont(14))
        self._secondary_font = cast(QFont, getFont(12))
        self._is_hovered = False
        self._is_selected = False

        self.setFixedHeight(AUTOCOMPLETE_ROW_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setProperty("selected", False)

        self.set_selected(row_state.is_selected)
        self._update_rendered_text()

    def rendered_tag_text(self) -> str:
        """Return the row-owned tag text after width-aware elision."""

        return self._rendered_tag_text

    def rendered_secondary_text(self) -> str:
        """Return the row-owned secondary text after width-aware elision."""

        return self._rendered_secondary_text

    def natural_tag_width(self) -> int:
        """Return the unelided width required by the full tag text."""

        return int(QFontMetrics(self._tag_font).horizontalAdvance(self._full_tag_text))

    def natural_popularity_width(self) -> int:
        """Return the width required by the formatted popularity text."""

        if not self._full_secondary_text:
            return 0
        source_width = int(
            self._secondary_metrics().horizontalAdvance(self._full_secondary_text)
        )
        return min(source_width, _SOURCE_LABEL_MAX_WIDTH)

    def sizeHint(self) -> QSize:
        """Return the preferred row size before panel width constraints apply."""

        width = (
            self.natural_tag_width()
            + self.natural_popularity_width()
            + (2 * _ROW_HORIZONTAL_MARGIN)
            + _ROW_COLUMN_GAP
        )
        return QSize(width, AUTOCOMPLETE_ROW_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Return the minimum row size equal to the preferred size."""

        return self.sizeHint()

    def set_render_state(
        self,
        row_state: PromptAutocompleteRowRenderState,
    ) -> None:
        """Replace row content while preserving the existing widget instance."""

        self._index = row_state.index
        self._full_tag_text = row_state.title
        self._full_secondary_text = row_state.source_label or row_state.detail or ""
        self.set_selected(row_state.is_selected)
        self._update_rendered_text()
        self.updateGeometry()
        self.update()

    def set_selected(self, is_selected: bool) -> None:
        """Apply selected-row paint state."""

        if self._is_selected == is_selected:
            return
        self._is_selected = is_selected
        self.setProperty("selected", is_selected)
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Elide long tag text when the panel narrows the row."""

        super().resizeEvent(event)
        self._update_rendered_text()

    def enterEvent(self, event: QEnterEvent) -> None:
        """Track hover state for lightweight row affordances."""

        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover state when the pointer leaves the row."""

        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit row activation without taking focus."""

        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw selected or hovered row backgrounds and row-owned text."""

        _ = event
        painter = QPainter(self)
        try:
            painter.setRenderHints(
                QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
            )
            self._paint_row_background(painter)
            self._paint_row_text(painter)
        finally:
            painter.end()

    def _paint_row_background(self, painter: QPainter) -> None:
        """Paint the selected or hovered row fill."""

        if not (self._is_selected or self._is_hovered):
            return
        fill_rect = self.rect().adjusted(6, 4, -6, 0)
        fill = (
            fluent_menu_selected_fill()
            if self._is_selected
            else fluent_menu_hover_fill()
        )
        painter.setBrush(fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(fill_rect, 5, 5)

    def _paint_row_text(self, painter: QPainter) -> None:
        """Paint the tag and secondary columns within the row."""

        tag_rect, secondary_rect = self._text_rects()
        painter.setPen(self._text_color())
        if self._rendered_tag_text:
            painter.setFont(self._tag_font)
            painter.drawText(
                tag_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._rendered_tag_text,
            )
        if self._rendered_secondary_text and secondary_rect.width() > 0:
            painter.setFont(self._secondary_font)
            painter.drawText(
                secondary_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self._rendered_secondary_text,
            )

    def _update_rendered_text(self) -> None:
        """Apply width-aware elision to row-owned text."""

        secondary_width = 0
        if self._full_secondary_text:
            secondary_width = min(
                self.natural_popularity_width(),
                _SOURCE_LABEL_MAX_WIDTH,
            )

        available_tag_width = self._available_tag_width(secondary_width)
        self._rendered_tag_text = self._tag_metrics().elidedText(
            self._full_tag_text,
            Qt.TextElideMode.ElideRight,
            available_tag_width,
        )
        self._rendered_secondary_text = self._secondary_metrics().elidedText(
            self._full_secondary_text,
            Qt.TextElideMode.ElideRight,
            _SOURCE_LABEL_MAX_WIDTH,
        )

    def _available_tag_width(self, secondary_width: int) -> int:
        """Return the current width available to the tag column."""

        reserved_secondary_width = 0
        if secondary_width > 0:
            reserved_secondary_width = secondary_width + _ROW_COLUMN_GAP
        return max(
            0,
            self.width() - (2 * _ROW_HORIZONTAL_MARGIN) - reserved_secondary_width,
        )

    def _text_rects(self) -> tuple[QRect, QRect]:
        """Return row-local text rectangles for tag and secondary columns."""

        secondary_width = self.natural_popularity_width()
        content_rect = self.rect().adjusted(
            _ROW_HORIZONTAL_MARGIN,
            0,
            -_ROW_HORIZONTAL_MARGIN,
            0,
        )
        if secondary_width <= 0:
            return content_rect, QRect(content_rect.right(), 0, 0, self.height())
        secondary_rect = QRect(
            content_rect.right() - secondary_width + 1,
            content_rect.top(),
            secondary_width,
            content_rect.height(),
        )
        tag_rect = QRect(
            content_rect.left(),
            content_rect.top(),
            max(0, content_rect.width() - secondary_width - _ROW_COLUMN_GAP),
            content_rect.height(),
        )
        return tag_rect, secondary_rect

    def _tag_metrics(self) -> QFontMetrics:
        """Return metrics for tag text rendering."""

        return QFontMetrics(self._tag_font)

    def _secondary_metrics(self) -> QFontMetrics:
        """Return metrics for secondary text rendering."""

        return QFontMetrics(self._secondary_font)

    @staticmethod
    def _text_color() -> QColor:
        """Return the qfluent label text color for the active theme."""

        return QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)


__all__ = [
    "AUTOCOMPLETE_ROW_HEIGHT",
    "PromptAutocompleteRow",
    "format_prompt_autocomplete_popularity",
]
