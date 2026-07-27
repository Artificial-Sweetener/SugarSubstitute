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

"""Draw prepared transient edit commands in deterministic content order."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .transient_edit_render_state import PromptTransientEditRenderLayer


class PromptTransientEditRenderer:
    """Draw transient insertion and deletion layers without editor queries."""

    def draw_insertion(
        self,
        painter: QPainter,
        layer: PromptTransientEditRenderLayer,
    ) -> None:
        """Draw prepared inserted text without reading editor state."""

        command = layer.insertion
        if command is None:
            return
        rect = QRectF(*command.rect)
        painter.save()
        try:
            painter.setFont(command.font)
            if command.erase_underlying_content:
                painter.fillRect(
                    rect.adjusted(-1.0, 0.0, 1.0, 0.0),
                    QColor.fromRgba(command.background_rgba),
                )
            painter.setPen(QColor.fromRgba(command.text_rgba))
            painter.drawText(
                QPointF(rect.left(), command.baseline),
                command.text,
            )
        finally:
            painter.restore()

    def draw_deletion(
        self,
        painter: QPainter,
        layer: PromptTransientEditRenderLayer,
    ) -> None:
        """Draw prepared erase bands without validating transient state."""

        command = layer.deletion
        if command is None:
            return
        painter.save()
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            color = QColor.fromRgba(command.background_rgba)
            for rect in command.rects:
                painter.fillRect(QRectF(*rect), color)
        finally:
            painter.restore()


__all__ = ["PromptTransientEditRenderer"]
