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

"""Own workflow-keyed generation progress lifecycle state."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from substitute.application.generation.generation_models import GenerationRunStarted
from substitute.application.generation.progress_service import (
    ProgressService,
    ProgressViewState,
)
from substitute.application.ports import ProgressUpdate
from substitute.shared.logging.logger import get_logger, log_debug

GenerationProgressRetirementReason = Literal[
    "completed",
    "failed",
    "cancelled",
    "skipped",
    "stopped",
    "interrupted",
    "replaced",
]

_LOGGER = get_logger("application.generation.workflow_progress_service")


@dataclass(frozen=True, slots=True)
class WorkflowProgressIdentity:
    """Identify one generation lifecycle allowed to drive workflow progress."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str


@dataclass(slots=True)
class WorkflowProgressState:
    """Store progress lifecycle and latest display state for one workflow."""

    active_identity: WorkflowProgressIdentity | None = None
    latest_view_state: ProgressViewState = field(
        default_factory=ProgressViewState.hidden
    )
    seen: bool = False
    sampler_started: bool = False
    retired_identities: set[WorkflowProgressIdentity] = field(default_factory=set)


class WorkflowProgressService:
    """Own generation progress lifecycle state per workflow."""

    def __init__(self, progress_service: ProgressService | None = None) -> None:
        """Create empty workflow progress state using the shared projector."""

        self._progress_service = progress_service or ProgressService()
        self._states_by_workflow: dict[str, WorkflowProgressState] = {}

    def register_run(self, event: GenerationRunStarted) -> ProgressViewState | None:
        """Accept one run and retire older progress for the same workflow."""

        state = self._state_for_workflow(event.workflow_id)
        previous_identity = state.active_identity
        new_identity = _identity_from_run_started(event)
        retirement: ProgressViewState | None = None
        if previous_identity is not None and previous_identity != new_identity:
            state.retired_identities.add(previous_identity)
            retirement = ProgressViewState.hidden(
                workflow_id=previous_identity.workflow_id,
                generation_run_id=previous_identity.generation_run_id,
                prompt_id=previous_identity.prompt_id,
            )
        state.active_identity = new_identity
        state.latest_view_state = ProgressViewState.hidden(
            workflow_id=event.workflow_id,
            generation_run_id=event.generation_run_id,
            prompt_id=event.prompt_id,
        )
        state.seen = False
        state.sampler_started = False
        log_debug(
            _LOGGER,
            "Workflow progress run registered",
            workflow_id=event.workflow_id,
            generation_run_id=event.generation_run_id,
            prompt_id=event.prompt_id,
            client_id=event.client_id,
            retired_previous=retirement is not None,
        )
        return retirement

    def apply_update(self, update: ProgressUpdate) -> ProgressViewState | None:
        """Apply a matching progress update to its owning workflow."""

        state = self._states_by_workflow.get(update.workflow_id)
        update_identity = _identity_from_update(update)
        if state is None:
            self._log_rejected_progress(update, reason="missing_workflow_lifecycle")
            return None
        if not self._identity_is_active(state, update_identity):
            self._log_rejected_progress(update, reason="inactive_progress_lifecycle")
            return None
        workflow_percent = (
            float(update.workflow_percent)
            if update.workflow_percent is not None
            else 0.0
        )
        view_state = self._progress_service.build_view_state(
            active=True,
            workflow_percent=workflow_percent,
            sampler_percent=update.sampler_percent,
            workflow_id=update.workflow_id,
            generation_run_id=update.generation_run_id,
            prompt_id=update.prompt_id,
        )
        state.latest_view_state = view_state
        state.seen = True
        if update.sampler_percent is not None and update.sampler_percent > 0:
            state.sampler_started = True
        return view_state

    def retire_progress(
        self,
        *,
        reason: GenerationProgressRetirementReason,
        workflow_id: str | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
        client_id: str | None = None,
    ) -> ProgressViewState | None:
        """Retire matching workflow progress and return the hidden projection."""

        if workflow_id is None:
            self.clear_all()
            return ProgressViewState.hidden()
        state = self._states_by_workflow.get(workflow_id)
        if state is None or state.active_identity is None:
            return ProgressViewState.hidden(workflow_id=workflow_id)
        identity = state.active_identity
        if not _identity_matches(
            identity,
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
        ):
            log_debug(
                _LOGGER,
                "Ignoring workflow progress retirement for non-active lifecycle",
                active_workflow_id=identity.workflow_id,
                active_generation_run_id=identity.generation_run_id,
                active_prompt_id=identity.prompt_id,
                active_client_id=identity.client_id,
                reason=reason,
                workflow_id=workflow_id,
                generation_run_id=generation_run_id,
                prompt_id=prompt_id,
                client_id=client_id,
            )
            return None
        return self._retire_identity(state, identity, reason=reason)

    def view_for_workflow(self, workflow_id: str) -> ProgressViewState:
        """Return the latest progress projection for one workflow."""

        state = self._states_by_workflow.get(workflow_id)
        if state is None:
            return ProgressViewState.hidden(workflow_id=workflow_id)
        return state.latest_view_state

    def remove_workflow(self, workflow_id: str) -> None:
        """Forget runtime progress state for a closed workflow."""

        self._states_by_workflow.pop(workflow_id, None)

    def retire_all(
        self,
        *,
        reason: GenerationProgressRetirementReason,
    ) -> tuple[ProgressViewState, ...]:
        """Retire all active workflow progress for queue-wide cancellation."""

        retired: list[ProgressViewState] = []
        for state in tuple(self._states_by_workflow.values()):
            identity = state.active_identity
            if identity is None:
                continue
            retired.append(self._retire_identity(state, identity, reason=reason))
        return tuple(retired)

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Move runtime progress state to a renamed workflow id."""

        if old_workflow_id == new_workflow_id:
            return
        state = self._states_by_workflow.pop(old_workflow_id, None)
        if state is None:
            return
        state.active_identity = (
            _identity_with_workflow(state.active_identity, new_workflow_id)
            if state.active_identity is not None
            else None
        )
        state.retired_identities = {
            _identity_with_workflow(identity, new_workflow_id)
            for identity in state.retired_identities
        }
        state.latest_view_state = _view_state_with_workflow(
            state.latest_view_state,
            new_workflow_id,
        )
        self._states_by_workflow[new_workflow_id] = state

    def clear_all(self) -> None:
        """Forget all runtime workflow progress state."""

        self._states_by_workflow.clear()

    def _state_for_workflow(self, workflow_id: str) -> WorkflowProgressState:
        """Return mutable progress state for one workflow."""

        return self._states_by_workflow.setdefault(workflow_id, WorkflowProgressState())

    @staticmethod
    def _identity_is_active(
        state: WorkflowProgressState,
        identity: WorkflowProgressIdentity,
    ) -> bool:
        """Return whether an identity may update the workflow state."""

        return (
            state.active_identity == identity
            and identity not in state.retired_identities
        )

    def _retire_identity(
        self,
        state: WorkflowProgressState,
        identity: WorkflowProgressIdentity,
        *,
        reason: GenerationProgressRetirementReason,
    ) -> ProgressViewState:
        """Mark one active identity retired and hide its workflow projection."""

        state.retired_identities.add(identity)
        state.active_identity = None
        state.seen = False
        state.sampler_started = False
        state.latest_view_state = ProgressViewState.hidden(
            workflow_id=identity.workflow_id,
            generation_run_id=identity.generation_run_id,
            prompt_id=identity.prompt_id,
        )
        log_debug(
            _LOGGER,
            "Workflow progress lifecycle retired",
            reason=reason,
            workflow_id=identity.workflow_id,
            generation_run_id=identity.generation_run_id,
            prompt_id=identity.prompt_id,
            client_id=identity.client_id,
        )
        return state.latest_view_state

    @staticmethod
    def _log_rejected_progress(update: ProgressUpdate, *, reason: str) -> None:
        """Log one rejected progress update with lifecycle context."""

        log_debug(
            _LOGGER,
            "Workflow progress update rejected",
            workflow_id=update.workflow_id,
            generation_run_id=update.generation_run_id,
            prompt_id=update.prompt_id,
            client_id=update.client_id,
            reason=reason,
        )


def _identity_from_run_started(
    event: GenerationRunStarted,
) -> WorkflowProgressIdentity:
    """Return progress identity from a run-start event."""

    return WorkflowProgressIdentity(
        workflow_id=event.workflow_id,
        generation_run_id=event.generation_run_id,
        prompt_id=event.prompt_id,
        client_id=event.client_id,
    )


def _identity_from_update(update: ProgressUpdate) -> WorkflowProgressIdentity:
    """Return progress identity from a progress update."""

    return WorkflowProgressIdentity(
        workflow_id=update.workflow_id,
        generation_run_id=update.generation_run_id,
        prompt_id=update.prompt_id,
        client_id=update.client_id,
    )


def _identity_matches(
    identity: WorkflowProgressIdentity,
    *,
    workflow_id: str | None,
    generation_run_id: str | None,
    prompt_id: str | None,
    client_id: str | None,
) -> bool:
    """Return whether identity matches all provided retirement fields."""

    return (
        (workflow_id is None or identity.workflow_id == workflow_id)
        and (
            generation_run_id is None or identity.generation_run_id == generation_run_id
        )
        and (prompt_id is None or identity.prompt_id == prompt_id)
        and (client_id is None or identity.client_id == client_id)
    )


def _identity_with_workflow(
    identity: WorkflowProgressIdentity,
    workflow_id: str,
) -> WorkflowProgressIdentity:
    """Return identity moved to a new workflow id."""

    return replace(identity, workflow_id=workflow_id)


def _view_state_with_workflow(
    view_state: ProgressViewState,
    workflow_id: str,
) -> ProgressViewState:
    """Return progress view moved to a new workflow id."""

    return replace(view_state, workflow_id=workflow_id)


__all__ = [
    "GenerationProgressRetirementReason",
    "WorkflowProgressIdentity",
    "WorkflowProgressService",
    "WorkflowProgressState",
]
