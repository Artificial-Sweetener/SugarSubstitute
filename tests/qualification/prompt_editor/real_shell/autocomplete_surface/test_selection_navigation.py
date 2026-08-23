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

"""Verify autocomplete selection navigation through the real shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
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


def test_real_shell_backpack_up_arrow_selects_previous_suggestion(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Wrap from the first suggestion to the prior one with Up."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "backpack")
    before = real_shell_scenario.snapshots.capture(field, label="before-backpack-up")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Up)
    after = real_shell_scenario.snapshots.capture(field, label="after-backpack-up")

    violations = transition_violations(
        action_name="autocomplete_navigation",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "backpack-up-navigation-left-bad-state",
            before=before,
            after=after,
            invariant="Up-arrow must retarget autocomplete preview coherently.",
            observed=f"violations={violations}; after={stale_observation(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.autocomplete_session_selected_index == 0
    assert before.autocomplete_preview_suffix == " basket"
    assert after.autocomplete_session_selected_index == 1
    assert after.autocomplete_preview_suffix == " strap"
    assert after.autocomplete_presenter_panel_visible
    assert after.projection_text == "backpack"
    assert after.active_projection_text == "backpack strap"
    assert not violations


def test_real_shell_multiline_backpack_up_arrow_selects_previous_suggestion(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep Up navigation in autocomplete for a multiline prompt."""

    prefix_line = "empty eyes, pointy ears, sharp teeth"
    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text=f"{prefix_line}\n"
    )
    real_shell_scenario.input.move_cursor_to_end(field)
    real_shell_scenario.input.type_text(field, "backpack")
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-multiline-backpack-up",
    )

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Up)
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-multiline-backpack-up",
    )

    violations = transition_violations(
        action_name="autocomplete_navigation",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "multiline-backpack-up-navigation-left-bad-state",
            before=before,
            after=after,
            invariant="Up-arrow must retarget multiline autocomplete coherently.",
            observed=f"violations={violations}; after={stale_observation(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.autocomplete_preview_active
    assert before.autocomplete_preview_suffix == " basket"
    assert before.autocomplete_session_selected_index == 0
    assert after.autocomplete_preview_active
    assert after.autocomplete_preview_suffix == " strap"
    assert after.autocomplete_session_selected_index == 1
    assert after.autocomplete_presenter_panel_visible
    assert after.source_text == f"{prefix_line}\nbackpack"
    assert after.projection_text == after.source_text
    assert after.active_projection_text == f"{after.source_text} strap"
    assert not violations
