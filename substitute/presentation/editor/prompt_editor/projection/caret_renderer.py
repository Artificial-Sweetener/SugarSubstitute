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

"""Draw a prepared custom caret without focus or blink-state discovery."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter

from substitute.presentation.widgets.text_caret import paint_text_caret

from .caret_render_state import PromptCaretRenderLayer


class PromptCaretRenderer:
    """Draw only the prepared custom caret command."""

    def draw(self, painter: QPainter, layer: PromptCaretRenderLayer) -> None:
        """Draw one caret without querying focus, selection, or blink state."""

        if layer.rect is None or layer.palette is None:
            return
        paint_text_caret(
            painter,
            QRectF(*layer.rect),
            layer.palette,
        )


__all__ = ["PromptCaretRenderer"]
