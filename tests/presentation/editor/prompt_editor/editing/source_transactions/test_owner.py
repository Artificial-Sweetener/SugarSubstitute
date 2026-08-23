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

"""Verify unified prompt source-transaction ownership through real Qt input."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pytest

from PySide6.QtCore import Qt
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    observe_prompt_editor_work,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


@dataclass(slots=True)
class _WorkRecorder:
    """Count stable owner events without inspecting private implementation calls."""

    counts: Counter[PromptEditorWorkEvent] = field(default_factory=Counter)

    def record(self, event: PromptEditorWorkEvent, elapsed_ms: float) -> None:
        """Record one owner operation."""

        _ = elapsed_ms
        self.counts[event] += 1


def _editor_with_source(
    widgets: list[QWidget],
    source_text: str,
) -> tuple[Any, Any]:
    """Build one production surface and install exact source through its owner."""

    editor = show_prompt_editor(
        widgets,
        text=source_text,
        width=520,
    )
    surface = surface_for(editor)
    surface.set_cursor_positions(
        cursor_position=len(source_text),
        anchor_position=len(source_text),
    )
    return editor, surface


def _assert_one_source_transaction(recorder: _WorkRecorder) -> None:
    """Require one source mutation and one projection application."""

    assert recorder.counts[PromptEditorWorkEvent.EDITING_REPLACE_RANGE] == 1
    assert recorder.counts[PromptEditorWorkEvent.SURFACE_SOURCE_APPLY] == 1


def test_typed_insert_and_grapheme_delete_each_commit_once(
    widgets: list[QWidget],
) -> None:
    """Keep ordinary insertion and grapheme deletion single-transaction edits."""

    editor, surface = _editor_with_source(widgets, "A👩‍🚀")
    insert_recorder = _WorkRecorder()
    with observe_prompt_editor_work(insert_recorder):
        QTest.keyClick(editor, Qt.Key.Key_X)

    assert surface.toPlainText() == "A👩‍🚀x"
    _assert_one_source_transaction(insert_recorder)

    surface.set_cursor_positions(cursor_position=4, anchor_position=4)
    delete_recorder = _WorkRecorder()
    with observe_prompt_editor_work(delete_recorder):
        QTest.keyClick(editor, Qt.Key.Key_Backspace)

    assert surface.toPlainText() == "Ax"
    assert surface.cursor_position == 1
    _assert_one_source_transaction(delete_recorder)


def test_ime_selection_commit_is_one_source_transaction(
    widgets: list[QWidget],
) -> None:
    """Keep one UTF-16-aware IME commit atomic across a selected source range."""

    _editor, surface = _editor_with_source(widgets, "replace 👩‍💻 me")
    surface.set_cursor_positions(
        cursor_position=len(surface.toPlainText()),
        anchor_position=0,
    )
    QApplication.sendEvent(surface, QInputMethodEvent("にほん", []))
    event = QInputMethodEvent()
    event.setCommitString("中文 日本語 한국어 👩‍💻")
    recorder = _WorkRecorder()

    with observe_prompt_editor_work(recorder):
        QApplication.sendEvent(surface, event)

    assert surface.toPlainText() == "中文 日本語 한국어 👩‍💻"
    _assert_one_source_transaction(recorder)


def test_cut_and_literal_paste_each_commit_source_once(
    widgets: list[QWidget],
) -> None:
    """Keep clipboard planning from duplicating source transactions."""

    editor, surface = _editor_with_source(widgets, "alpha beta")
    surface.set_cursor_positions(cursor_position=5, anchor_position=0)
    cut_recorder = _WorkRecorder()
    with observe_prompt_editor_work(cut_recorder):
        QTest.keyClick(
            editor,
            Qt.Key.Key_X,
            Qt.KeyboardModifier.ControlModifier,
        )

    assert QApplication.clipboard().text() == "alpha"
    assert surface.toPlainText() == " beta"
    _assert_one_source_transaction(cut_recorder)

    QApplication.clipboard().setText("gamma")
    surface.set_cursor_positions(cursor_position=0, anchor_position=0)
    paste_recorder = _WorkRecorder()
    with observe_prompt_editor_work(paste_recorder):
        QTest.keyClick(
            editor,
            Qt.Key.Key_V,
            Qt.KeyboardModifier.ControlModifier,
        )

    assert surface.toPlainText() == "gamma beta"
    assert paste_recorder.counts[PromptEditorWorkEvent.EDITING_PASTE] == 1
    _assert_one_source_transaction(paste_recorder)


def test_history_round_trip_restores_source_and_selection(
    widgets: list[QWidget],
) -> None:
    """Preserve source and cursor restoration through keyboard undo and redo."""

    editor, surface = _editor_with_source(widgets, "alpha")
    surface.set_cursor_positions(cursor_position=5, anchor_position=0)
    QTest.keyClick(editor, Qt.Key.Key_X)

    assert surface.toPlainText() == "x"
    assert surface.cursor_position == 1
    assert surface.anchor_position == 1

    QTest.keyClick(
        editor,
        Qt.Key.Key_Z,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert surface.toPlainText() == "alpha"
    assert surface.cursor_position == 5
    assert surface.anchor_position == 0

    QTest.keyClick(
        editor,
        Qt.Key.Key_Y,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert surface.toPlainText() == "x"
    assert surface.cursor_position == 1
    assert surface.anchor_position == 1
