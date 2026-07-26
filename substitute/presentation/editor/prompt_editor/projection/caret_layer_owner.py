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

"""Publish the exact custom-caret command before prompt painting."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPalette

from .caret_render_state import (
    EMPTY_CARET_RENDER_LAYER,
    PromptCaretRenderLayer,
)


class PromptCaretRenderLayerOwner:
    """Own publication of the exact custom caret consumed by a paint pass."""

    def __init__(self) -> None:
        """Create an initially hidden caret layer."""

        self._layer = EMPTY_CARET_RENDER_LAYER

    @property
    def layer(self) -> PromptCaretRenderLayer:
        """Return the currently published immutable caret layer."""

        return self._layer

    def prepare(
        self,
        *,
        visible: bool,
        rect: QRectF,
        palette: QPalette,
    ) -> bool:
        """Publish one visible caret or the shared empty layer."""

        if not visible:
            if self._layer is EMPTY_CARET_RENDER_LAYER:
                return False
            self._layer = EMPTY_CARET_RENDER_LAYER
            return True
        rect_key = (rect.x(), rect.y(), rect.width(), rect.height())
        palette_key = int(palette.cacheKey())
        if self._layer.rect == rect_key and self._layer.palette_key == palette_key:
            return False
        self._layer = PromptCaretRenderLayer(
            rect=rect_key,
            palette_key=palette_key,
            palette=QPalette(palette),
        )
        return True


__all__ = ["PromptCaretRenderLayerOwner"]
