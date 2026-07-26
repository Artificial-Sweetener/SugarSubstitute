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

"""Resolve visible source bounds and bounded viewport damage geometry."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from .state import PromptProjectionGeometryInput
from .visible_lines import visible_projection_lines


@dataclass(frozen=True, slots=True)
class PromptViewportGeometry:
    """Resolve viewport queries from one immutable layout input."""

    input: PromptProjectionGeometryInput

    def visible_source_bounds(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[int, int] | None:
        """Return the source interval intersecting one viewport."""

        visible_lines = visible_projection_lines(
            self.input.layout_snapshot.lines,
            document_top=viewport_rect.top() + scroll_offset,
            document_bottom=viewport_rect.bottom() + scroll_offset,
        )
        if not visible_lines:
            return None
        return (visible_lines[0].source_start, visible_lines[-1].source_end)

    def visual_line_range_viewport_rect(
        self,
        *,
        first_line_index: int,
        line_count: int,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> QRectF | None:
        """Return the clipped viewport rect for a contiguous visual-line range."""

        if line_count <= 0 or viewport_rect.isEmpty():
            return None
        lines = self.input.layout_snapshot.lines
        start_index = max(0, first_line_index)
        end_index = min(len(lines), start_index + line_count)
        if start_index >= end_index:
            return None
        repaint_rect: QRectF | None = None
        for line in lines[start_index:end_index]:
            line_rect = QRectF(
                viewport_rect.left(),
                line.top - scroll_offset,
                viewport_rect.width(),
                line.height,
            )
            repaint_rect = (
                line_rect if repaint_rect is None else repaint_rect.united(line_rect)
            )
        if repaint_rect is None:
            return None
        clipped_rect = repaint_rect.intersected(viewport_rect)
        if not clipped_rect.isValid() or clipped_rect.isEmpty():
            return None
        return clipped_rect


__all__ = ["PromptViewportGeometry"]
