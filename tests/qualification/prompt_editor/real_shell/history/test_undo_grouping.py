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

"""Verify observable prompt-editor undo, redo, and edit-group behavior."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
import pytest

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_undo_redo_roundtrip_keeps_projection_and_history_sane(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep editor owners coherent through real undo and redo key sequences."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "alpha")
    edited = real_shell_scenario.snapshots.capture(field, label="after-typing-alpha")
    real_shell_scenario.input.focus_editor(field)
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Undo)
    real_shell_scenario.wait_for_queued_delivery()
    undone = real_shell_scenario.snapshots.capture(field, label="after-undo-alpha")
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Redo)
    real_shell_scenario.wait_for_queued_delivery()
    redone = real_shell_scenario.snapshots.capture(field, label="after-redo-alpha")

    undo_violations = transition_violations(
        action_name="undo_redo",
        before=edited,
        after=undone,
        snapshot_violations=snapshot_invariant_violations,
    )
    redo_violations = transition_violations(
        action_name="undo_redo",
        before=undone,
        after=redone,
        snapshot_violations=snapshot_invariant_violations,
    )
    if undo_violations or redo_violations:
        artifact = real_shell_scenario.artifacts.save(
            "undo-redo-left-bad-editor-state",
            before=undone,
            after=redone,
            invariant="Undo/redo must leave editor owners coherent.",
            observed=f"undo={undo_violations}; redo={redo_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert redone.source_text == edited.source_text
    assert not undo_violations
    assert not redo_violations


def test_real_shell_contiguous_typing_undoes_as_one_group(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Undo contiguous typing with one user-visible history operation."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    before = real_shell_scenario.snapshots.capture(
        field, label="before-typing-group-alpha"
    )
    real_shell_scenario.input.type_text(field, "alpha")
    typed = real_shell_scenario.snapshots.capture(
        field, label="after-typing-group-alpha"
    )
    real_shell_scenario.input.focus_editor(field)
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Undo)
    real_shell_scenario.wait_for_queued_delivery()
    undone = real_shell_scenario.snapshots.capture(
        field, label="after-typing-group-undo"
    )
    violations = transition_violations(
        action_name="undo_redo",
        before=typed,
        after=undone,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "typing-group-undo-left-bad-editor-state",
            before=typed,
            after=undone,
            invariant="Contiguous word typing must undo as one edit group.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert typed.source_text == "alpha"
    assert undone.source_text == ""
    assert undone.redo_available
    assert not violations
    assert before.source_text == ""


def test_real_shell_repeated_backspace_undoes_as_one_delete_group(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Undo repeated Backspace with one user-visible history operation."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="abcdef")
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(field, label="before-delete-group")
    real_shell_scenario.input.press_key_burst(
        field,
        Qt.Key.Key_Backspace,
        repetitions=3,
    )
    deleted = real_shell_scenario.snapshots.capture(field, label="after-delete-group")
    real_shell_scenario.input.focus_editor(field)
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Undo)
    real_shell_scenario.wait_for_queued_delivery()
    undone = real_shell_scenario.snapshots.capture(
        field, label="after-delete-group-undo"
    )
    delete_violations = transition_violations(
        action_name="backspace",
        before=before,
        after=deleted,
        snapshot_violations=snapshot_invariant_violations,
    )
    undo_violations = transition_violations(
        action_name="undo_redo",
        before=deleted,
        after=undone,
        snapshot_violations=snapshot_invariant_violations,
    )
    violations = delete_violations + undo_violations
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "delete-group-undo-left-bad-editor-state",
            before=before,
            after=undone,
            invariant="Repeated Backspace must undo as one delete edit group.",
            observed=f"delete={delete_violations}; undo={undo_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert deleted.source_text == "abc"
    assert undone.source_text == "abcdef"
    assert undone.redo_available
    assert not violations
