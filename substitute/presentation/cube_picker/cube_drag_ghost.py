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

"""Floating held-cube widget used by the staging drawer drag interaction."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QWidget,
)

from substitute.application.cubes import CubeStackDraftEntry
from substitute.presentation.cubes.cube_card_visual import (
    CubeCardVisual,
    CubeCardVisualState,
)
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
    CUBE_ITEM_ICON_INSET_EXPANDED,
    CUBE_ITEM_ICON_SIZE_EXPANDED,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh


class CubeDragGhost(QFrame):
    """Render the cube card that follows the cursor during staging drags."""

    def __init__(
        self,
        *,
        entry: CubeStackDraftEntry,
        icon: QIcon,
        parent: QWidget,
    ) -> None:
        """Create the floating card."""

        super().__init__(parent)
        self._entry = entry
        self._icon = icon
        self._selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(CUBE_ITEM_EXPANDED_WIDTH, CUBE_ITEM_HEIGHT)
        self.setObjectName("cubeDragGhost")
        self._offset = QPoint(
            CUBE_ITEM_ICON_INSET_EXPANDED + (CUBE_ITEM_ICON_SIZE_EXPANDED // 2),
            CUBE_ITEM_HEIGHT // 2,
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 170))
        self.setGraphicsEffect(shadow)
        connect_theme_refresh(self, self._apply_theme_styles)

    def move_to_global(self, global_pos: QPoint) -> None:
        """Move the ghost so it appears held under the cursor."""

        parent = self.parentWidget()
        if parent is None:
            return
        local_pos = parent.mapFromGlobal(global_pos - self._offset)
        self.move(local_pos)
        self.raise_()

    def paintEvent(self, event: object) -> None:
        """Paint the drag ghost with the shared selected cube-card visual."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        CubeCardVisual.draw(
            painter,
            rect=self.rect(),
            font=self.font(),
            state=CubeCardVisualState(
                primary_text=self._entry.display_name,
                secondary_text=self._entry.secondary_text,
                icon=self._icon,
                selected=True,
                hovered=False,
                pressed=False,
                enabled=self.isEnabled(),
                close_visible=False,
                compact_progress=0.0,
                selected_fill_color=self._selected_fill_color,
            ),
        )

    def _apply_theme_styles(self) -> None:
        """Refresh selected fill so drag ghosts match live cube-stack cards."""

        self._selected_fill_color = CubeCardVisual.selected_fill_color_for_widget(self)
        self.update()


__all__ = ["CubeDragGhost"]
