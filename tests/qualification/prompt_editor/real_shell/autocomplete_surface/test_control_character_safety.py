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

"""Verify autocomplete control keys preserve prompt source safety."""

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


def test_real_shell_autocomplete_tab_does_not_insert_literal_tab(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Accept active autocomplete on Tab without writing a literal tab."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "re")
    before = real_shell_scenario.snapshots.capture(field, label="before-tab")
    route = real_shell_scenario.input.press_key(field, Qt.Key.Key_Tab, text="\t")
    after = real_shell_scenario.snapshots.capture(field, label="after-tab")
    violations = _transition_violations("tab", before=before, after=after)

    if violations or route.inserted_text == "\t":
        artifact = real_shell_scenario.artifacts.save(
            "tab-inserted-literal-tab",
            before=before,
            after=after,
            invariant="Tab with active autocomplete must not insert a literal tab.",
            observed=f"violations={violations}; source after Tab was {after.source_text!r}",
        )
        pytest.fail(f"prompt editor invariant failed; artifacts: {artifact}")

    assert "\t" not in after.source_text
    assert after.source_text.startswith("re:zero kara hajimeru isekai seikatsu")


def test_real_shell_plain_tab_does_not_insert_literal_tab(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Consume plain Tab without mutating prompt source text."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    before = real_shell_scenario.snapshots.capture(field, label="before-plain-tab")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Tab, text="\t")
    after = real_shell_scenario.snapshots.capture(field, label="after-plain-tab")
    violations = _transition_violations("tab", before=before, after=after)

    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "plain-tab-inserted-literal-tab",
            before=before,
            after=after,
            invariant="Plain Tab must not insert a literal tab into prompt source.",
            observed=f"violations={violations}; source after Tab was {after.source_text!r}",
        )
        pytest.fail(f"plain Tab inserted a literal tab; artifacts: {artifact}")

    assert after.source_text == before.source_text


def test_real_shell_plain_escape_does_not_insert_control_character(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Consume plain Escape without mutating prompt source text."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    before = real_shell_scenario.snapshots.capture(field, label="before-plain-escape")
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Escape)
    after = real_shell_scenario.snapshots.capture(field, label="after-plain-escape")
    violations = _transition_violations("escape", before=before, after=after)

    if violations:
        artifact = real_shell_scenario.artifacts.save(
            "plain-escape-inserted-control-character",
            before=before,
            after=after,
            invariant="Plain Escape must not insert a control character.",
            observed=f"violations={violations}; source after Escape was {after.source_text!r}",
        )
        pytest.fail(f"plain Escape inserted a control character; artifacts: {artifact}")

    assert after.source_text == before.source_text


def _transition_violations(
    action_name: str,
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Evaluate a key transition through the production snapshot invariants."""

    return transition_violations(
        action_name=action_name,
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )
