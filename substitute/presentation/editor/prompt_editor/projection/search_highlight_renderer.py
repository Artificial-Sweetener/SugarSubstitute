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

"""Draw prepared search-highlight commands without geometry discovery."""

from __future__ import annotations

from bisect import bisect_left

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .search_highlight_layer import PromptSearchHighlightLayer


class PromptSearchHighlightRenderer:
    """Draw immutable search highlights in match order."""

    def draw(
        self,
        painter: QPainter,
        layer: PromptSearchHighlightLayer,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> None:
        """Draw only prepared commands intersecting the current viewport."""

        if not layer.rects:
            return
        document_top = viewport_rect.top() + scroll_offset
        document_bottom = viewport_rect.bottom() + scroll_offset
        first_index = bisect_left(
            layer.tops,
            document_top - layer.maximum_height,
        )
        painter.save()
        try:
            painter.translate(0.0, -scroll_offset)
            painter.setClipRect(viewport_rect.translated(0.0, scroll_offset))
            painter.setPen(Qt.PenStyle.NoPen)
            for command in layer.rects[first_index:]:
                if command.top > document_bottom:
                    break
                if command.top + command.height < document_top:
                    continue
                painter.setBrush(QColor.fromRgba(command.color_rgba))
                painter.drawRect(
                    QRectF(
                        command.left,
                        command.top,
                        command.width,
                        command.height,
                    )
                )
        finally:
            painter.restore()


__all__ = ["PromptSearchHighlightRenderer"]
