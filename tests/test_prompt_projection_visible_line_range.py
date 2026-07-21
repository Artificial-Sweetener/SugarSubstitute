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

"""Cover bounded visual-line lookup by viewport and source range."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionLineSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.visible_line_range import (
    PromptProjectionSourceLineIndex,
    visible_projection_lines,
)


def test_visible_projection_lines_bounds_vertical_lookup() -> None:
    """Viewport lookup should return only vertically intersecting lines."""

    lines = tuple(
        _line(index * 10, (index + 1) * 10, top=index * 20.0) for index in range(5)
    )

    visible = visible_projection_lines(
        lines,
        document_top=21.0,
        document_bottom=59.0,
    )

    assert visible == lines[1:3]


def test_source_line_index_returns_only_intersecting_visual_lines() -> None:
    """Source lookup should skip unrelated lines and preserve wrapped boundaries."""

    lines = (
        _line(0, 10, top=0.0),
        _line(10, 20, top=20.0),
        _line(20, 20, top=40.0),
        _line(20, 30, top=60.0),
        _line(30, 40, top=80.0),
    )
    index = PromptProjectionSourceLineIndex(lines)

    assert index.lines_intersecting(12, 18) == (lines[1],)
    assert index.lines_intersecting(18, 22) == (lines[1], lines[2], lines[3])
    assert index.lines_intersecting(20, 20) == (lines[1], lines[2], lines[3])
    assert index.lines_intersecting(100, 110) == ()


def _line(
    source_start: int,
    source_end: int,
    *,
    top: float,
) -> PromptProjectionLineSnapshot:
    """Return one fragment-free visual line for range lookup tests."""

    return PromptProjectionLineSnapshot(
        top=top,
        height=16.0,
        source_start=source_start,
        source_end=source_end,
        source_content_start=source_start,
        source_content_end=source_end,
        line_break_start=None,
        line_break_end=None,
        fragments=(),
        caret_stops=(),
    )
