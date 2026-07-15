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

"""Characterization tests for workflow session/tab application services."""

from __future__ import annotations

from substitute.application.workflows import (
    DEFAULT_WORKFLOW_TAB_LABEL,
    WorkflowSessionService,
    WorkflowTabService,
    is_default_workflow_tab_label,
    normalize_default_workflow_tab_label,
)
from substitute.domain.workflow import WorkflowState


def test_plan_new_workflow_tab_generates_unique_labels() -> None:
    """Planning duplicate tab labels should append stable numeric suffixes."""
    service = WorkflowTabService()

    first = service.plan_new_workflow_tab(
        base_name="Recipe",
        existing_labels=set(),
        existing_workflow_ids={"main"},
    )
    second = service.plan_new_workflow_tab(
        base_name="Recipe",
        existing_labels={"Recipe"},
        existing_workflow_ids={"main", first.workflow_id},
    )

    assert first.tab_label == "Recipe"
    assert second.tab_label == "Recipe (2)"
    assert first.workflow_id != second.workflow_id


def test_normalize_default_workflow_tab_label_updates_generated_defaults() -> None:
    """Generated blank and legacy labels should normalize to the current default."""

    assert normalize_default_workflow_tab_label("") == DEFAULT_WORKFLOW_TAB_LABEL
    assert normalize_default_workflow_tab_label("   ") == DEFAULT_WORKFLOW_TAB_LABEL
    assert (
        normalize_default_workflow_tab_label("Untitled Workflow")
        == DEFAULT_WORKFLOW_TAB_LABEL
    )
    assert (
        normalize_default_workflow_tab_label("Untitled Workflow (2)")
        == "Untitled Workflow (2)"
    )
    assert (
        normalize_default_workflow_tab_label("Untitled Recipe")
        == DEFAULT_WORKFLOW_TAB_LABEL
    )
    assert (
        normalize_default_workflow_tab_label("Untitled Recipe (2)")
        == "Untitled Workflow (2)"
    )
    assert (
        normalize_default_workflow_tab_label("Untitled Recipe Draft")
        == "Untitled Recipe Draft"
    )


def test_is_default_workflow_tab_label_matches_only_generated_labels() -> None:
    """Default-label detection should avoid rewriting user-authored custom names."""

    assert is_default_workflow_tab_label("Untitled Workflow") is True
    assert is_default_workflow_tab_label("Untitled Workflow (2)") is True
    assert is_default_workflow_tab_label("Untitled Recipe") is True
    assert is_default_workflow_tab_label("Untitled Recipe Draft") is False
    assert is_default_workflow_tab_label("My Untitled Workflow") is False


def test_close_inactive_workflow_keeps_active_workflow() -> None:
    """Closing inactive workflows should not switch active workflow context."""
    session_service = WorkflowSessionService(WorkflowState)
    transition = session_service.add_workflow("workflow_12345")

    closed = session_service.close_workflow(
        "workflow_12345",
        ["main", "workflow_12345"],
    )

    assert closed.removed_workflow is transition.workflow
    assert "workflow_12345" not in session_service.workflows
    assert session_service.active_workflow_id == "main"
    assert closed.next_active_workflow_id == "main"
    assert closed.active_changed is False


def test_add_existing_workflow_registers_provided_state_without_activation() -> None:
    """Existing workflow registration should store the caller-provided state."""

    session_service = WorkflowSessionService(WorkflowState)
    provided = WorkflowState(metadata={"title": "Duplicated Recipe"})

    transition = session_service.add_existing_workflow("wf-copy", provided)

    assert session_service.workflows["wf-copy"] is provided
    assert transition.workflow is provided
    assert transition.workflow_id == "wf-copy"
    assert transition.previous_active_workflow_id == "main"
    assert transition.active_changed is False
    assert session_service.active_workflow_id == "main"


def test_add_existing_workflow_can_activate_registered_state() -> None:
    """Existing workflow registration should preserve add-workflow transition semantics."""

    session_service = WorkflowSessionService(WorkflowState)
    provided = WorkflowState(metadata={"title": "Duplicated Recipe"})

    transition = session_service.add_existing_workflow(
        "wf-copy",
        provided,
        activate=True,
    )

    assert session_service.workflows["wf-copy"] is provided
    assert session_service.active_workflow_id == "wf-copy"
    assert transition.previous_active_workflow_id == "main"
    assert transition.active_changed is True


def test_add_existing_workflow_rejects_duplicate_id() -> None:
    """Existing workflow registration should fail closed on duplicate workflow ids."""

    session_service = WorkflowSessionService(WorkflowState)

    try:
        session_service.add_existing_workflow("main", WorkflowState())
    except ValueError as error:
        assert str(error) == "Workflow id 'main' already exists."
    else:
        raise AssertionError("Expected duplicate workflow id to raise ValueError.")


def test_activate_workflow_returns_no_change_for_current_workflow() -> None:
    """Activating the already active workflow should be an explicit no-op."""

    session_service = WorkflowSessionService(WorkflowState)

    transition = session_service.activate_workflow("main")

    assert transition.previous_workflow_id == "main"
    assert transition.new_workflow_id == "main"
    assert transition.active_changed is False


def test_close_active_workflow_selects_left_neighbor() -> None:
    """Closing active workflow should select the nearest left visual neighbor."""

    session_service = WorkflowSessionService(WorkflowState)
    session_service.add_workflow("wf-a")
    session_service.add_workflow("wf-b", activate=True)
    session_service.add_workflow("wf-c")

    transition = session_service.close_workflow(
        "wf-b", ["main", "wf-a", "wf-b", "wf-c"]
    )

    assert transition.next_active_workflow_id == "wf-a"
    assert session_service.active_workflow_id == "wf-a"
    assert transition.active_changed is True


def test_close_active_first_workflow_selects_right_neighbor() -> None:
    """Closing first active workflow should select the nearest right neighbor."""

    session_service = WorkflowSessionService(WorkflowState)
    session_service.add_workflow("wf-a")
    session_service.activate_workflow("main")

    transition = session_service.close_workflow("main", ["main", "wf-a"])

    assert transition.next_active_workflow_id == "wf-a"
    assert session_service.active_workflow_id == "wf-a"


def test_close_last_workflow_returns_no_successor() -> None:
    """Closing the only workflow should leave no active successor."""

    session_service = WorkflowSessionService(WorkflowState)

    transition = session_service.close_workflow("main", ["main"])

    assert transition.next_active_workflow_id is None
    assert session_service.active_workflow_id == ""


def test_inline_rename_invalid_name_reverts_to_old_key() -> None:
    """Invalid inline rename requests should reject and preserve old key text."""
    service = WorkflowTabService()

    decision = service.resolve_inline_rename(
        old_workflow_id="main",
        proposed_name="bad/name",
        existing_tab_keys={"main"},
        existing_workflow_ids={"main"},
    )

    assert decision.accepted is False
    assert decision.workflow_id == "main"
    assert decision.tab_label == "main"


def test_inline_rename_conflict_is_resolved_with_suffix() -> None:
    """Conflicting inline rename requests should uniquify with numeric suffix."""
    service = WorkflowTabService()

    decision = service.resolve_inline_rename(
        old_workflow_id="workflow_11111",
        proposed_name="main",
        existing_tab_keys={"main", "workflow_11111"},
        existing_workflow_ids={"main", "workflow_11111"},
    )

    assert decision.accepted is True
    assert decision.workflow_id == "main (2)"
    assert decision.tab_label == "main (2)"
