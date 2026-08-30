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

"""Verify authored separator completion and regional publication."""

from __future__ import annotations

from PySide6.QtCore import Qt
import pytest

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_newline_before_separator_preserves_regional_structure(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep the following separator stable after a global-prompt newline."""

    source = (
        "blue decorative staff bow ribbon,  \n\n[SEP]\n"
        "grass, flower field, cloudy sky, pink petals, blue petals, "
        "mountainous horizon,    "
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    cursor_position = source.index("ribbon,") + len("ribbon,")
    real_shell_scenario.input.set_source_cursor_position(field, cursor_position)
    before = real_shell_scenario.snapshots.capture(field, label="before-global-newline")

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Return)
    after = real_shell_scenario.snapshots.capture(field, label="after-global-newline")

    assert (
        after.source_text == source[:cursor_position] + "\n" + source[cursor_position:]
    )
    assert before.projection_text.count("\ufffc") == 1
    assert after.projection_text.count("\ufffc") == 1
    assert "[SEP]" not in after.projection_text
    assert not transition_violations(
        action_name="newline",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )


def test_real_shell_separator_completion_normalizes_in_one_undo_transaction(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Normalize a completed separator in the authored edit transaction."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="global[SEP")
    real_shell_scenario.input.set_source_cursor_position(field, len("global[SEP"))

    real_shell_scenario.input.type_text(field, "]")
    normalized = real_shell_scenario.snapshots.capture(
        field,
        label="normalized-separator",
    )
    real_shell_scenario.input.undo(field)
    undone = real_shell_scenario.snapshots.capture(field, label="undone-separator")

    assert normalized.source_text == "global\n[SEP]\n"
    assert normalized.projection_text.count("\ufffc") == 1
    assert undone.source_text == "global[SEP"
    assert not snapshot_invariant_violations(normalized)
    assert not snapshot_invariant_violations(undone)


@pytest.mark.parametrize(
    ("source", "cursor_position", "expected_source"),
    (
        (
            "global\n[SEP]\nregional",
            len("global\n[SEP]\n"),
            "global\n[SEP]\n[SEP]\nregional",
        ),
        (
            "global\n[SEP]\nregional alpha",
            len("global\n[SEP]\nregional"),
            "global\n[SEP]\nregional\n[SEP]\n alpha",
        ),
    ),
)
def test_real_shell_typing_second_separator_creates_new_region(
    real_shell_scenario: PromptEditorRealShellScenario,
    source: str,
    cursor_position: int,
    expected_source: str,
) -> None:
    """Create another partition when authoring `[SEP]` inside one region."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, cursor_position)

    real_shell_scenario.input.type_text(field, "[SEP]")
    after = real_shell_scenario.snapshots.capture(
        field,
        label="authored-second-separator",
    )

    assert after.source_text == expected_source
    assert after.document_view_region_separator_count == 2
    assert after.projection_region_separator_count == 2
    assert after.projection_text.count("\ufffc") == 2
    assert "[SEP]" not in after.projection_text
    assert sum(row.is_structural for row in after.visible_layout_rows) == 2
    assert not snapshot_invariant_violations(after)


def test_real_shell_second_separator_completion_publishes_adjacent_region_immediately(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Publish both partitions immediately after completing a nearby marker."""

    source = "global\n[SEP]\n[SEPregional"
    completion_position = source.index("regional")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, completion_position)

    immediate = real_shell_scenario.input.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_BracketRight,
        label="adjacent-second-separator-immediate",
    )
    settled = real_shell_scenario.snapshots.capture(
        field,
        label="adjacent-second-separator-settled",
    )

    for snapshot in (immediate, settled):
        _assert_two_published_regions(snapshot)
    assert not snapshot_invariant_violations(settled)


def _assert_two_published_regions(snapshot: PromptEditorStateSnapshot) -> None:
    """Assert the exact source and structure for two published regions."""

    assert snapshot.source_text == "global\n[SEP]\n[SEP]\nregional"
    assert snapshot.document_view_region_separator_count == 2
    assert snapshot.projection_region_separator_count == 2
    assert snapshot.projection_text.count("\ufffc") == 2
    assert "[SEP]" not in snapshot.projection_text
    assert sum(row.is_structural for row in snapshot.visible_layout_rows) == 2
