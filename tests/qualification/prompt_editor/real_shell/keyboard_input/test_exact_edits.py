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

"""Verify exact keyboard edits through the production prompt-editor route."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest

from substitute.application.prompt_editor.document.service import PromptDocumentService
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_emphasis_shortcut_crosses_zero_and_undoes(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Apply signed emphasis stepping and undo through the production shell route."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="(cat:0.00), dog"
    )
    real_shell_scenario.input.set_source_cursor_position(field, 2)

    route = real_shell_scenario.input.press_key(
        field,
        Qt.Key.Key_Down,
        modifiers=Qt.KeyboardModifier.ControlModifier,
    )

    assert route.source_after == "(cat:-0.05), dog"
    stepped = real_shell_scenario.snapshots.capture(
        field,
        label="negative-emphasis-step",
    )
    assert not snapshot_invariant_violations(stepped)

    real_shell_scenario.input.undo(field)

    assert field.editor.toPlainText() == "(cat:0.00), dog"


def test_real_shell_repeated_emphasis_keeps_one_shell(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Repeated Ctrl+Up must adjust one emphasis instead of nesting wrappers."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="1girl")
    cursor = field.editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    field.editor.setTextCursor(cursor)

    for _step in range(3):
        real_shell_scenario.input.press_key(
            field,
            Qt.Key.Key_Up,
            modifiers=Qt.KeyboardModifier.ControlModifier,
        )

    source = field.editor.toPlainText()
    assert source == "(1girl:1.15)"
    assert len(PromptDocumentService().build_document_view(source).emphasis_spans) == 1
    snapshot = real_shell_scenario.snapshots.capture(
        field,
        label="repeated-emphasis-single-shell",
    )
    assert not snapshot_invariant_violations(snapshot)


def test_real_shell_typed_selection_replacement_preserves_exact_keys(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Replace selected text without rewriting unrelated source context."""

    source_text = "open (, alpha, {lighting/day}, omega"
    selection_start = source_text.index(",", source_text.index("{"))
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source_text)
    cursor = field.editor.textCursor()
    cursor.setPosition(selection_start)
    cursor.setPosition(selection_start + 2, QTextCursor.MoveMode.KeepAnchor)
    field.editor.setTextCursor(cursor)
    target = real_shell_scenario.input.focus_editor(field)

    QTest.keyClicks(target, ") ")

    assert field.editor.toPlainText() == "open (, alpha, {lighting/day}) omega"
    assert field.editor.textCursor().position() == selection_start + 2
