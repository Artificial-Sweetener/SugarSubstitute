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

"""Verify real-shell transient projection editing and repair contracts."""

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


def test_real_shell_backspace_keeps_projection_state_current(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep projection owner state current after Backspace."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "masterpiece, best quality")
    before = real_shell_scenario.snapshots.capture(field, label="before-backspace")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Backspace)
    after = real_shell_scenario.snapshots.capture(field, label="after-backspace")
    _assert_transition(
        real_shell_scenario,
        artifact_name="backspace-live-paint-mismatch",
        action_name="backspace",
        before=before,
        after=after,
        invariant="Backspace must leave projection owner state current.",
    )


def test_real_shell_transient_edit_dirty_regions_stay_bounded(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep dirty regions bounded across wrapped insertion and erasure."""

    prompt = (
        "(small:1.20) breasts, flat chest, see-through silhouette, "
        "sparkling blue sash, sparkling blue bralette,\n\n"
        "backpack basket\n\n"
        "empty eyes, pointy ears, sharp teeth, too many rabbits, backlighting"
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
    real_shell_scenario.shell.resize(500, 620)
    real_shell_scenario.wait_for_queued_delivery()
    real_shell_scenario.input.move_cursor_to_end(field)
    before_insert = real_shell_scenario.snapshots.capture(
        field,
        label="before-dirty-region-insert",
    )
    real_shell_scenario.input.type_text(field, ", red eyes")
    after_insert = real_shell_scenario.snapshots.capture(
        field,
        label="after-dirty-region-insert",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Backspace)
    after_backspace = real_shell_scenario.snapshots.capture(
        field,
        label="after-dirty-region-backspace",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Delete)
    after_delete = real_shell_scenario.snapshots.capture(
        field,
        label="after-dirty-region-delete",
    )

    insert_violations = transition_violations(
        action_name="typing",
        before=before_insert,
        after=after_insert,
        snapshot_violations=snapshot_invariant_violations,
    )
    backspace_violations = transition_violations(
        action_name="backspace",
        before=after_insert,
        after=after_backspace,
        snapshot_violations=snapshot_invariant_violations,
    )
    delete_violations = transition_violations(
        action_name="delete",
        before=after_backspace,
        after=after_delete,
        snapshot_violations=snapshot_invariant_violations,
    )
    violations = insert_violations + backspace_violations + delete_violations
    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "transient-edit-dirty-regions-left-bad-state",
            before=before_insert,
            after=after_delete,
            invariant="Transient edit dirty regions must remain bounded and coherent.",
            observed=f"insert={insert_violations}; backspace={backspace_violations}; delete={delete_violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
    assert after_insert.source_text.endswith("backlighting, red eyes")
    assert not violations


def test_real_shell_deferred_typing_keeps_transient_overlay_state_valid(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose valid transient overlay state during deferred safe typing."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alpha, (small:1.20), <lora:missing:1.00>, omega"
    )
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(
        field, label="before-deferred-overlay-typing"
    )
    real_shell_scenario.input.type_text(field, "re")
    after = real_shell_scenario.snapshots.capture(
        field, label="after-deferred-overlay-typing"
    )
    _assert_transition(
        real_shell_scenario,
        artifact_name="deferred-typing-left-invalid-transient-overlay",
        action_name="typing",
        before=before,
        after=after,
        invariant="Deferred typing must expose valid transient overlay owner state.",
    )
    assert after.source_text.endswith("omegare")
    assert after.transient_caret_geometry_present
    assert after.transient_caret_geometry_valid
    assert after.transient_insertion_overlay_present
    assert after.transient_insertion_overlay_valid


def test_real_shell_trailing_typing_keeps_caret_aligned_without_erasing_background(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Align accumulated end typing without erasing the underlying projection."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="alpha")
    real_shell_scenario.input.move_cursor_to_end(field)
    before = real_shell_scenario.snapshots.capture(
        field, label="trailing-typing-before"
    )
    after = real_shell_scenario.input.type_text_and_capture_immediate_state(
        field, "xyz", label="trailing-typing-immediate"
    )
    command = field.editor._surface._render_frame_owner.frame.transient_layer.insertion
    assert command is not None
    assert command.text == "xyz"
    assert before.caret_rect is not None
    assert after.transient_insertion_overlay_viewport_rect is not None
    assert after.caret_rect is not None
    assert command.rect[0] == pytest.approx(before.caret_rect[0])
    assert after.caret_rect[0] == pytest.approx(command.rect[0] + command.rect[2])
    assert not command.erase_underlying_content


def test_real_shell_space_after_deferred_typing_updates_projection_or_bridge(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Retain projection or a valid transient bridge after deferred-space input."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "alpha")
    before = real_shell_scenario.snapshots.capture(field, label="before-deferred-space")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Space, text=" ")
    after = real_shell_scenario.snapshots.capture(field, label="after-deferred-space")
    _assert_transition(
        real_shell_scenario,
        artifact_name="space-after-deferred-typing-left-stale-projection",
        action_name="space",
        before=before,
        after=after,
        invariant="Space after deferred typing must either rebuild projection or keep a valid transient bridge.",
    )
    assert after.source_text == "alpha "


def test_real_shell_delete_at_end_after_canvas_navigation_is_noop(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Avoid constructing an invalid projection range for Delete at source end."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    real_shell_scenario.input.switch_canvas("Output")
    real_shell_scenario.input.switch_canvas("Input")
    before = real_shell_scenario.snapshots.capture(field, label="before-delete-at-end")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Delete)
    after = real_shell_scenario.snapshots.capture(field, label="after-delete-at-end")
    assert after.source_text == before.source_text
    assert after.cursor_position == before.cursor_position


def _assert_transition(
    scenario: PromptEditorRealShellScenario,
    *,
    artifact_name: str,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
    invariant: str,
) -> None:
    """Fail with a replay artifact when a projection transition violates owners."""

    violations = transition_violations(
        action_name=action_name,
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
    if violations:
        artifact = scenario.artifacts.save(
            artifact_name,
            before=before,
            after=after,
            invariant=invariant,
            observed=f"violations={violations}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
