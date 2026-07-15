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

"""Paint source-line and search chrome from prepared projection geometry."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from qfluentwidgets import isDarkTheme, themeColor  # type: ignore[import-untyped]

from .layout_engine import PromptProjectionLayout
from .selection_geometry import PromptProjectionSourceLineRect


class PromptSourceLineChrome:
    """Own source-line background and search-highlight projection chrome."""

    def __init__(self) -> None:
        """Initialize disabled source-line chrome with no reserved inset."""

        self._enabled = False
        self._content_left_inset = 0.0

    @property
    def enabled(self) -> bool:
        """Return whether source-line backgrounds should be painted."""

        return self._enabled

    @property
    def content_left_inset(self) -> float:
        """Return viewport-local space reserved for source-line chrome."""

        return self._content_left_inset

    def set_enabled(self, enabled: bool) -> bool:
        """Store source-line chrome visibility and report whether it changed."""

        if self._enabled == enabled:
            return False
        self._enabled = enabled
        return True

    def set_content_left_inset(self, inset: float) -> bool:
        """Store reserved source-line inset and report whether it changed."""

        inset = max(0.0, inset)
        if abs(self._content_left_inset - inset) < 0.01:
            return False
        self._content_left_inset = inset
        return True

    def source_line_rects(
        self,
        *,
        layout: PromptProjectionLayout,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible source logical line rects aligned to projection."""

        return layout.source_line_rects(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def current_source_line_index(
        self,
        *,
        layout: PromptProjectionLayout,
        cursor_position: int,
    ) -> int:
        """Return the newline-delimited source line containing the cursor."""

        return layout.source_line_index_for_position(cursor_position)

    def paint_source_lines(
        self,
        painter: QPainter,
        *,
        source_lines: tuple[PromptProjectionSourceLineRect, ...],
        current_line_index: int,
        focus_active: bool,
    ) -> None:
        """Paint zebra and current-line backgrounds beneath projection content."""

        if not self._enabled:
            return
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for source_line in source_lines:
            if source_line.line_index % 2 == 1:
                painter.fillRect(source_line.rect, _source_line_zebra_color())
            if source_line.line_index == current_line_index and focus_active:
                painter.fillRect(source_line.rect, _source_line_current_color())
        painter.restore()

    def paint_search_matches(
        self,
        painter: QPainter,
        *,
        layout: PromptProjectionLayout,
        match_ranges: tuple[tuple[int, int], ...],
        active_match_index: int | None,
        viewport_rect: QRectF,
        scroll_offset: float,
        palette: QPalette,
    ) -> None:
        """Paint transient search highlight ranges beneath text and selection."""

        if not match_ranges:
            return
        painter.save()
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            for match_index, (start, length) in enumerate(match_ranges):
                highlight_color = self.search_match_color(
                    palette,
                    active=match_index == active_match_index,
                )
                painter.setBrush(highlight_color)
                for rect in layout.source_range_fragments(
                    start=start,
                    end=start + length,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                ):
                    painter.drawRect(rect)
        finally:
            painter.restore()

    def search_match_color(self, palette: QPalette, *, active: bool) -> QColor:
        """Return the fill color used for passive and active search matches."""

        highlight_color = QColor(palette.color(QPalette.ColorRole.Highlight))
        if active:
            highlight_color.setAlpha(150)
            return highlight_color
        highlight_color.setAlpha(90)
        return highlight_color


def _source_line_zebra_color() -> QColor:
    """Return the subtle alternating source-line fill color."""

    return QColor(255, 255, 255, 16) if isDarkTheme() else QColor(0, 0, 0, 12)


def _source_line_current_color() -> QColor:
    """Return the current source-line highlight color."""

    color = QColor(themeColor())
    color.setAlpha(38 if isDarkTheme() else 34)
    return color
