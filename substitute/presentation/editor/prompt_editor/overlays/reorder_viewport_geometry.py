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

"""Own bounded reorder overlay viewport geometry identity."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect

from ..geometry.widget_mapping import reorder_overlay_content_rect
from ..projection.reorder_state import (
    PromptReorderOverlayPositionGeometryKey,
    reorder_overlay_position_geometry_key,
)
from .reorder_overlay_ports import PromptReorderEditor


@dataclass(frozen=True, slots=True)
class PromptReorderViewportGeometrySnapshot:
    """Publish one coherent viewport read for broad frame refresh."""

    viewport_rect: QRect
    content_rect: QRect
    position_key: PromptReorderOverlayPositionGeometryKey


class PromptReorderViewportGeometryOwner:
    """Build the sole bounded identity for reorder viewport positioning."""

    def __init__(self, editor: PromptReorderEditor) -> None:
        """Store the stable editor geometry adapter."""

        self._editor = editor
        self._publication: PromptReorderViewportGeometrySnapshot | None = None

    @property
    def published_content_rect(self) -> QRect:
        """Return the content bounds from the last complete viewport capture."""

        publication = self._publication
        return QRect() if publication is None else QRect(publication.content_rect)

    def position_geometry_key(self) -> PromptReorderOverlayPositionGeometryKey:
        """Return the current viewport, content, and scroll identity."""

        viewport_rect = self._editor.viewport().rect()
        content_rect = reorder_overlay_content_rect(self._editor)
        scrollbar = self._editor.verticalScrollBar()
        return reorder_overlay_position_geometry_key(
            viewport_left=viewport_rect.left(),
            viewport_top=viewport_rect.top(),
            viewport_width=viewport_rect.width(),
            viewport_height=viewport_rect.height(),
            content_left=content_rect.left(),
            content_top=content_rect.top(),
            content_width=content_rect.width(),
            content_height=content_rect.height(),
            scroll_offset=scrollbar.value(),
        )

    def viewport_rect(self) -> QRect:
        """Return the viewport rectangle used to align the overlay."""

        return self._editor.viewport().rect()

    def capture(self) -> PromptReorderViewportGeometrySnapshot:
        """Read and publish viewport, content, scroll, and position identity."""

        viewport_rect = self._editor.viewport().rect()
        content_rect = reorder_overlay_content_rect(self._editor)
        scrollbar = self._editor.verticalScrollBar()
        self._publication = PromptReorderViewportGeometrySnapshot(
            viewport_rect=viewport_rect,
            content_rect=content_rect,
            position_key=reorder_overlay_position_geometry_key(
                viewport_left=viewport_rect.left(),
                viewport_top=viewport_rect.top(),
                viewport_width=viewport_rect.width(),
                viewport_height=viewport_rect.height(),
                content_left=content_rect.left(),
                content_top=content_rect.top(),
                content_width=content_rect.width(),
                content_height=content_rect.height(),
                scroll_offset=scrollbar.value(),
            ),
        )
        return self._publication
