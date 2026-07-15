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

"""Provide shared QFluent popup chrome for attached presentation surfaces."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.flyout import (  # type: ignore[import-untyped]
    FlyoutViewBase,
)


class AttachedFluentPopupFrame(FlyoutViewBase):  # type: ignore[misc]
    """Paint QFluent flyout chrome without adopting top-level popup behavior."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a child-widget frame with a stable content layout."""

        super().__init__(parent=parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(1, 1, 1, 1)
        outer_layout.setSpacing(0)
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(10, 10, 10, 10)
        self._content_layout.setSpacing(8)
        outer_layout.addLayout(self._content_layout)

    def content_layout(self) -> QVBoxLayout:
        """Return the layout that consumers use for surface-specific content."""

        return self._content_layout

    def addWidget(
        self,
        widget: QWidget,
        stretch: int = 0,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> None:
        """Append one widget to the content layout using FlyoutViewBase's API."""

        self._content_layout.addWidget(widget, stretch, align)


def fluent_menu_hover_fill() -> QColor:
    """Return the QFluent menu hover fill color for custom-painted rows."""

    return QColor(255, 255, 255, 20) if isDarkTheme() else QColor(0, 0, 0, 23)


def fluent_menu_selected_fill() -> QColor:
    """Return the QFluent menu selected fill color for custom-painted rows."""

    return QColor(255, 255, 255, 20) if isDarkTheme() else QColor(0, 0, 0, 18)


__all__ = [
    "AttachedFluentPopupFrame",
    "fluent_menu_hover_fill",
    "fluent_menu_selected_fill",
]
