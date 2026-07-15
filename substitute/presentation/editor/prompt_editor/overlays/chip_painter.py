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

"""Paint overlay-owned chip chrome from prepared visual geometry."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from .chip_visuals import PROMPT_CHIP_BUBBLE_RADIUS, PromptChipVisual


@dataclass(frozen=True, slots=True)
class PromptChipPaintStyle:
    """Describe the reusable chrome style for one painted chip state."""

    fill_color: QColor
    border_color: QColor
    outline_only: bool = False
    outline_width: float = 1.0
    opacity: float = 1.0


class PromptChipPainter:
    """Paint shared overlay chip chrome."""

    def paint_chrome(
        self,
        *,
        painter: QPainter,
        visual: PromptChipVisual,
        style: PromptChipPaintStyle,
    ) -> None:
        """Paint one chip bubble using the supplied shared visual and style."""

        painter.save()
        painter.setOpacity(style.opacity)
        painter.setBrush(
            Qt.BrushStyle.NoBrush if style.outline_only else QColor(style.fill_color)
        )
        painter.setPen(QPen(style.border_color, style.outline_width))
        painter.drawPath(self._chrome_path(visual))
        painter.restore()

    def _chrome_path(self, visual: PromptChipVisual) -> QPainterPath:
        """Return one stroke path for all bubble rects in a logical chip."""

        path = QPainterPath()
        for bubble_rect in visual.bubble_rects:
            bubble_path = QPainterPath()
            bubble_path.addRoundedRect(
                bubble_rect,
                PROMPT_CHIP_BUBBLE_RADIUS,
                PROMPT_CHIP_BUBBLE_RADIUS,
            )
            path = path.united(bubble_path)
        return path.simplified()


__all__ = ["PromptChipPainter", "PromptChipPaintStyle"]
