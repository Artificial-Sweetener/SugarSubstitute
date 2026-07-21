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

"""Verify lazy reused-line composition preserves semantic rebind requests."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.projection.reused_line_sequence import (
    PromptProjectionReusedLineSequence,
)
from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
)


def _line(source_start: int) -> PromptProjectionLineSnapshot:
    """Return one minimal immutable line for sequence ownership tests."""

    return PromptProjectionLineSnapshot(
        top=float(source_start),
        height=16.0,
        source_start=source_start,
        source_end=source_start + 1,
        source_content_start=source_start,
        source_content_end=source_start + 1,
        line_break_start=None,
        line_break_end=None,
        fragments=(),
        caret_stops=(
            PromptProjectionLineCaretStopSnapshot(
                projection_position=source_start,
                rect=QRectF(0.0, float(source_start), 1.0, 16.0),
            ),
        ),
    )


def test_zero_delta_suffix_still_uses_semantic_rebind_callback() -> None:
    """Stable geometry must not bypass semantic ownership changes in reused lines."""

    prefix = _line(0)
    suffix = _line(1)
    shifted_lines: list[PromptProjectionLineSnapshot] = []

    def rebind(
        line: PromptProjectionLineSnapshot,
        source_delta: int,
        projection_delta: int,
        y_delta: float,
    ) -> PromptProjectionLineSnapshot:
        """Record suffix rebinding even when every coordinate delta is zero."""

        assert (source_delta, projection_delta, y_delta) == (0, 0, 0.0)
        rebound = _line(line.source_start + 10)
        shifted_lines.append(rebound)
        return rebound

    lines = PromptProjectionReusedLineSequence(
        (prefix,),
        (suffix,),
        shift_line=rebind,
        source_delta=0,
        projection_delta=0,
        y_delta=0.0,
    )

    assert lines[0] is prefix
    assert lines[1].source_start == 11
    assert shifted_lines == [lines[1]]
