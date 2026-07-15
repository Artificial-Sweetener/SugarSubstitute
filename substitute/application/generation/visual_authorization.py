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

"""Authorize generation visuals before they can mutate canvas state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.application.ports import GenerationVisualIdentity


class VisualRunState(StrEnum):
    """Describe the lifecycle state used for visual-event authorization."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class AcceptedVisualRun:
    """Capture one prompt-bound run accepted for visual routing."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    state: VisualRunState = VisualRunState.RUNNING


@dataclass(slots=True)
class VisualAuthorizationService:
    """Own run acceptance rules for previews and final generated images."""

    _runs: dict[tuple[str, str], AcceptedVisualRun]
    _active_run_by_workflow: dict[str, str]

    def __init__(self) -> None:
        """Initialize empty in-memory authorization state."""

        self._runs = {}
        self._active_run_by_workflow = {}

    def register_run(
        self,
        *,
        workflow_id: str,
        generation_run_id: str,
        prompt_id: str,
        client_id: str,
    ) -> None:
        """Accept one run and supersede older active runs for the workflow."""

        previous_run_id = self._active_run_by_workflow.get(workflow_id)
        if previous_run_id is not None and previous_run_id != generation_run_id:
            self._transition_run(
                workflow_id=workflow_id,
                generation_run_id=previous_run_id,
                state=VisualRunState.SUPERSEDED,
            )
        self._runs[(workflow_id, generation_run_id)] = AcceptedVisualRun(
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
            state=VisualRunState.RUNNING,
        )
        self._active_run_by_workflow[workflow_id] = generation_run_id

    def complete_run(
        self,
        *,
        workflow_id: str,
        generation_run_id: str,
        prompt_id: str,
    ) -> None:
        """Mark one active run completed while keeping final commit authorization."""

        run = self._runs.get((workflow_id, generation_run_id))
        if run is None or run.prompt_id != prompt_id:
            return
        self._runs[(workflow_id, generation_run_id)] = AcceptedVisualRun(
            workflow_id=run.workflow_id,
            generation_run_id=run.generation_run_id,
            prompt_id=run.prompt_id,
            client_id=run.client_id,
            state=VisualRunState.COMPLETED,
        )

    def fail_run(
        self,
        *,
        workflow_id: str,
        generation_run_id: str,
    ) -> None:
        """Reject future visuals for a failed or cancelled run."""

        self._transition_run(
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            state=VisualRunState.FAILED,
        )

    def authorize_preview(self, identity: GenerationVisualIdentity) -> bool:
        """Return whether a preview may be displayed for the active workflow run."""

        run = self._matching_run(identity)
        if run is None:
            return False
        return (
            run.state is VisualRunState.RUNNING
            and self._active_run_by_workflow.get(identity.workflow_id)
            == identity.generation_run_id
        )

    def authorize_final_output(self, identity: GenerationVisualIdentity) -> bool:
        """Return whether a final output may register into workflow state."""

        run = self._matching_run(identity)
        if run is None:
            return False
        return run.state in {VisualRunState.RUNNING, VisualRunState.COMPLETED}

    def _matching_run(
        self,
        identity: GenerationVisualIdentity,
    ) -> AcceptedVisualRun | None:
        """Return the stored run when all required identity fields match."""

        run = self._runs.get((identity.workflow_id, identity.generation_run_id))
        if run is None:
            return None
        if run.prompt_id != identity.prompt_id or run.client_id != identity.client_id:
            return None
        if not identity.source_key or not identity.source_label:
            return None
        return run

    def _transition_run(
        self,
        *,
        workflow_id: str,
        generation_run_id: str,
        state: VisualRunState,
    ) -> None:
        """Set a terminal run state when the run is still known."""

        run = self._runs.get((workflow_id, generation_run_id))
        if run is None:
            return
        self._runs[(workflow_id, generation_run_id)] = AcceptedVisualRun(
            workflow_id=run.workflow_id,
            generation_run_id=run.generation_run_id,
            prompt_id=run.prompt_id,
            client_id=run.client_id,
            state=state,
        )
        if self._active_run_by_workflow.get(workflow_id) == generation_run_id:
            self._active_run_by_workflow.pop(workflow_id, None)


__all__ = [
    "AcceptedVisualRun",
    "VisualAuthorizationService",
    "VisualRunState",
]
