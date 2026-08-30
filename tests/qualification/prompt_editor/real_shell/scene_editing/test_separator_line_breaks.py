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

"""Verify separator-aware vertical traversal and line-break projection."""

from __future__ import annotations

from PySide6.QtCore import Qt
import pytest

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_vertical_navigation_crosses_separator_as_line_break(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Skip separator chrome while preserving the text-column affinity."""

    source = "alpha\n[SEP]\nbravo"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    global_position = source.index("alpha") + 3
    regional_position = source.index("bravo") + 3
    real_shell_scenario.input.set_source_cursor_position(field, regional_position)

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Up)
    after_up = real_shell_scenario.snapshots.capture(
        field,
        label="separator-up-crossing",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Down)
    after_down = real_shell_scenario.snapshots.capture(
        field,
        label="separator-down-crossing",
    )

    assert after_up.cursor_position == global_position
    assert after_up.caret_state_placement == "plain_text"
    assert after_down.cursor_position == regional_position
    assert after_down.caret_state_placement == "plain_text"
    assert not snapshot_invariant_violations(after_up)
    assert not snapshot_invariant_violations(after_down)


@pytest.mark.parametrize(
    ("separator_occurrence", "boundary"),
    (
        (0, "before"),
        (0, "after"),
        (1, "before"),
        (1, "after"),
    ),
)
def test_real_shell_line_breaks_adjacent_to_multiple_separators_preserve_chrome(
    real_shell_scenario: PromptEditorRealShellScenario,
    separator_occurrence: int,
    boundary: str,
) -> None:
    """Preserve both structural rows beside either separator boundary."""

    source = (
        "testbest quality, score_7, masterpiece, very aesthetic\n\n"
        "2girls, standing, full body, looking at viewer, outdoors, cherry blossoms, "
        "school uniform \n"
        "[SEP]\n"
        "1girl, red hair, long hair, green eyes, smile, blazer, pleated skirt, "
        "black thighhighs \n\n\n"
        "[SEP]\n"
        "1girl, blue hair, short hair, blue eyes, serious, cardigan, pleated skirt, "
        "kneehighs\n"
    )
    separator_positions = (source.index("[SEP]"), source.rindex("[SEP]"))
    insertion_position = separator_positions[separator_occurrence]
    if boundary == "after":
        insertion_position += len("[SEP]\n")

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, insertion_position)
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Return)
    after = real_shell_scenario.snapshots.capture(
        field,
        label=f"separator-{separator_occurrence}-{boundary}-newline",
    )

    assert after.projection_region_separator_count == 2
    assert after.document_view_region_separator_count == 2
    assert after.projection_text.count("\ufffc") == 2
    assert "[SEP]" not in after.projection_text
    assert not snapshot_invariant_violations(after)


@pytest.mark.parametrize(
    ("source", "insertion_position"),
    (
        ("school uniform [SEP]\nregional", len("school uniform ")),
        ("global\n[SEP] regional", len("global\n[SEP]")),
    ),
)
def test_real_shell_line_break_promotes_inline_separator_to_decoration(
    real_shell_scenario: PromptEditorRealShellScenario,
    source: str,
    insertion_position: int,
) -> None:
    """Publish structural chrome immediately when a line break isolates `[SEP]`."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(field, insertion_position)

    immediate = real_shell_scenario.input.press_key_and_capture_immediate_state(
        field,
        Qt.Key.Key_Return,
        label="separator-promotion-immediate",
    )
    settled = real_shell_scenario.snapshots.capture(
        field,
        label="separator-promotion-settled",
    )

    for snapshot in (immediate, settled):
        assert snapshot.projection_region_separator_count == 1
        assert snapshot.document_view_region_separator_count == 1
        assert snapshot.projection_text.count("\ufffc") == 1
        assert "[SEP]" not in snapshot.projection_text
    assert not snapshot_invariant_violations(settled)
