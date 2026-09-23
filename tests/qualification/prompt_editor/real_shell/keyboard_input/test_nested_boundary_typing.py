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

"""Keep rapid typing at nested emphasis boundaries source-ordered."""

from __future__ import annotations

from PySide6.QtTest import QTest

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_rapid_comma_space_after_new_nested_weight_keeps_caret_after_comma(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Insert a space after the comma even while nested projection catches up."""

    source = "alpha, (weighted segment:1.20), omega"
    insertion_position = source.index(":1.20")
    inserted = "more text, even more text, (fast:1.20), <lora:detail:0.8>, "
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    target = real_shell_scenario.input.focus_editor(field)
    real_shell_scenario.input.set_source_cursor_position(field, insertion_position)

    QTest.keyClicks(target, inserted)
    real_shell_scenario.wait_for_queued_delivery()
    snapshot = real_shell_scenario.snapshots.capture(
        field, label="rapid-nested-comma-space"
    )

    assert snapshot.source_text == (
        source[:insertion_position] + inserted + source[insertion_position:]
    )
    assert snapshot.cursor_position == insertion_position + len(inserted)
    assert not snapshot_invariant_violations(snapshot)
