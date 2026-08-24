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

"""Verify autocomplete dismissal across focus and route transitions."""

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
from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_ghost_requires_visually_present_dropdown(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear ghost text together with the visible dropdown on Escape."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(field, label="before-escape")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Escape)
    after = real_shell_scenario.snapshots.capture(field, label="after-escape")

    _assert_no_dismissal_violations(
        real_shell_scenario,
        artifact_name="ghost-without-visible-dropdown",
        before=before,
        after=after,
        action_name="escape",
        invariant="Visible ghost text requires a visually present dropdown.",
    )


def test_real_shell_click_away_clears_ghost_and_dropdown(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear ghost state and dropdown when focus leaves the editor."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(field, label="before-click-away")
    real_shell_scenario.input.click_away_from_editor(field)
    after = real_shell_scenario.snapshots.capture(field, label="after-click-away")

    _assert_no_dismissal_violations(
        real_shell_scenario,
        artifact_name="click-away-left-ghost-without-dropdown",
        before=before,
        after=after,
        action_name="click_away",
        invariant=(
            "Clicking outside active autocomplete clears projection ghost state "
            "and the visible dropdown."
        ),
    )


def test_real_shell_backpack_click_away_clears_basket_ghost(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear whitespace-tag ghost text when focus leaves autocomplete."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "backpack")
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-backpack-click-away",
    )
    real_shell_scenario.input.click_away_from_editor(field)
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-backpack-click-away",
    )

    _assert_no_dismissal_violations(
        real_shell_scenario,
        artifact_name="backpack-click-away-left-basket-ghost",
        before=before,
        after=after,
        action_name="click_away",
        invariant="Click-away must clear `backpack basket` ghost projection.",
    )

    assert not after.autocomplete_preview_active
    assert not after.autocomplete_presenter_panel_visible
    assert after.active_projection_text == after.projection_text == "backpack"


def test_real_shell_canvas_navigation_clears_ghost_and_dropdown(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear autocomplete state when moving away from and back to the canvas."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(field, label="before-canvas-nav")
    real_shell_scenario.input.switch_canvas("Output")
    real_shell_scenario.input.switch_canvas("Input")
    after = real_shell_scenario.snapshots.capture(field, label="after-canvas-nav")

    _assert_no_dismissal_violations(
        real_shell_scenario,
        artifact_name="canvas-navigation-left-ghost-without-dropdown",
        before=before,
        after=after,
        action_name="canvas",
        invariant=(
            "Canvas navigation clears autocomplete projection ghost state "
            "and the visible dropdown."
        ),
    )


def test_real_shell_workflow_navigation_clears_ghost_and_dropdown(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear autocomplete state when switching workflows and returning."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        alias="alpha",
        initial_text="",
    )
    real_shell_scenario.workflows.add_prompt_workflow(
        alias="beta",
        initial_text="",
        activate=False,
    )
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(field, label="before-workflow-nav")
    real_shell_scenario.workflows.activate_workflow("beta", force_refresh=False)
    real_shell_scenario.workflows.activate_workflow("alpha", force_refresh=False)
    field = real_shell_scenario.workflows.prompt_field("alpha")
    after = real_shell_scenario.snapshots.capture(field, label="after-workflow-nav")

    _assert_no_dismissal_violations(
        real_shell_scenario,
        artifact_name="workflow-navigation-left-ghost-without-dropdown",
        before=before,
        after=after,
        action_name="workflow",
        invariant=(
            "Workflow navigation clears autocomplete projection ghost state "
            "and the visible dropdown."
        ),
    )


def test_real_shell_escape_clears_ghost_and_dropdown(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear visible autocomplete surfaces when Escape dismisses completion."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-escape-clear",
    )
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Escape)
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-escape-clear",
    )

    _assert_no_dismissal_violations(
        real_shell_scenario,
        artifact_name="escape-did-not-clear-autocomplete",
        before=before,
        after=after,
        action_name="escape",
        invariant="Escape with active autocomplete clears ghost and dropdown.",
    )


def test_real_shell_cursor_navigation_clears_or_retargets_ghost(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Clear or retarget ghost text when a caret move changes the active prefix."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(field, label="before-left")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Left)
    after = real_shell_scenario.snapshots.capture(field, label="after-left")

    _assert_no_dismissal_violations(
        real_shell_scenario,
        artifact_name="cursor-navigation-stale-ghost",
        before=before,
        after=after,
        action_name="cursor",
        invariant="Cursor movement clears or retargets autocomplete ghost text.",
    )


def _assert_no_dismissal_violations(
    scenario: PromptEditorRealShellScenario,
    *,
    artifact_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
    action_name: str,
    invariant: str,
) -> None:
    """Persist complete state when a transition leaves a stale autocomplete view."""

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
            observed=f"violations={violations}; after={stale_observation(after)}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")
