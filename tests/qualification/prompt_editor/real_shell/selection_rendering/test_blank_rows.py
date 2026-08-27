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

"""Verify selection paint ownership for projected blank rows."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtGui import QTextCursor

from tests.support.prompt_editor.real_shell.models import PromptEditorVisibleLayoutRow
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_select_all_highlights_blank_rows_between_projected_paragraphs(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Paint blank rows created by consecutive hard line breaks on select-all."""

    prompt = (
        "alpha,\n\n(small:1.20) breasts, flat chest,\n\n(pale skin:1.20), pointy ears"
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
    real_shell_scenario.shell.resize(760, 520)
    real_shell_scenario.input.focus_editor(field)
    cursor = cast(Any, field.editor).textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len(prompt), QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    selected = real_shell_scenario.snapshots.capture(
        field,
        label="select-all-projected-paragraph-breaks",
    )

    expected_blank_ranges = _blank_line_break_ranges(prompt)
    blank_rows = {
        (row.source_start, row.source_end): row
        for row in selected.visible_layout_rows
        if (row.source_start, row.source_end) in expected_blank_ranges
    }

    assert selected.selection_range == (0, len(prompt))
    assert set(blank_rows) == set(expected_blank_ranges)
    for row in blank_rows.values():
        assert row.text == "\n"
        assert _row_has_selection_rect(row, selected.selection_rects)


def _blank_line_break_ranges(prompt: str) -> tuple[tuple[int, int], ...]:
    """Return newline ranges owning visual blank rows in consecutive breaks."""

    return tuple(
        (index + 1, index + 2)
        for index in range(len(prompt) - 1)
        if prompt[index] == "\n" and prompt[index + 1] == "\n"
    )


def _row_has_selection_rect(
    row: PromptEditorVisibleLayoutRow,
    selection_rects: tuple[tuple[float, float, float, float], ...],
) -> bool:
    """Return whether a document-local selection rect intersects one row."""

    row_top = row.document_top
    row_bottom = row.document_top + row.height
    for _left, rect_top, _width, rect_height in selection_rects:
        rect_center_y = rect_top + rect_height / 2.0
        if row_top <= rect_center_y <= row_bottom:
            return True
    return False
