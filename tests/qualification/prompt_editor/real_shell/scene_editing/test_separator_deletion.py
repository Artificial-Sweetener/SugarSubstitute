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

"""Verify deletion and immediate projection repair around separators."""

from __future__ import annotations

from PySide6.QtCore import Qt

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_backspace_at_region_start_deletes_separator_closing_bracket(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose a partial marker when backspacing from regional text."""

    source = "global\n[SEP]\npink witch hat"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    regional_start = source.index("pink")
    real_shell_scenario.input.set_source_cursor_position(field, regional_start)
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-region-backspace",
    )

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Backspace)
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-region-backspace",
    )

    assert before.cursor_position == regional_start
    assert before.caret_state_placement == "plain_text"
    assert after.source_text == "global\n[SEP\npink witch hat"
    assert after.cursor_position == source.index("[SEP]") + len("[SEP")
    assert "[SEP" in after.projection_text
    assert "[SEP]" not in after.projection_text
    assert not any(row.is_structural for row in after.visible_layout_rows)
    assert not snapshot_invariant_violations(after)


def test_real_shell_backspace_below_separator_decoration_rebuilds_immediately(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Delete a separator closing bracket immediately below its decoration."""

    source = "global\n[SEP]\nregional"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    regional_start = source.index("regional")
    real_shell_scenario.input.click_projected_source_position(field, regional_start)
    clicked = real_shell_scenario.snapshots.capture(
        field,
        label="separator-below-backspace-clicked",
    )

    immediate = real_shell_scenario.input.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_Backspace,
        label="separator-below-backspace-immediate",
    )
    settled = real_shell_scenario.snapshots.capture(
        field,
        label="separator-below-backspace-settled",
    )

    for snapshot in (immediate, settled):
        assert snapshot.source_text == "global\n[SEP\nregional"
        assert snapshot.document_view_region_separator_count == 0
        assert snapshot.projection_region_separator_count == 0
        assert not any(row.is_structural for row in snapshot.visible_layout_rows)
    assert clicked.cursor_position == regional_start
    assert clicked.caret_state_placement == "plain_text"
    assert not snapshot_invariant_violations(settled)


def test_real_shell_backspace_removes_extra_line_below_separator_decoration(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Delete an extra regional line without demoting the separator."""

    source = "global\n[SEP]\n\nregional"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    regional_start = source.index("regional")

    real_shell_scenario.input.click_projected_source_position(field, regional_start)
    clicked = real_shell_scenario.snapshots.capture(
        field,
        label="separator-extra-line-backspace-clicked",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Backspace)
    settled = real_shell_scenario.snapshots.capture(
        field,
        label="separator-extra-line-backspace-settled",
    )

    assert clicked.cursor_position == regional_start
    assert clicked.caret_state_placement == "plain_text"
    assert settled.source_text == "global\n[SEP]\nregional"
    assert settled.cursor_position == regional_start - 1
    assert settled.document_view_region_separator_count == 1
    assert settled.projection_region_separator_count == 1
    assert sum(row.is_structural for row in settled.visible_layout_rows) == 1
    assert not snapshot_invariant_violations(settled)


def test_real_shell_backspace_on_separator_closing_bracket_reveals_partial_marker(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Reveal editable partial marker text when deleting the closing bracket."""

    source = "global\n[SEP]\nregional"
    separator_end = source.index("[SEP]") + len("[SEP]")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, separator_end)
    before = real_shell_scenario.snapshots.capture(
        field,
        label="separator-closing-before",
    )

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Backspace)
    after = real_shell_scenario.snapshots.capture(
        field,
        label="separator-closing-after",
    )

    assert before.caret_state_placement == "token_trailing_edge"
    assert after.source_text == "global\n[SEP\nregional"
    assert "[SEP" in after.projection_text
    assert "[SEP]" not in after.projection_text
    assert after.projection_region_separator_count == 0
    assert not any(row.is_structural for row in after.visible_layout_rows)
    assert not snapshot_invariant_violations(after)


def test_real_shell_delete_before_separator_deletes_opening_bracket(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose partial marker text when deleting a separator's opening bracket."""

    source = "global\n[SEP]\npink witch hat"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    global_end = source.index("\n")
    real_shell_scenario.input.set_source_cursor_position(field, global_end)

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Delete)
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-separator-leading-delete",
    )

    assert after.source_text == "global\nSEP]\npink witch hat"
    assert after.cursor_position == global_end + 1
    assert "SEP]" in after.projection_text
    assert "[SEP]" not in after.projection_text
    assert not any(row.is_structural for row in after.visible_layout_rows)
    assert not snapshot_invariant_violations(after)


def test_real_shell_repeated_delete_exposes_partial_separator_text(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Preserve structure for one delete before exposing a partial marker."""

    source = "global\n\n[SEP]\npink witch hat"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    global_end = source.index("\n")
    real_shell_scenario.input.set_source_cursor_position(field, global_end)

    immediate_structural = (
        real_shell_scenario.input.press_key_and_capture_immediate_state(
            field,
            Qt.Key.Key_Delete,
            label="separator-delete-preserves-structure",
        )
    )
    still_structural = real_shell_scenario.snapshots.capture(
        field,
        label="separator-delete-preserves-structure-settled",
    )
    immediate_partial = real_shell_scenario.input.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_Delete,
        label="separator-delete-exposes-partial-marker",
    )
    now_partial = real_shell_scenario.snapshots.capture(
        field,
        label="separator-delete-exposes-partial-marker-settled",
    )

    for snapshot in (immediate_structural, still_structural):
        assert snapshot.source_text == "global\n[SEP]\npink witch hat"
        assert snapshot.projection_text.count("\ufffc") == 1
        assert "[SEP]" not in snapshot.projection_text
        assert sum(row.is_structural for row in snapshot.visible_layout_rows) == 1
        assert not snapshot.transient_deletion_overlay_present
    for snapshot in (immediate_partial, now_partial):
        assert snapshot.source_text == "global\nSEP]\npink witch hat"
        assert "SEP]" in snapshot.projection_text
        assert "[SEP]" not in snapshot.projection_text
        assert not any(row.is_structural for row in snapshot.visible_layout_rows)
        assert not snapshot.transient_deletion_overlay_present
    assert not snapshot_invariant_violations(still_structural)
    assert not snapshot_invariant_violations(now_partial)
