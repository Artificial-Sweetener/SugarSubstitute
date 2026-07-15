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

"""Regression tests for incremental projection caret-map consistency."""

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.prompt_projection_invariants import (
    validate_prompt_projection_document,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture
def widgets() -> Iterator[list[QWidget]]:
    """Track live Qt widgets for cleanup after each test."""

    live_widgets: list[QWidget] = []
    yield live_widgets
    for widget in reversed(live_widgets):
        widget.close()
        widget.deleteLater()
    process_events(ensure_qapp())


def test_delete_after_middle_selection_delete_advances_to_next_source_boundary(
    widgets: list[QWidget],
) -> None:
    """Second Delete after deleting selected middle text removes the next character."""

    box = _editor_after_selected_middle_delete(widgets)

    QTest.keyClick(box, Qt.Key.Key_Delete)
    process_events(ensure_qapp())

    assert box.toPlainText() == "1,"
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 1


def test_right_arrow_after_middle_selection_delete_advances_one_source_boundary(
    widgets: list[QWidget],
) -> None:
    """Right Arrow after deleting selected middle text moves to the next boundary."""

    box = _editor_after_selected_middle_delete(widgets)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(ensure_qapp())

    assert box.toPlainText() == "1l,"
    assert box.textCursor().selectionStart() == 2
    assert box.textCursor().selectionEnd() == 2


def test_incremental_selection_delete_keeps_plain_text_caret_map_consistent(
    widgets: list[QWidget],
) -> None:
    """Selection Delete commits caret stops that match the edited plain text run."""

    box = _editor_after_selected_middle_delete(widgets)
    document = surface_for(box).projection_document()

    validate_prompt_projection_document(document)
    assert box.toPlainText() == "1l,"
    assert tuple(document.runs[0].source_positions) == (0, 1, 2, 3)
    assert tuple(stop.state.source_position for stop in document.caret_map.stops) == (
        0,
        1,
        2,
        3,
    )


def _editor_after_selected_middle_delete(widgets: list[QWidget]) -> PromptEditor:
    """Return an editor after typing `1girl,` and deleting source range `[1, 4]`."""

    box = show_prompt_editor(widgets, text="", width=260)
    QTest.keyClicks(box, "1girl,")
    process_events(ensure_qapp())
    _select_source_range(box, 1, 4)
    QTest.keyClick(box, Qt.Key.Key_Delete)
    process_events(ensure_qapp())
    assert box.toPlainText() == "1l,"
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 1
    return box


def _select_source_range(box: PromptEditor, start: int, end: int) -> None:
    """Select a source range through the public Qt cursor API."""

    cursor = box.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(ensure_qapp())
