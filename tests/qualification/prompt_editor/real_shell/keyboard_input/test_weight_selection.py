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

"""Qualify native selection behavior while editing a projected numeric weight."""

from __future__ import annotations

from decimal import Decimal
from dataclasses import replace

import pytest
from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import (
    QContextMenuEvent,
    QFontMetricsF,
    QInputMethodEvent,
    QKeySequence,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit
from substitute.presentation.widgets.action_menu import ActionMenu

from tests.presentation.editor.prompt_editor.interactions.weight.mounting import (
    emphasis_token_for,
    lora_token_for,
    start_exact_weight_edit,
)
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.prompt_editor.projection_engine_support import surface_for


@pytest.mark.parametrize(
    ("source", "value_text", "lora"),
    [
        ("(red cube:1.25)", "1.25", False),
        ("((atmospheric:2.80) perspective:1.15)", "2.80", False),
        ("<lora:detail:1.25>", "1.25", True),
    ],
    ids=["emphasis", "nested-emphasis", "lora"],
)
def test_exact_weight_input_starts_at_displayed_weight_origin(
    real_shell_scenario: PromptEditorRealShellScenario,
    source: str,
    value_text: str,
    lora: bool,
) -> None:
    """Align the native edit caret with the first painted weight glyph."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.focus_editor(field)
    surface = surface_for(field.editor)
    token = next(
        token
        for token in surface.projection_document().tokens
        if token.value_text == value_text
    )
    displayed_slot = surface.token_weight_text_rect(token)
    assert displayed_slot is not None
    displayed_text_left = displayed_slot.left() + (4.0 if lora else 0.0)

    start_exact_weight_edit(field.editor, token)
    editor = QApplication.focusWidget()
    assert isinstance(editor, QLineEdit)
    editor.setCursorPosition(0)
    QApplication.processEvents()
    cursor_rect = editor.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
    assert isinstance(cursor_rect, QRect)
    edit_text_left = (
        editor.geometry().left() + cursor_rect.left() + cursor_rect.width() / 2.0
    )
    displayed_text_top = displayed_slot.top() + max(
        0.0,
        (displayed_slot.height() - QFontMetricsF(editor.font()).height()) / 2.0,
    )
    edit_text_top = editor.geometry().top() + cursor_rect.top()

    assert edit_text_left == pytest.approx(displayed_text_left, abs=0.75), (
        displayed_slot,
        editor.geometry(),
        cursor_rect,
        editor.text(),
        editor.font().toString(),
    )
    assert edit_text_top == pytest.approx(displayed_text_top, abs=1.0)

    editor.selectAll()
    QTest.keyClicks(editor, "0.95")
    editor.setCursorPosition(0)
    QApplication.processEvents()
    editing_token = surface.exact_weight_editor.token()
    assert editing_token is not None
    editing_rect = surface.token_weight_edit_rect(editing_token)
    assert editing_rect is not None
    edited_cursor_rect = editor.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
    assert isinstance(edited_cursor_rect, QRect)
    edited_text_left = (
        editor.geometry().left()
        + edited_cursor_rect.left()
        + edited_cursor_rect.width() / 2.0
    )
    assert edited_text_left == pytest.approx(editing_rect.left(), abs=0.75)
    assert field.editor.toPlainText() == source


@pytest.mark.parametrize("lora", [False, True], ids=["emphasis", "lora"])
@pytest.mark.parametrize(
    "operation", ["native-left", "select-all", "replace-selection"]
)
def test_exact_weight_selection_keeps_edits_inside_the_number(
    real_shell_scenario: PromptEditorRealShellScenario,
    lora: bool,
    operation: str,
) -> None:
    """Keep numeric caret and selection actions independent of underlying prompt text."""

    source = (
        "a <lora:detail:1.25> on a white table"
        if lora
        else "a (red cube:1.25) on a white table"
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.focus_editor(field)
    token = lora_token_for(field.editor) if lora else emphasis_token_for(field.editor)
    start_exact_weight_edit(field.editor, token)
    target = QApplication.focusWidget()
    assert target is not None

    if operation == "native-left":
        QTest.keyClick(target, Qt.Key.Key_Left)
        QTest.keyClick(target, Qt.Key.Key_Backspace)
        reference = QLineEdit()
        try:
            reference.setText("1.25")
            reference.selectAll()
            QTest.keyClick(reference, Qt.Key.Key_Left)
            QTest.keyClick(reference, Qt.Key.Key_Backspace)
            expected_weight = str(Decimal(reference.text()).quantize(Decimal("0.00")))
        finally:
            reference.deleteLater()
    elif operation == "select-all":
        QTest.keyClick(target, Qt.Key.Key_Left)
        QTest.keyClick(target, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        assert not field.editor.textCursor().hasSelection()
        QTest.keyClick(target, Qt.Key.Key_9)
        expected_weight = "9.00"
    else:
        QTest.keyClick(target, Qt.Key.Key_End)
        QTest.keyClick(target, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
        snapshot = real_shell_scenario.snapshots.capture(
            field, label="weight-partial-selection"
        )
        assert snapshot.exact_weight_input is not None
        assert snapshot.exact_weight_input.selected_text == "5"
        assert not snapshot_invariant_violations(snapshot)
        invalid = replace(
            snapshot,
            exact_weight_input=replace(snapshot.exact_weight_input, selection_start=99),
        )
        assert "exact_weight_selection_out_of_bounds" in snapshot_invariant_violations(
            invalid
        )
        QTest.keyClick(target, Qt.Key.Key_9)
        expected_weight = "1.29"

    assert field.editor.toPlainText() == source
    QTest.keyClick(target, Qt.Key.Key_Return)
    assert field.editor.toPlainText() == source.replace("1.25", expected_weight)


@pytest.mark.parametrize("lora", [False, True], ids=["emphasis", "lora"])
@pytest.mark.parametrize("completion", ["commit", "cancel", "focus-out", "invalid"])
def test_exact_weight_native_undo_and_completion(
    real_shell_scenario: PromptEditorRealShellScenario,
    lora: bool,
    completion: str,
) -> None:
    """Keep native input history transient until the semantic commit boundary."""

    source = "<lora:detail:1.25>" if lora else "(red cube:1.25)"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.focus_editor(field)
    token = lora_token_for(field.editor) if lora else emphasis_token_for(field.editor)
    start_exact_weight_edit(field.editor, token)
    target = QApplication.focusWidget()
    assert isinstance(target, QLineEdit)
    event = QInputMethodEvent()
    event.setCommitString("2.75")
    QApplication.sendEvent(target, event)
    assert target.text() == "2.75"
    QTest.keySequence(target, QKeySequence.StandardKey.Undo)
    assert target.text() == "1.25"
    QTest.keySequence(target, QKeySequence.StandardKey.Redo)
    assert target.text() == "2.75"
    assert field.editor.toPlainText() == source

    if completion == "invalid":
        target.selectAll()
        QTest.keyClicks(target, "9" * 40)
        QTest.keyClick(target, Qt.Key.Key_Return)
    elif completion == "cancel":
        QTest.keyClick(target, Qt.Key.Key_Escape)
    elif completion == "focus-out":
        real_shell_scenario.input.focus_editor(field)
    else:
        QTest.keyClick(target, Qt.Key.Key_Return)
    expected = (
        source
        if completion in {"cancel", "invalid"}
        else source.replace("1.25", "2.75")
    )
    assert field.editor.toPlainText() == expected
    assert (
        real_shell_scenario.snapshots.capture(
            field, label="finished-weight"
        ).exact_weight_input
        is None
    )


@pytest.mark.usefixtures("qt_clipboard_owner")
def test_exact_weight_fluent_menu_survives_opening(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep Fluent's asynchronous menu alive until the user dismisses it."""

    source = "(red cube:1.25)"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.focus_editor(field)
    start_exact_weight_edit(field.editor, emphasis_token_for(field.editor))
    target = QApplication.focusWidget()
    assert isinstance(target, QLineEdit)
    position = target.rect().center()
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, position, target.mapToGlobal(position)
    )
    QApplication.sendEvent(target, event)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    menus = target.findChildren(ActionMenu)
    assert len(menus) == 1
    menu = menus[0]
    assert menu.isVisible()
    assert all("&" not in action.text() for action in menu.actions())
    assert field.editor.toPlainText() == source
    menu.close()
