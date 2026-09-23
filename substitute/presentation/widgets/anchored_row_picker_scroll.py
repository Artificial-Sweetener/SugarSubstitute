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

"""Own bounded QFluent scrolling for anchored picker rows."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import SingleDirectionScrollArea  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)


class AnchoredRowPickerScrollSurface(SingleDirectionScrollArea):  # type: ignore[misc]
    """Render one vertically bounded picker row document with QFluent chrome."""

    def __init__(
        self,
        *,
        row_width: int,
        row_height: int,
        row_count: int,
        row_spacing: int,
        maximum_height: int | None,
        parent: QWidget,
    ) -> None:
        """Create a transparent row viewport sized to whole visible rows."""

        super().__init__(parent, orient=Qt.Orientation.Vertical)
        self._row_height = max(1, row_height)
        self._row_spacing = max(0, row_spacing)
        self._row_count = max(0, row_count)
        self._natural_height = self._height_for_rows(self._row_count)
        self._visible_row_count = self._resolve_visible_row_count(maximum_height)
        self._requires_scroll = self._visible_row_count < self._row_count

        configure_qfluent_scroll_surface(self)
        self.setObjectName("anchoredRowPickerScroll")
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.enableTransparentBackground()
        self.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {"
            "border: none;"
            "background: transparent;"
            "}"
        )

        self.content = QWidget(self)
        self.content.setObjectName("anchoredRowPickerContent")
        self.content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.layout_rows = QVBoxLayout(self.content)
        self.layout_rows.setContentsMargins(0, 0, 0, 0)
        self.layout_rows.setSpacing(self._row_spacing)
        self.content.setFixedSize(row_width, self._natural_height)
        self.setWidget(self.content)

        viewport_height = self._height_for_rows(self._visible_row_count)
        self.setFixedSize(row_width, viewport_height)
        scroll_bar = self.verticalScrollBar()
        scroll_bar.setRange(0, max(0, self._natural_height - viewport_height))
        scroll_bar.setPageStep(viewport_height)
        scroll_bar.setSingleStep(self._row_height + self._row_spacing)

    def add_row(self, row: QWidget) -> None:
        """Append one row widget to the scroll document."""

        self.layout_rows.addWidget(row)

    def reveal(self, row: QWidget) -> None:
        """Scroll just enough to keep one highlighted row fully visible."""

        self.ensureWidgetVisible(row, 0, 0)

    def reveal_at_slot(self, row_index: int, visible_slot: int) -> None:
        """Place one row at a preferred visible slot for initial presentation."""

        if not self._requires_scroll:
            return
        stride = self._row_height + self._row_spacing
        scroll_row = max(0, row_index - max(0, visible_slot))
        self.verticalScrollBar().setValue(scroll_row * stride)

    def visible_row_count(self) -> int:
        """Return the number of complete rows exposed by the viewport."""

        return self._visible_row_count

    def requires_scroll(self) -> bool:
        """Return whether the row document exceeds the viewport."""

        return self._requires_scroll

    def _resolve_visible_row_count(self, maximum_height: int | None) -> int:
        """Return the complete row count that fits the requested height."""

        if self._row_count <= 0:
            return 0
        if maximum_height is None or self._natural_height <= maximum_height:
            return self._row_count
        stride = self._row_height + self._row_spacing
        return max(
            1,
            min(
                self._row_count,
                (max(1, maximum_height) + self._row_spacing) // stride,
            ),
        )

    def _height_for_rows(self, row_count: int) -> int:
        """Return document height for a number of complete picker rows."""

        if row_count <= 0:
            return 0
        return row_count * self._row_height + (row_count - 1) * self._row_spacing


__all__ = ["AnchoredRowPickerScrollSurface"]
