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

"""Draw prepared source-line chrome without geometry or theme discovery."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .source_line_render_state import PromptSourceLineChromeLayer


class PromptSourceLineChromeRenderer:
    """Draw immutable source-line fill commands in publication order."""

    def draw(
        self,
        painter: QPainter,
        layer: PromptSourceLineChromeLayer,
    ) -> None:
        """Draw prepared fills without querying their owner."""

        if not layer.fills:
            return
        painter.save()
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            for fill in layer.fills:
                painter.fillRect(
                    QRectF(fill.left, fill.top, fill.width, fill.height),
                    QColor.fromRgba(fill.color_rgba),
                )
        finally:
            painter.restore()


__all__ = ["PromptSourceLineChromeRenderer"]
