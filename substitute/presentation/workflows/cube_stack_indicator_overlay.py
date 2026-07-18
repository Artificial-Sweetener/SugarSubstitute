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

"""Paint the active-cube indicator above the cube stack viewport."""
# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QPainter,
)
from PySide6.QtWidgets import QWidget
from qfluentwidgets.common.color import themeColor  # type: ignore[import-untyped]

from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableCloseButtonDisplayMode,
)

CubeCloseButtonDisplayMode = ReorderableCloseButtonDisplayMode

if TYPE_CHECKING:
    from substitute.presentation.workflows.cube_stack_view import CubeStack


class CubeStackIndicatorOverlay(QWidget):
    """Paint the selected-cube indicator above cube item widgets."""

    def __init__(self, stack: CubeStack) -> None:
        """Create a transparent overlay tied to one cube stack viewport."""

        super().__init__(stack.view)
        self._stack = stack
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

    def sync(self) -> None:
        """Match viewport geometry and z-order before repainting."""

        current_item = self._stack.currentTab()
        self.setGeometry(self._stack.view.rect())
        self.raise_()
        self.setVisible(current_item is not None and current_item.isVisible())
        self.update()

    def paintEvent(self, event: object) -> None:
        """Draw the active selection indicator in viewport coordinates."""

        _ = event
        item = self._stack.currentTab()
        if item is None or not item.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(themeColor())
        indicator_x = item.x() + 1
        painter.drawRoundedRect(
            indicator_x,
            self._stack._getIndicatorY(),
            3,
            16,
            1.5,
            1.5,
        )


__all__ = ["CubeStackIndicatorOverlay"]
