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

"""Own projection selection-layer refresh across surface transitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)

from .content_selection_layer import (
    EMPTY_PROJECTION_SELECTION_LAYER,
    PromptProjectionSelectionLayer,
)
from .prepared_frame import PromptProjectionPreparedFrame


@dataclass(frozen=True, slots=True)
class PromptProjectionSelectionLayerKey:
    """Identify one exact selection, layout, viewport, and paint style."""

    geometry_identity: int
    anchor_position: int
    cursor_position: int
    viewport: tuple[int, int, int, int]
    scroll_offset: int
    style_identity: int


class PromptProjectionSelectionLayerOwner:
    """Refresh and publish the active viewport's prepared selection layer."""

    def __init__(
        self,
        *,
        frame: Callable[[], PromptProjectionPreparedFrame],
        selection: Callable[[], PromptProjectionSelection],
        viewport_rect: Callable[[], QRectF],
        scroll_offset: Callable[[], float],
        preview_active: Callable[[], bool],
    ) -> None:
        """Bind narrow state queries used only at explicit refresh boundaries."""

        self._frame = frame
        self._selection = selection
        self._viewport_rect = viewport_rect
        self._scroll_offset = scroll_offset
        self._preview_active = preview_active
        self._layer = EMPTY_PROJECTION_SELECTION_LAYER
        self._key: PromptProjectionSelectionLayerKey | None = None

    @property
    def layer(self) -> PromptProjectionSelectionLayer:
        """Return the currently published immutable selection layer."""

        return self._layer

    def refresh(self) -> None:
        """Publish selection commands for the current live frame and viewport."""

        if self._preview_active():
            self._layer = EMPTY_PROJECTION_SELECTION_LAYER
            self._key = None
            return
        frame = self._frame()
        selection = self._selection()
        viewport_rect = self._viewport_rect()
        scroll_offset = self._scroll_offset()
        key = PromptProjectionSelectionLayerKey(
            geometry_identity=id(frame.output.snapshot),
            anchor_position=selection.anchor_position,
            cursor_position=selection.cursor_position,
            viewport=_rect_key(viewport_rect),
            scroll_offset=_coordinate(scroll_offset),
            style_identity=id(frame.paint_input.base_text_styles),
        )
        if key == self._key:
            return
        self._layer = frame.prepare_selection_layer(
            selection,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        self._key = key


def _rect_key(rect: QRectF) -> tuple[int, int, int, int]:
    """Quantize one viewport rectangle for stable selection-layer identity."""

    return (
        _coordinate(rect.x()),
        _coordinate(rect.y()),
        _coordinate(rect.width()),
        _coordinate(rect.height()),
    )


def _coordinate(value: float) -> int:
    """Quantize one viewport coordinate without losing subpixel identity."""

    return int(round(value * 100.0))


__all__ = [
    "PromptProjectionSelectionLayerKey",
    "PromptProjectionSelectionLayerOwner",
]
