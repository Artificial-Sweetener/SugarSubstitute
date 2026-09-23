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

"""Qualify intentional nested emphasis through the real shortcut route."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from substitute.application.prompt_editor.document.service import PromptDocumentService
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_selecting_word_inside_weighted_phrase_creates_inner_emphasis(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Permit a deliberate inner shell after the phrase received a weight."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="atmospheric perspective, portrait"
    )
    cursor = field.editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len("atmospheric perspective"), QTextCursor.MoveMode.KeepAnchor)
    field.editor.setTextCursor(cursor)
    first = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )
    assert first.source_after == "(atmospheric perspective:1.05), portrait"

    cursor = field.editor.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(1 + len("atmospheric"), QTextCursor.MoveMode.KeepAnchor)
    field.editor.setTextCursor(cursor)
    second = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )

    assert second.source_after == "((atmospheric:1.05) perspective:1.05), portrait"
    assert (
        len(
            PromptDocumentService()
            .build_document_view(second.source_after)
            .emphasis_spans
        )
        == 2
    )
    snapshot = real_shell_scenario.snapshots.capture(
        field, label="nested-inner-after-outer"
    )
    assert snapshot.projection_token_count == 2
    assert ":1.05)" not in snapshot.projection_text
    assert not snapshot_invariant_violations(snapshot)

    adjusted_inner = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )
    assert (
        adjusted_inner.source_after == "((atmospheric:1.10) perspective:1.05), portrait"
    )

    cursor = field.editor.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(
        adjusted_inner.source_after.rfind(":1.05)"),
        QTextCursor.MoveMode.KeepAnchor,
    )
    field.editor.setTextCursor(cursor)
    adjusted_outer = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )
    assert (
        adjusted_outer.source_after == "((atmospheric:1.10) perspective:1.10), portrait"
    )
    after_adjustments = real_shell_scenario.snapshots.capture(
        field, label="nested-emphasis-independent-adjustments"
    )
    assert after_adjustments.projection_token_count == 2
    assert not snapshot_invariant_violations(after_adjustments)


def test_selecting_phrase_around_weighted_word_creates_outer_emphasis(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Permit a deliberate outer shell around a previously weighted word."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="atmospheric perspective, portrait"
    )
    cursor = field.editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len("atmospheric"), QTextCursor.MoveMode.KeepAnchor)
    field.editor.setTextCursor(cursor)
    first = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )
    assert first.source_after == "(atmospheric:1.05) perspective, portrait"

    cursor = field.editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(
        len("(atmospheric:1.05) perspective"), QTextCursor.MoveMode.KeepAnchor
    )
    field.editor.setTextCursor(cursor)
    second = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )

    assert second.source_after == "((atmospheric:1.05) perspective:1.05), portrait"
    assert (
        len(
            PromptDocumentService()
            .build_document_view(second.source_after)
            .emphasis_spans
        )
        == 2
    )
    snapshot = real_shell_scenario.snapshots.capture(
        field, label="nested-outer-after-inner"
    )
    assert snapshot.projection_token_count == 2
    assert ":1.05)" not in snapshot.projection_text
    assert not snapshot_invariant_violations(snapshot)


def test_three_nested_shells_keep_caret_and_projection_coherent(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep every shell interactive when no plain content separates them."""

    source = "(((cat:1.05):1.10):1.15), portrait"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    initial = real_shell_scenario.snapshots.capture(field, label="three-deep-initial")

    assert initial.projection_token_count == 3
    assert not snapshot_invariant_violations(initial)

    real_shell_scenario.input.set_source_cursor_position(field, source.index("cat") + 1)
    inner = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )
    assert inner.source_after == "(((cat:1.10):1.10):1.15), portrait"
    after = real_shell_scenario.snapshots.capture(field, label="three-deep-adjusted")
    assert after.projection_token_count == 3
    assert not snapshot_invariant_violations(after)


def test_editing_inside_nested_emphasis_preserves_both_weights_and_history(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep nested decorations aligned through typing, undo, and redo."""

    source = "((atmospheric:1.05) perspective:1.15), portrait"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    insert_at = source.index("atmospheric") + 5
    real_shell_scenario.input.set_source_cursor_position(field, insert_at)
    real_shell_scenario.input.press_key(field, Qt.Key.Key_X, text="x")
    edited = real_shell_scenario.snapshots.capture(field, label="nested-edit")

    assert edited.source_text == source[:insert_at] + "x" + source[insert_at:]
    assert not snapshot_invariant_violations(edited)
    real_shell_scenario.input.set_source_cursor_position(field, len(edited.source_text))
    real_shell_scenario.wait_until(
        lambda: (
            real_shell_scenario.snapshots.capture(
                field, label="nested-edit-wait"
            ).projection_token_count
            == 2
        ),
        description="nested edit projection",
    )
    settled_edit = real_shell_scenario.snapshots.capture(
        field, label="nested-edit-settled"
    )
    assert settled_edit.projection_token_count == 2
    assert not snapshot_invariant_violations(settled_edit)

    real_shell_scenario.input.undo(field)
    undone = real_shell_scenario.snapshots.capture(field, label="nested-undo")
    assert undone.source_text == source
    assert not snapshot_invariant_violations(undone)
    real_shell_scenario.input.set_source_cursor_position(field, len(undone.source_text))
    real_shell_scenario.wait_until(
        lambda: (
            real_shell_scenario.snapshots.capture(
                field, label="nested-undo-wait"
            ).projection_token_count
            == 2
        ),
        description="nested undo projection",
    )
    settled_undo = real_shell_scenario.snapshots.capture(
        field, label="nested-undo-settled"
    )
    assert settled_undo.projection_token_count == 2
    assert not snapshot_invariant_violations(settled_undo)

    real_shell_scenario.input.redo(field)
    redone = real_shell_scenario.snapshots.capture(field, label="nested-redo")
    assert redone.source_text == edited.source_text
    assert not snapshot_invariant_violations(redone)
    real_shell_scenario.input.set_source_cursor_position(field, len(redone.source_text))
    real_shell_scenario.wait_until(
        lambda: (
            real_shell_scenario.snapshots.capture(
                field, label="nested-redo-wait"
            ).projection_token_count
            == 2
        ),
        description="nested redo projection",
    )
    settled_redo = real_shell_scenario.snapshots.capture(
        field, label="nested-redo-settled"
    )
    assert settled_redo.projection_token_count == 2
    assert not snapshot_invariant_violations(settled_redo)


def test_keyboard_highlight_inside_outer_shell_targets_inner_word(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Let visible caret navigation select a word for intentional nesting."""

    source = "(atmospheric perspective:1.15), portrait"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, 1)
    for _character in "atmospheric":
        real_shell_scenario.input.press_key(
            field, Qt.Key.Key_Right, modifiers=Qt.KeyboardModifier.ShiftModifier
        )
    selected = real_shell_scenario.snapshots.capture(field, label="nested-highlight")
    assert selected.selected_source_text == "atmospheric"
    assert not snapshot_invariant_violations(selected)

    adjusted = real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier
    )
    assert adjusted.source_after == "((atmospheric:1.05) perspective:1.15), portrait"
    nested = real_shell_scenario.snapshots.capture(
        field, label="nested-highlight-adjusted"
    )
    assert nested.projection_token_count == 2
    assert not snapshot_invariant_violations(nested)
