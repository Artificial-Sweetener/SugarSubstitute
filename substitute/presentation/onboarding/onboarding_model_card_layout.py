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

"""Own centered, width-dependent packing of onboarding model cards."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget

from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
)


class ModelCardLayout(QLayout):
    """Wrap fixed portrait cards while centering each incomplete row."""

    def __init__(self, parent: QWidget) -> None:
        """Keep card identity independent of row count and viewport changes."""
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(10)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        """Retain insertion order across every layout width."""
        self._items.append(item)
        self.invalidate()

    def count(self) -> int:
        """Expose the number of mounted choices to Qt."""
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        """Return a mounted choice without transferring ownership."""
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        """Transfer an item to the caller for explicit widget disposal."""
        if not 0 <= index < len(self._items):
            return None
        item = self._items.pop(index)
        self.invalidate()
        return item

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        """Tell containing stages that narrower card rows require more height."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        """Derive total height from the same row partition used for placement."""
        columns = self._columns(width)
        rows = (len(self._items) + columns - 1) // columns
        return rows * CARD_HEIGHT + max(0, rows - 1) * self.spacing()

    def minimumSize(self) -> QSize:  # noqa: N802
        """Permit wrapping down to one intact portrait card."""
        return QSize(CARD_WIDTH, CARD_HEIGHT) if self._items else QSize(0, 0)

    def minimumHeightForWidth(self, width: int) -> int:  # noqa: N802
        """Keep every fixed-height row reachable in a scrolling container."""
        return self.heightForWidth(width)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Prefer the established five-column composition where space permits."""
        columns = min(5, len(self._items))
        width = columns * CARD_WIDTH + max(0, columns - 1) * self.spacing()
        return QSize(width, self.heightForWidth(width))

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        """Place each row without resizing or recreating model choices."""
        super().setGeometry(rect)
        columns = self._columns(rect.width())
        for start in range(0, len(self._items), columns):
            row = self._items[start : start + columns]
            width = len(row) * CARD_WIDTH + (len(row) - 1) * self.spacing()
            left = rect.x() + max(0, (rect.width() - width) // 2)
            top = rect.y() + (start // columns) * (CARD_HEIGHT + self.spacing())
            for column, item in enumerate(row):
                item.setGeometry(
                    QRect(
                        left + column * (CARD_WIDTH + self.spacing()),
                        top,
                        CARD_WIDTH,
                        CARD_HEIGHT,
                    )
                )

    def _columns(self, width: int) -> int:
        """Keep five-column density while bounding rows to available width."""
        return min(5, max(1, (width + self.spacing()) // (CARD_WIDTH + self.spacing())))
