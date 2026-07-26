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

"""Draw shaped input-method preedit content without editor-state queries."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter

from .input_method_render_state import PromptInputMethodRenderLayer


class PromptInputMethodRenderer:
    """Draw only the shaped input-method layer published before paint."""

    def draw(
        self,
        painter: QPainter,
        layer: PromptInputMethodRenderLayer,
    ) -> None:
        """Draw preedit glyphs and its prepared cursor line."""

        layout = layer.layout
        if layout is None:
            return
        painter.save()
        try:
            layout.draw(painter, QPointF(*layer.origin))
            if layer.cursor_line is not None:
                painter.setPen(QColor.fromRgba(layer.cursor_rgba))
                start_x, start_y, end_x, end_y = layer.cursor_line
                painter.drawLine(
                    QPointF(start_x, start_y),
                    QPointF(end_x, end_y),
                )
        finally:
            painter.restore()


__all__ = ["PromptInputMethodRenderer"]
