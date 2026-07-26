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

"""Build half-height separator rows with caret geometry hosted outside them."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from ..projection.metrics import PromptProjectionMetrics
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from .models import PromptProjectionLineSnapshot


@dataclass(frozen=True, slots=True)
class PromptRegionStructuralRowLayout:
    """Return one structural line plus the caret rect hosted on its following line."""

    line: PromptProjectionLineSnapshot
    trailing_caret_rect: QRectF
    following_line_source_start: int


class PromptRegionStructuralRowLayoutBuilder:
    """Own the vertical geometry contract for projected regional separators."""

    def build(
        self,
        run: PromptProjectionRun,
        *,
        top: float,
        content_left: float,
        leading_caret_rect: QRectF,
        metrics: PromptProjectionMetrics,
    ) -> PromptRegionStructuralRowLayout:
        """Build a half row whose edge carets live on adjacent text lines."""

        row_height = metrics.initial_row_height() * 0.5
        trailing_caret_rect = metrics.caret_rect(
            x_left=content_left,
            row_top=top + row_height,
            row_height=metrics.initial_row_height(),
        )
        token_end = run.source_positions[1]
        line = PromptProjectionLineSnapshot(
            top=top,
            height=row_height,
            source_start=run.source_start,
            source_end=run.source_end,
            source_content_start=run.source_start,
            source_content_end=token_end,
            line_break_start=token_end if token_end < run.source_end else None,
            line_break_end=run.source_end if token_end < run.source_end else None,
            fragments=(),
            caret_stops=(),
        )
        return PromptRegionStructuralRowLayout(
            line=line,
            trailing_caret_rect=trailing_caret_rect,
            following_line_source_start=run.source_positions[-1],
        )


__all__ = [
    "PromptRegionStructuralRowLayout",
    "PromptRegionStructuralRowLayoutBuilder",
]
