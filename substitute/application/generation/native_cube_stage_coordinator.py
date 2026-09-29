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

"""Advance disconnected native Cubes through one ordered user run."""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4

from substitute.application.generation.generation_execution_dispatcher import (
    GenerationExecutionDispatcher,
)
from substitute.application.generation.generation_models import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationStartResult,
    PreparedGenerationRequest,
)
from substitute.application.ports.comfy_gateway import ListenerCompleted, OutputSavePlan


@dataclass(slots=True)
class _StageRun:
    """Track the active Comfy prompt and frozen stage plan for one run."""

    request: PreparedGenerationRequest
    workflow_payload: dict[str, object]
    output_save_plan: OutputSavePlan
    callbacks: GenerationCallbacks
    stages: tuple[tuple[str, ...], ...]
    generation_run_id: str
    stage_index: int = 0
    prompt_id: str | None = None
    cancelled: bool = False
    advancement_requested: bool = False


class NativeCubeStageCoordinator:
    """Queue the next independent Cube only after the prior stage finishes."""

    def __init__(self, dispatcher: GenerationExecutionDispatcher) -> None:
        """Use the existing queue and listener owner for each Comfy prompt."""

        self._dispatcher = dispatcher
        self._active_runs: dict[str, _StageRun] = {}

    def dispatch(
        self,
        *,
        request: PreparedGenerationRequest,
        workflow_payload: dict[str, object],
        output_save_plan: OutputSavePlan,
        callbacks: GenerationCallbacks,
        stages: tuple[tuple[str, ...], ...],
    ) -> GenerationStartResult:
        """Start a frozen sequence while retaining one user-run identity."""

        if len(stages) < 2:
            return self._dispatcher.dispatch(
                request=request,
                workflow_payload=workflow_payload,
                output_save_plan=output_save_plan,
                callbacks=callbacks,
                native_cube_execution=True,
            )
        run = _StageRun(
            request=request,
            workflow_payload=workflow_payload,
            output_save_plan=output_save_plan,
            callbacks=callbacks,
            stages=stages,
            generation_run_id=uuid4().hex,
        )
        self._active_runs[run.generation_run_id] = run
        return self._dispatch_stage(run)

    def cancel_active_runs(self) -> None:
        """Prevent queued stage transitions after a user interruption."""

        for run in self._active_runs.values():
            run.cancelled = True
        self._active_runs.clear()

    def _dispatch_stage(self, run: _StageRun) -> GenerationStartResult:
        """Queue the current stage and attach completion-driven advancement."""

        stage_index = run.stage_index

        def on_failure(failure: GenerationFailure) -> None:
            """Retire a failed sequence without queueing successor Cubes."""

            self._active_runs.pop(run.generation_run_id, None)
            run.callbacks.on_failure(failure)

        def on_completed(event: ListenerCompleted) -> None:
            """Advance only once for the accepted stage prompt."""

            if (
                run.cancelled
                or run.stage_index != stage_index
                or run.prompt_id != event.prompt_id
                or run.advancement_requested
            ):
                return
            run.advancement_requested = True
            if stage_index == len(run.stages) - 1:
                self._active_runs.pop(run.generation_run_id, None)
                if run.callbacks.on_completed is not None:
                    run.callbacks.on_completed(event)
                return

            def advance() -> None:
                """Request the next stage after queue-state validation."""

                self._advance(run, stage_index)

            if run.callbacks.request_stage_advance is None:
                advance()
            else:
                run.callbacks.request_stage_advance(advance)

        stage_callbacks = replace(
            run.callbacks,
            on_failure=on_failure,
            on_completed=on_completed,
        )
        result = self._dispatcher.dispatch(
            request=run.request,
            workflow_payload=run.workflow_payload,
            output_save_plan=run.output_save_plan,
            callbacks=stage_callbacks,
            native_cube_execution=True,
            execution_targets=run.stages[stage_index],
            generation_run_id=run.generation_run_id,
        )
        run.prompt_id = result.prompt_id
        if not result.started:
            self._active_runs.pop(run.generation_run_id, None)
        return result

    def _advance(self, run: _StageRun, completed_index: int) -> None:
        """Transition a live run after the queue owner approves advancement."""

        if run.cancelled or run.stage_index != completed_index:
            return
        run.stage_index += 1
        run.advancement_requested = False
        self._dispatch_stage(run)


__all__ = ["NativeCubeStageCoordinator"]
