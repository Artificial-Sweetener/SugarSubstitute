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

"""Verify selection and whitespace lifecycle for real-shell autocomplete."""

from __future__ import annotations

from PySide6.QtCore import Qt
import pytest

from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
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


def test_real_shell_autocomplete_selection_navigation_stays_coherent(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep session, popup, and preview coherent while changing selection."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text_and_wait_for_autocomplete(field, "re")
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-autocomplete-down",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Down)
    after_down = real_shell_scenario.snapshots.capture(
        field,
        label="after-autocomplete-down",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Up)
    after_up = real_shell_scenario.snapshots.capture(
        field,
        label="after-autocomplete-up",
    )

    down_violations = transition_violations(
        action_name="autocomplete_navigation",
        before=before,
        after=after_down,
        snapshot_violations=snapshot_invariant_violations,
    )
    up_violations = transition_violations(
        action_name="autocomplete_navigation",
        before=after_down,
        after=after_up,
        snapshot_violations=snapshot_invariant_violations,
    )
    violations = down_violations + up_violations
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "autocomplete-selection-navigation-left-bad-state",
            before=before,
            after=after_up,
            invariant="Autocomplete selection movement must keep session and popup coherent.",
            observed=f"down={down_violations}; up={up_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert before.autocomplete_session_selected_index == 0
    assert after_down.autocomplete_session_selected_index == 1
    assert after_up.autocomplete_session_selected_index == 0
    assert after_up.popup_state_visible
    assert after_up.autocomplete_preview_active
    assert not violations


def test_real_shell_space_does_not_displace_ghost_text(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear non-whitespace completion instead of displacing its ghost text."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text_and_wait_for_autocomplete(field, "re")
    before = real_shell_scenario.snapshots.capture(field, label="before-space")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Space, text=" ")
    after = real_shell_scenario.snapshots.capture(field, label="after-space")
    violations = transition_violations(
        action_name="space",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )

    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "space-displaced-ghost-text",
            before=before,
            after=after,
            invariant=(
                "Space with active autocomplete must not leave ghost text visually "
                "separated from the committed prefix."
            ),
            observed=f"source after Space was {after.source_text!r}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert not violations
    assert not after.autocomplete_preview_active
    assert not after.autocomplete_presenter_panel_visible


def test_real_shell_space_keeps_whitespace_tag_completion_active(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep a whitespace-containing tag completion active after Space."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text_and_wait_for_autocomplete(field, "backpack")
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-backpack-space",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Space, text=" ")
    after = real_shell_scenario.snapshots.capture(field, label="after-backpack-space")

    violations = transition_violations(
        action_name="space",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations or not after.autocomplete_preview_active:
        artifact = real_shell_scenario.artifacts.save(
            "space-dismissed-whitespace-tag-completion",
            before=before,
            after=after,
            invariant=(
                "Space is part of tag autocomplete; `backpack ` should keep "
                "`backpack basket` active with `basket` as ghost text."
            ),
            observed=f"violations={violations}; after={stale_observation(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "backpack "
    assert after.autocomplete_session_prefix == "backpack "
    assert after.autocomplete_preview_suffix == "basket"
    assert after.autocomplete_preview_source_position == len("backpack ")
    assert after.autocomplete_presenter_panel_visible


def test_real_shell_space_clears_stale_whitespace_leading_preview(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Retarget a leaked whitespace-leading preview after Space commits."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="backpack")
    real_shell_scenario.input.move_cursor_to_end(field)
    field.editor.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("backpack"),
            suffix_text=" basket",
        )
    )
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-stale-backpack-space",
    )

    real_shell_scenario.input.press_key(field, Qt.Key.Key_Space, text=" ")
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-stale-backpack-space",
    )

    violations = transition_violations(
        action_name="space",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if (
        violations
        or after.cursor_position != len("backpack ")
        or not after.autocomplete_preview_active
        or after.autocomplete_preview_suffix != "basket"
        or after.autocomplete_preview_source_position != len("backpack ")
    ):
        artifact = real_shell_scenario.artifacts.save(
            "space-retargeted-stale-backpack-preview",
            before=before,
            after=after,
            invariant=(
                "Space must retarget stale whitespace-leading autocomplete preview "
                "instead of moving the caret through ghost text."
            ),
            observed=stale_observation(after),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "backpack "
    assert after.cursor_position == len("backpack ")
    assert after.autocomplete_preview_active
    assert after.autocomplete_preview_suffix == "basket"
    assert after.autocomplete_preview_source_position == len("backpack ")


def test_real_shell_space_after_autocomplete_dismissal_rebuilds_projection(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Rebuild projection after Space follows an autocomplete dismissal."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text_and_wait_for_autocomplete(field, "backpack")
    active = real_shell_scenario.snapshots.capture(
        field,
        label="before-backpack-escape",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Escape)
    dismissed = real_shell_scenario.snapshots.capture(
        field,
        label="after-backpack-escape",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Space, text=" ")
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-backpack-space-after-escape",
    )

    violations = transition_violations(
        action_name="space",
        before=dismissed,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "space-after-backpack-dismissal-left-stale-projection",
            before=active,
            after=after,
            invariant=(
                "Space after autocomplete dismissal must immediately rebuild "
                "projection so stale ghost text cannot remain painted."
            ),
            observed=(
                f"violations={violations}; dismissed={stale_observation(dismissed)}"
            ),
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert after.source_text == "backpack "
    assert after.projection_document_source_text == "backpack "
    assert after.active_projection_source_text == "backpack "
    assert not after.projection_has_pending_update
    assert not after.projection_has_stale_geometry
