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

"""Manage workflow session state transitions for presentation callers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, cast

from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger

WorkflowT = TypeVar("WorkflowT")
_LOGGER = get_logger("application.workflows.workflow_session_service")


@dataclass(frozen=True)
class WorkflowActivationTransition:
    """Describe an active-workflow context switch."""

    previous_workflow_id: str
    new_workflow_id: str
    active_changed: bool


@dataclass(frozen=True)
class WorkflowCreationTransition(Generic[WorkflowT]):
    """Describe a workflow creation and optional activation."""

    workflow_id: str
    workflow: WorkflowT
    previous_active_workflow_id: str
    active_changed: bool


@dataclass(frozen=True)
class WorkflowCloseTransition(Generic[WorkflowT]):
    """Describe a workflow close and selected successor workflow."""

    closed_workflow_id: str
    previous_active_workflow_id: str
    next_active_workflow_id: str | None
    active_changed: bool
    removed_workflow: WorkflowT | None


@dataclass(frozen=True)
class WorkflowRenameTransition:
    """Describe a workflow id rename and active-id outcome."""

    old_workflow_id: str
    new_workflow_id: str
    active_changed: bool


@dataclass
class WorkflowSessionState(Generic[WorkflowT]):
    """Store mutable workflow-session state for a single desktop session."""

    workflows: dict[str, WorkflowT]
    active_workflow_id: str


class WorkflowSessionService(Generic[WorkflowT]):
    """Own workflow map and active-workflow transitions without UI dependencies."""

    def __init__(
        self,
        workflow_factory: Callable[[], WorkflowT] | None = None,
        *,
        default_workflow_id: str = "main",
    ) -> None:
        """Initialize session with one default workflow and active workflow id."""
        resolved_factory: Callable[[], WorkflowT]
        if workflow_factory is None:
            resolved_factory = cast(Callable[[], WorkflowT], WorkflowState)
        else:
            resolved_factory = workflow_factory
        initial_workflow = resolved_factory()
        self._workflow_factory = resolved_factory
        self._state = WorkflowSessionState(
            workflows={default_workflow_id: initial_workflow},
            active_workflow_id=default_workflow_id,
        )

    @property
    def workflows(self) -> dict[str, WorkflowT]:
        """Return mutable mapping of workflow id to workflow state."""
        return self._state.workflows

    @property
    def active_workflow_id(self) -> str:
        """Return current active workflow id."""
        return self._state.active_workflow_id

    def get_workflow(self, workflow_id: str) -> WorkflowT | None:
        """Return workflow state for id when present."""
        return self._state.workflows.get(workflow_id)

    def get_active_workflow(self) -> WorkflowT:
        """Return active workflow state or raise KeyError if session is invalid."""
        return self._state.workflows[self._state.active_workflow_id]

    def add_workflow(
        self,
        workflow_id: str,
        *,
        activate: bool = False,
    ) -> WorkflowCreationTransition[WorkflowT]:
        """Create and register workflow id, optionally activating it."""
        if workflow_id in self._state.workflows:
            raise ValueError(f"Workflow id '{workflow_id}' already exists.")
        previous = self._state.active_workflow_id
        workflow = self._workflow_factory()
        self._state.workflows[workflow_id] = workflow
        if activate:
            self._state.active_workflow_id = workflow_id
        return WorkflowCreationTransition(
            workflow_id=workflow_id,
            workflow=workflow,
            previous_active_workflow_id=previous,
            active_changed=activate and previous != workflow_id,
        )

    def add_existing_workflow(
        self,
        workflow_id: str,
        workflow: WorkflowT,
        *,
        activate: bool = False,
    ) -> WorkflowCreationTransition[WorkflowT]:
        """Register an existing workflow state, optionally activating it."""

        if workflow_id in self._state.workflows:
            raise ValueError(f"Workflow id '{workflow_id}' already exists.")
        previous = self._state.active_workflow_id
        self._state.workflows[workflow_id] = workflow
        if activate:
            self._state.active_workflow_id = workflow_id
        return WorkflowCreationTransition(
            workflow_id=workflow_id,
            workflow=workflow,
            previous_active_workflow_id=previous,
            active_changed=activate and previous != workflow_id,
        )

    def replace_workflows(
        self,
        workflows: dict[str, WorkflowT],
        *,
        active_workflow_id: str,
    ) -> None:
        """Replace the full workflow map during trusted session restoration."""

        if active_workflow_id and active_workflow_id not in workflows:
            raise ValueError(
                f"Active workflow id '{active_workflow_id}' does not exist."
            )
        self._state = WorkflowSessionState(
            workflows=dict(workflows),
            active_workflow_id=active_workflow_id,
        )

    def close_workflow(
        self,
        workflow_id: str,
        ordered_workflow_ids: Sequence[str],
    ) -> WorkflowCloseTransition[WorkflowT]:
        """Remove workflow id and choose the active successor from visual order."""

        previous = self._state.active_workflow_id
        removed = self._state.workflows.pop(workflow_id, None)
        next_active = self._resolve_close_successor(
            workflow_id,
            ordered_workflow_ids,
        )
        active_changed = workflow_id == previous
        if active_changed:
            self._state.active_workflow_id = next_active or ""
        return WorkflowCloseTransition(
            closed_workflow_id=workflow_id,
            previous_active_workflow_id=previous,
            next_active_workflow_id=next_active,
            active_changed=active_changed,
            removed_workflow=removed,
        )

    def rename_workflow(
        self,
        old_workflow_id: str,
        new_workflow_id: str,
    ) -> WorkflowRenameTransition | None:
        """Rename workflow id mapping and update active id when needed."""
        if old_workflow_id == new_workflow_id:
            if old_workflow_id not in self._state.workflows:
                return None
            return WorkflowRenameTransition(
                old_workflow_id=old_workflow_id,
                new_workflow_id=new_workflow_id,
                active_changed=False,
            )
        if old_workflow_id not in self._state.workflows:
            return None
        if new_workflow_id in self._state.workflows:
            raise ValueError(f"Workflow id '{new_workflow_id}' already exists.")

        self._state.workflows[new_workflow_id] = self._state.workflows.pop(
            old_workflow_id
        )
        active_changed = self._state.active_workflow_id == old_workflow_id
        if self._state.active_workflow_id == old_workflow_id:
            self._state.active_workflow_id = new_workflow_id
        return WorkflowRenameTransition(
            old_workflow_id=old_workflow_id,
            new_workflow_id=new_workflow_id,
            active_changed=active_changed,
        )

    def activate_workflow(self, workflow_id: str) -> WorkflowActivationTransition:
        """Switch active workflow id and return transition metadata."""
        if workflow_id not in self._state.workflows:
            raise KeyError(f"Workflow id '{workflow_id}' does not exist.")
        previous = self._state.active_workflow_id
        self._state.active_workflow_id = workflow_id
        transition = WorkflowActivationTransition(
            previous_workflow_id=previous,
            new_workflow_id=workflow_id,
            active_changed=previous != workflow_id,
        )
        return transition

    def _resolve_close_successor(
        self,
        workflow_id: str,
        ordered_workflow_ids: Sequence[str],
    ) -> str | None:
        """Return active close successor from visual order and remaining workflows."""

        remaining_ids = [
            candidate
            for candidate in ordered_workflow_ids
            if candidate != workflow_id and candidate in self._state.workflows
        ]
        if self._state.active_workflow_id != workflow_id:
            return self._state.active_workflow_id
        if not remaining_ids:
            return None
        try:
            closed_index = list(ordered_workflow_ids).index(workflow_id)
        except ValueError:
            return remaining_ids[-1]

        left_neighbors = [
            candidate
            for candidate in ordered_workflow_ids[:closed_index]
            if candidate in remaining_ids
        ]
        if left_neighbors:
            return left_neighbors[-1]

        right_neighbors = [
            candidate
            for candidate in ordered_workflow_ids[closed_index + 1 :]
            if candidate in remaining_ids
        ]
        if right_neighbors:
            return right_neighbors[0]
        return remaining_ids[-1]


__all__ = [
    "WorkflowActivationTransition",
    "WorkflowCloseTransition",
    "WorkflowCreationTransition",
    "WorkflowRenameTransition",
    "WorkflowSessionService",
    "WorkflowSessionState",
]
