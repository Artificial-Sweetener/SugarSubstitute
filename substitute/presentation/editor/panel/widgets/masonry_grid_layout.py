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

"""Provide masonry-style Qt layout with optional per-widget column spans."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget

EDITOR_SECTION_GAP = 8


class MasonryGridLayout(QLayout):
    """
    Responsive column layout where widgets can specify a 'column_span' property.
    Honors column span when placing widgets, falling back to span=1 if not enough room.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        column_width: int = 400,
        spacing: int = 8,
    ) -> None:
        """Initialize the masonry layout with its base column width and spacing."""

        super().__init__(parent)
        self.column_width = column_width
        self.setSpacing(spacing)
        self.items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:
        """Append one layout item to the masonry grid."""

        self.items.append(item)

    def count(self) -> int:
        """Return the number of tracked layout items."""

        return len(self.items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        """Return one layout item when the requested index is valid."""

        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem:
        """Remove and return one layout item by index."""

        if 0 <= index < len(self.items):
            return self.items.pop(index)
        raise IndexError(f"Invalid layout index: {index}")

    def sizeHint(self) -> QSize:
        """Return the current preferred size for the masonry layout."""

        return self._compute_size_hint()

    def minimumSize(self) -> QSize:
        """Return the current minimum size for the masonry layout."""

        return self._compute_size_hint()

    def _compute_size_hint(self) -> QSize:
        """Estimate the layout size from the current parent width and item spans."""

        spacing = self.spacing()
        min_col_w = self.column_width
        parent = self.parentWidget()
        avail_width = parent.width() if parent else (min_col_w * 2 + spacing)
        n_cols = max(1, (avail_width + spacing) // (min_col_w + spacing))
        total_spacing = (n_cols - 1) * spacing
        # Dynamic column width: fill available space evenly
        col_w = (avail_width - total_spacing) // n_cols if n_cols > 0 else min_col_w
        col_heights = [0] * n_cols

        for item in self.items:
            widget = item.widget()
            if not widget or not widget.isVisible():
                continue
            span = widget.property("column_span") or 1
            span = int(span)
            span = min(span, n_cols)
            # Find shortest columns where span fits
            best_col = -1
            min_height = 2**31 - 1
            for i in range(n_cols - span + 1):
                max_h = max(col_heights[j] for j in range(i, i + span))
                if max_h < min_height:
                    min_height = max_h
                    best_col = i
            if best_col == -1:
                best_col = col_heights.index(min(col_heights))
                span = 1
            h_hint = widget.sizeHint().height()
            for j in range(best_col, best_col + span):
                col_heights[j] = min_height + h_hint + spacing

        total_height = max(col_heights) if col_heights else 0
        width = n_cols * col_w + spacing * (n_cols - 1)
        return QSize(width, total_height)

    def _do_layout(self, rect: QRect) -> None:
        """Position visible widgets into the shortest available column spans."""

        spacing = self.spacing()
        avail_width = rect.width()
        min_col_w = self.column_width
        n_cols = max(1, (avail_width + spacing) // (min_col_w + spacing))
        total_spacing = (n_cols - 1) * spacing
        # Dynamic column width: fill available space evenly
        col_w = (avail_width - total_spacing) // n_cols if n_cols > 0 else min_col_w
        col_heights = [rect.y()] * n_cols

        for item in self.items:
            widget = item.widget()
            if not widget or not widget.isVisible():
                continue

            # Get widget's desired column span
            span = widget.property("column_span") or 1
            span = int(span)
            span = min(span, n_cols)  # Don't allow more than available columns

            # Find first position where span columns are all free/shortest
            best_col = -1
            min_height = 2**31 - 1
            for i in range(n_cols - span + 1):
                # Max height among columns in the span
                max_h = max(col_heights[j] for j in range(i, i + span))
                if max_h < min_height:
                    min_height = max_h
                    best_col = i

            # Fallback: if no span fits, just use shortest single column
            if best_col == -1:
                best_col = col_heights.index(min(col_heights))
                span = 1

            x = rect.x() + best_col * (col_w + spacing)
            y = max(col_heights[j] for j in range(best_col, best_col + span))
            w_hint = col_w * span + spacing * (span - 1)
            h_hint = widget.sizeHint().height()

            item.setGeometry(QRect(x, y, w_hint, h_hint))
            # Update column heights for all spanned columns
            for j in range(best_col, best_col + span):
                col_heights[j] = y + h_hint + spacing

    def hasHeightForWidth(self) -> bool:
        """Report that the masonry layout does not derive height from width callbacks."""

        return False

    def setGeometry(self, rect: QRect) -> None:
        """Apply layout geometry and recompute child placement for the new bounds."""

        super().setGeometry(rect)
        self._do_layout(rect)
        parent = self.parentWidget()
        if parent:
            parent.updateGeometry()
