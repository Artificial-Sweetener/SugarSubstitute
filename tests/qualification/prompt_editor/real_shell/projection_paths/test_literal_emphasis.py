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

"""Qualify literal parenthesis presentation within production emphasis fields."""

from __future__ import annotations

from PySide6.QtCore import Qt

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_emphasis_hides_escapes_without_invisible_caret_stops(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose literal parens once while retaining the exact authored source."""

    source = r"(casshern \(series\):1.25), portrait"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    initial = real_shell_scenario.snapshots.capture(
        field, label="literal-emphasis-initial"
    )

    assert initial.source_text == source
    assert r"\(" not in initial.projection_text
    assert r"\)" not in initial.projection_text

    opening_escape = source.index(r"\(")
    real_shell_scenario.input.set_source_cursor_position(field, opening_escape)
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Right)
    after_right = real_shell_scenario.snapshots.capture(
        field, label="literal-emphasis-after-right"
    )

    assert after_right.cursor_position == opening_escape + 2
    assert not snapshot_invariant_violations(after_right)

    real_shell_scenario.input.set_rich_rendering(field, enabled=False)
    raw = real_shell_scenario.snapshots.capture(field, label="literal-emphasis-raw")
    assert raw.projection_text == source

    real_shell_scenario.input.set_rich_rendering(field, enabled=True)
    restored = real_shell_scenario.snapshots.capture(
        field, label="literal-emphasis-restored"
    )
    assert restored.source_text == source
    assert r"\(" not in restored.projection_text
    assert r"\)" not in restored.projection_text
    assert not snapshot_invariant_violations(restored)


def test_real_shell_edits_inside_literal_emphasis_keep_display_and_history(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep a literal nested group hidden through typing, undo, and redo."""

    source = r"(casshern \(series\):1.25), portrait"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    insert_at = source.index("series") + 3
    real_shell_scenario.input.set_source_cursor_position(field, insert_at)
    real_shell_scenario.input.press_key(field, Qt.Key.Key_X, text="x")
    edited = real_shell_scenario.snapshots.capture(
        field, label="literal-emphasis-edited"
    )

    assert edited.source_text == source[:insert_at] + "x" + source[insert_at:]
    assert r"\(" not in edited.projection_text
    assert r"\)" not in edited.projection_text
    assert not snapshot_invariant_violations(edited)

    real_shell_scenario.input.undo(field)
    undone = real_shell_scenario.snapshots.capture(
        field, label="literal-emphasis-undone"
    )
    assert undone.source_text == source
    assert r"\(" not in undone.projection_text

    real_shell_scenario.input.redo(field)
    redone = real_shell_scenario.snapshots.capture(
        field, label="literal-emphasis-redone"
    )
    assert redone.source_text == edited.source_text
    assert r"\(" not in redone.projection_text
    assert not snapshot_invariant_violations(redone)
