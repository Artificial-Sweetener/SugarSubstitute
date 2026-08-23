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

"""Verify real-shell selection, replacement, and paste interaction behavior."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import pytest

from tests.support.prompt_editor.real_shell.invariants.autocomplete import (
    stale_observation,
)
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


def test_real_shell_multiline_paste_keeps_projection_and_selection_sane(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep projection, caret, scroll, and overlays coherent after multiline paste."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="alpha")
    real_shell_scenario.input.focus_editor(field)
    QApplication.clipboard().setText("backpack basket\nempty eyes")
    QTest.keySequence(field.editor.viewport(), QKeySequence.StandardKey.Paste)
    real_shell_scenario.wait_for_queued_delivery()
    after = real_shell_scenario.snapshots.capture(field, label="after-multiline-paste")
    violations = snapshot_invariant_violations(after)
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "multiline-paste-left-bad-editor-state",
            before=after,
            after=after,
            invariant="Multiline paste must leave editor owners coherent.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert "backpack basket\nempty eyes" in after.source_text
    assert not violations


def test_real_shell_shift_selection_keeps_selection_and_caret_sane(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Extend and collapse a keyboard selection without corrupting editor owners."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alpha beta gamma"
    )
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(
        field, label="before-shift-selection"
    )
    for _ in range(5):
        real_shell_scenario.input.press_key(
            field, Qt.Key.Key_Left, modifiers=Qt.KeyboardModifier.ShiftModifier
        )
    selected = real_shell_scenario.snapshots.capture(field, label="after-shift-left")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Right)
    collapsed = real_shell_scenario.snapshots.capture(
        field, label="after-collapse-right"
    )
    selection_violations = transition_violations(
        action_name="selection",
        before=before,
        after=selected,
        snapshot_violations=snapshot_invariant_violations,
    )
    collapse_violations = transition_violations(
        action_name="caret",
        before=selected,
        after=collapsed,
        snapshot_violations=snapshot_invariant_violations,
    )
    if selection_violations or collapse_violations:
        artifact = real_shell_scenario.artifacts.save(
            "shift-selection-left-bad-editor-state",
            before=before,
            after=collapsed,
            invariant="Shift selection and collapse must keep editor owners coherent.",
            observed=f"selection={selection_violations}; collapse={collapse_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert selected.selected_source_text == "gamma"
    assert collapsed.selection_range[0] == collapsed.selection_range[1]
    assert not selection_violations
    assert not collapse_violations


def test_real_shell_wrapped_multiline_selection_geometry_clears_on_collapse(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose bounded wrapped selection geometry and clear it on collapse."""

    prompt = (
        "masterpiece, best quality, official art, backpack basket,\n"
        "empty eyes, pointy ears, sharp teeth, too many rabbits,\n"
        "glowing red eyes, long white hair, swept bangs"
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
    real_shell_scenario.shell.resize(520, 620)
    real_shell_scenario.wait_for_queued_delivery()
    cursor = cast(Any, field.editor).textCursor()
    start, end = prompt.index("backpack"), prompt.index("glowing")
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    selected = real_shell_scenario.snapshots.capture(
        field, label="after-wrapped-selection"
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Right)
    collapsed = real_shell_scenario.snapshots.capture(
        field, label="after-selection-collapse"
    )
    selection_violations = transition_violations(
        action_name="selection",
        before=selected,
        after=selected,
        snapshot_violations=snapshot_invariant_violations,
    )
    collapse_violations = transition_violations(
        action_name="caret",
        before=selected,
        after=collapsed,
        snapshot_violations=snapshot_invariant_violations,
    )
    violations = selection_violations + collapse_violations
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "wrapped-selection-geometry-left-bad-state",
            before=selected,
            after=collapsed,
            invariant="Wrapped multiline selection rects must be bounded and clear on collapse.",
            observed=f"selection={selection_violations}; collapse={collapse_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert selected.selection_range == (start, end)
    assert selected.selection_rects
    assert collapsed.selection_range[0] == collapsed.selection_range[1]
    assert not collapsed.selection_rects
    assert not violations


def test_real_shell_selection_replacement_collapses_selection_and_updates_projection(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Collapse a replaced source selection at the inserted text."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alpha beta gamma"
    )
    cursor = cast(Any, field.editor).textCursor()
    start, end = len("alpha "), len("alpha beta")
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    before = real_shell_scenario.snapshots.capture(
        field, label="before-selection-replace"
    )
    real_shell_scenario.input.type_text(field, "omega")
    after = real_shell_scenario.snapshots.capture(
        field, label="after-selection-replace"
    )
    violations = transition_violations(
        action_name="selection",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "selection-replacement-left-bad-editor-state",
            before=before,
            after=after,
            invariant="Selection replacement must collapse and update projection.",
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert after.source_text == "alpha omega gamma"
    assert after.selection_range[0] == after.selection_range[1]
    assert after.cursor_position == len("alpha omega")
    assert after.projection_document_source_text == after.source_text
    assert not violations


def test_real_shell_selection_clears_active_autocomplete_surfaces(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear ghost text and dropdown when an active completion gains selection."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(
        field, label="before-autocomplete-selection"
    )
    real_shell_scenario.input.press_key(
        field, Qt.Key.Key_Left, modifiers=Qt.KeyboardModifier.ShiftModifier
    )
    after = real_shell_scenario.snapshots.capture(
        field, label="after-autocomplete-selection"
    )
    violations = transition_violations(
        action_name="selection",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "selection-left-autocomplete-active",
            before=before,
            after=after,
            invariant="Selection must clear autocomplete ghost and dropdown.",
            observed=f"violations={violations}; after={stale_observation(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert before.autocomplete_preview_active
    assert after.selection_range[0] != after.selection_range[1]
    assert not after.autocomplete_preview_active
    assert not after.autocomplete_presenter_panel_visible
    assert not violations
