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

"""Coordinate workspace generation button flows from the shell layer."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import app_text

from dataclasses import dataclass
from typing import Callable

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
    GenerationRunStarted,
    GenerationService,
)
from substitute.application.generation.job_queue_service import (
    GenerationJobQueueService,
    GenerationQueueBatchEntry,
)
from substitute.application.ports import (
    GenerationExecutionTiming,
    InterruptResult,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.errors import (
    ErrorReport,
    SubstituteOperationContext,
    build_comfy_connection_error_report,
    build_substitute_exception_report,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

WorkflowId = str
_LOGGER = get_logger("presentation.shell.workspace_generation_controller")


class GenerationPreflightError(RuntimeError):
    """Signal that presentation preflight blocked generation before request build."""

    def __init__(
        self,
        *,
        workflow_id: WorkflowId,
        message: str,
        error_report: ErrorReport | None = None,
        report_error: bool = True,
    ) -> None:
        """Capture workflow context for generation failure routing."""

        super().__init__(message)
        self.workflow_id = workflow_id
        self.error_report = error_report
        self.report_error = report_error


@dataclass(frozen=True)
class GenerationUiBindings:
    """Bundle shell callbacks required by generation-service orchestration."""

    build_generation_request: Callable[[], GenerationRequest]
    randomize_seeds: Callable[[], None]
    clear_output_for_workflow: Callable[[WorkflowId], None]
    on_progress: Callable[[ProgressUpdate], None]
    on_model_load_progress: Callable[[ModelLoadProgressUpdate], None]
    on_preview: Callable[[PreviewImageUpdate], None]
    on_output_image: Callable[[OutputImageUpdate], None]
    on_failure: Callable[[GenerationFailure], None]
    on_timing: Callable[[GenerationExecutionTiming], None]
    on_completed: Callable[[ListenerCompleted], None]
    refresh_generation_actions: Callable[[], None]
    on_run_started: Callable[[GenerationRunStarted], None] | None = None
    effective_batch_count: Callable[[], int] | None = None
    build_queued_generation_snapshots: (
        Callable[[], tuple[GenerationJobSnapshot, ...]] | None
    ) = None
    capture_queued_generation_preparation: (
        Callable[[], "QueuedGenerationPreparationJob"] | None
    ) = None


@dataclass(frozen=True)
class QueuedGenerationPreparationJob:
    """Carry a detached queue preparation job and main-thread completion hook."""

    prepare_snapshots: Callable[[], GenerationPreparationResult]
    on_prepared: Callable[
        [GenerationPreparationResult], tuple[GenerationJobSnapshot, ...]
    ]


class GenerationPreparationExecutor:
    """Run captured generation preparation jobs off the UI thread."""

    def __init__(
        self,
        submitter: TaskSubmitter | None = None,
        *,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Store the preparation execution route."""

        if submitter is None:
            raise TypeError("submitter is required for generation preparation.")
        self._task_scope = TaskScope(
            submitter=submitter,
            scope_id="generation_preparation",
        )
        self._close_submitter = close_submitter or (lambda: None)
        self._closed = False
        self._next_token = 0
        self._callbacks_by_token: dict[
            int,
            tuple[
                Callable[[GenerationPreparationResult], None],
                Callable[[BaseException], None],
            ],
        ] = {}

    def close(self) -> None:
        """Close the owned execution route when the controller is disposed."""

        if self._closed:
            return
        self._closed = True
        self._callbacks_by_token.clear()
        self._task_scope.close(reason="generation_preparation_executor_closed")
        self._close_submitter()

    def submit(
        self,
        *,
        prepare_snapshots: Callable[[], GenerationPreparationResult],
        on_completed: Callable[[GenerationPreparationResult], None],
        on_failed: Callable[[BaseException], None],
    ) -> None:
        """Submit one detached preparation job and return immediately."""

        if self._closed:
            raise RuntimeError("Generation preparation executor is closed.")
        self._next_token += 1
        token = self._next_token
        self._callbacks_by_token[token] = (on_completed, on_failed)
        request: TaskRequest[GenerationPreparationResult] = TaskRequest(
            identity=TaskIdentity(
                request_id=token,
                domain="generation_preparation",
            ),
            context=ExecutionContext(
                operation="generation_preparation",
                reason="queue_generation_snapshots",
                lane="generation_preparation",
                safe_fields=(("request_id", token),),
            ),
            work=lambda _token: prepare_snapshots(),
        )
        try:
            handle = self._task_scope.submit(request)
        except BaseException:
            self._callbacks_by_token.pop(token, None)
            raise
        handle.add_done_callback(
            lambda outcome: self._handle_completed(token, outcome),
            reason="generation_preparation_completed",
        )

    def _handle_completed(
        self,
        token: int,
        outcome: TaskOutcome[GenerationPreparationResult],
    ) -> None:
        """Run the success callback on the bridge owner thread."""

        callbacks = self._callbacks_by_token.pop(token, None)
        if callbacks is None:
            return
        on_completed, on_failed = callbacks
        if outcome.status == "succeeded" and outcome.result is not None:
            on_completed(outcome.result)
            return
        if outcome.status == "cancelled":
            on_failed(
                RuntimeError(
                    outcome.cancellation_reason or "Generation preparation cancelled."
                )
            )
            return
        on_failed(outcome.error or RuntimeError("Generation preparation failed."))


class WorkspaceGenerationController:
    """Own generation-button and interrupt orchestration for the workspace shell."""

    def __init__(
        self,
        generation_service: GenerationService,
        job_queue_service: GenerationJobQueueService | None = None,
        preparation_executor: GenerationPreparationExecutor | None = None,
    ) -> None:
        """Store the application generation service dependency."""

        self._generation_service = generation_service
        self._job_queue_service = job_queue_service
        self._preparation_executor = (
            preparation_executor or _MissingGenerationPreparationExecutor()
        )
        self._continuous_active = False
        self._backend_available = True
        self._backend_unavailable_message: ApplicationText = app_text(
            "ComfyUI is still starting."
        )

    def close(self) -> None:
        """Close generation controller execution resources."""

        close = getattr(self._preparation_executor, "close", None)
        if callable(close):
            close()

    @property
    def is_continuous_active(self) -> bool:
        """Return whether the continuous-generation loop is currently active."""

        return self._continuous_active

    def set_backend_available(
        self, available: bool, *, message: ApplicationText
    ) -> None:
        """Set whether generation may be dispatched to the Comfy backend."""

        self._backend_available = available
        self._backend_unavailable_message = message

    def handle_generate_clicked(
        self,
        *,
        current_mode: str,
        bindings: GenerationUiBindings,
    ) -> None:
        """Handle generate-button clicks for single and continuous modes."""

        self._handle_generate_clicked_profiled(
            current_mode=current_mode,
            bindings=bindings,
        )

    def _handle_generate_clicked_profiled(
        self,
        *,
        current_mode: str,
        bindings: GenerationUiBindings,
    ) -> None:
        """Run generate-button behavior after top-level routing."""

        if current_mode == "continuous":
            if not self._continuous_active:
                if not self._backend_available:
                    self._report_backend_unavailable(bindings)
                    return
                self._start_continuous_generation(bindings)
            else:
                self.stop_continuous_generation(bindings=bindings)
            return

        if not self._backend_available:
            self._report_backend_unavailable(bindings)
            return

        callbacks = self._build_generation_callbacks(bindings)
        if self._job_queue_service is not None:
            batch_count = self._effective_batch_count(bindings)
            if bindings.capture_queued_generation_preparation is not None:
                self._submit_queued_generation_preparation_batches(
                    bindings=bindings,
                    callbacks=callbacks,
                    batch_count=batch_count,
                    operation="queue_generation",
                )
                return
            for _batch_index in range(batch_count):
                try:
                    snapshots = self._build_queued_generation_snapshots(bindings)
                except GenerationPreflightError as error:
                    callbacks.on_failure(
                        generation_preflight_failure(
                            error,
                            operation="queue_generation",
                        )
                    )
                    return
                self._enqueue_snapshot_entry_batch(
                    tuple(
                        GenerationQueueBatchEntry(
                            snapshot=snapshot,
                            callbacks=callbacks,
                        )
                        for snapshot in snapshots
                    ),
                )
            return

        try:
            request = bindings.build_generation_request()
        except GenerationPreflightError as error:
            callbacks.on_failure(
                generation_preflight_failure(
                    error,
                    operation="generate",
                )
            )
            return
        self._generation_service.run_single_generation(
            request=request,
            callbacks=callbacks,
        )

    def stop_continuous_generation(self, *, bindings: GenerationUiBindings) -> None:
        """Stop continuous generation and restore button state."""

        self._continuous_active = False
        bindings.refresh_generation_actions()
        log_info(_LOGGER, "Continuous generation stop requested")

    def skip_active_queue_job(
        self,
        *,
        bindings: GenerationUiBindings | None = None,
    ) -> None:
        """Skip the active queued generation job when queueing is enabled."""

        if self._job_queue_service is None:
            return
        self._job_queue_service.skip_active_job()
        if bindings is not None:
            self._recover_continuous_generation_after_skip(bindings)
            bindings.refresh_generation_actions()

    def cancel_generation_queue(
        self,
        *,
        bindings: GenerationUiBindings | None = None,
    ) -> InterruptResult | None:
        """Cancel queued generation work and stop active continuous requeue."""

        if self._continuous_active:
            self._continuous_active = False
            log_info(_LOGGER, "Continuous generation stopped before queue cancellation")
        if bindings is not None:
            bindings.refresh_generation_actions()
        if self._job_queue_service is not None:
            self._job_queue_service.cancel_all_jobs()
            return None
        return self._generation_service.interrupt_generation()

    def interrupt_generation(self) -> InterruptResult:
        """Delegate interrupt requests to the application generation service."""

        return self._generation_service.interrupt_generation()

    @staticmethod
    def _build_generation_callbacks(
        bindings: GenerationUiBindings,
    ) -> GenerationCallbacks:
        """Build callback bridge for generation progress, preview, output, and failure."""

        return GenerationCallbacks(
            randomize_seeds=bindings.randomize_seeds,
            clear_output=bindings.clear_output_for_workflow,
            on_run_started=bindings.on_run_started,
            on_progress=bindings.on_progress,
            on_model_load_progress=bindings.on_model_load_progress,
            on_preview=bindings.on_preview,
            on_output_image=bindings.on_output_image,
            on_failure=bindings.on_failure,
            on_timing=bindings.on_timing,
            on_completed=bindings.on_completed,
        )

    @staticmethod
    def _effective_batch_count(bindings: GenerationUiBindings) -> int:
        """Return a clamped normal-generation batch count from UI bindings."""

        if bindings.effective_batch_count is None:
            return 1
        return max(1, int(bindings.effective_batch_count()))

    def _start_continuous_generation(self, bindings: GenerationUiBindings) -> None:
        """Start continuous generation by enqueueing the first snapshot cycle."""

        if self._job_queue_service is None:
            failure = generation_preflight_failure(
                GenerationPreflightError(
                    workflow_id="queue",
                    message=app_text(
                        "Continuous generation requires the generation queue."
                    ),
                ),
                operation="continuous_generation",
            )
            bindings.on_failure(failure)
            return

        self._continuous_active = True
        bindings.refresh_generation_actions()
        log_info(_LOGGER, "Continuous generation start accepted")
        try:
            if bindings.capture_queued_generation_preparation is not None:
                self._submit_queued_generation_preparation_batches(
                    bindings=bindings,
                    callbacks=None,
                    batch_count=1,
                    operation="continuous_generation",
                    continuous=True,
                )
            else:
                self._enqueue_next_continuous_snapshot(bindings)
        except GenerationPreflightError as error:
            self._stop_continuous_after_terminal_failure(bindings)
            log_warning(
                _LOGGER,
                "Continuous generation enqueue cycle failed during preflight",
                workflow_id=error.workflow_id,
                failure_message=str(error),
            )
            bindings.on_failure(
                generation_preflight_failure(
                    error,
                    operation="continuous_generation",
                )
            )

    def _enqueue_next_continuous_snapshot(
        self,
        bindings: GenerationUiBindings,
    ) -> None:
        """Enqueue one continuous snapshot cycle while continuous mode is active."""

        if not self._continuous_active:
            return
        if self._job_queue_service is None:
            raise GenerationPreflightError(
                workflow_id="queue",
                message=app_text(
                    "Continuous generation requires the generation queue."
                ),
            )

        snapshots = self._build_queued_generation_snapshots(bindings)
        if not snapshots:
            raise GenerationPreflightError(
                workflow_id="queue",
                message=app_text("Continuous generation prepared no jobs."),
            )
        final_snapshot_index = len(snapshots) - 1
        entries = tuple(
            GenerationQueueBatchEntry(
                snapshot=snapshot,
                callbacks=self._build_continuous_callbacks(
                    bindings,
                    requeue_on_completed=index == final_snapshot_index,
                ),
            )
            for index, snapshot in enumerate(snapshots)
        )
        self._enqueue_snapshot_entry_batch(
            entries,
        )
        for index, snapshot in enumerate(snapshots):
            log_debug(
                _LOGGER,
                "Enqueued continuous generation snapshot",
                workflow_id=snapshot.workflow_id,
                workflow_name=snapshot.workflow_name,
                cycle_position=index + 1,
                cycle_size=len(snapshots),
            )

    def _submit_queued_generation_preparation_batches(
        self,
        *,
        bindings: GenerationUiBindings,
        callbacks: GenerationCallbacks | None,
        batch_count: int,
        operation: str,
        continuous: bool = False,
    ) -> None:
        """Capture queue preparation jobs and submit them to execution."""

        if self._job_queue_service is None:
            raise GenerationPreflightError(
                workflow_id="queue",
                message=app_text("Generation queue snapshot bindings are unavailable."),
            )
        capture_preparation = bindings.capture_queued_generation_preparation
        if capture_preparation is None:
            raise GenerationPreflightError(
                workflow_id="queue",
                message=app_text(
                    "Generation queue preparation bindings are unavailable."
                ),
            )
        for batch_index in range(batch_count):
            try:
                preparation_job = capture_preparation()
            except GenerationPreflightError as error:
                self._handle_preparation_preflight_error(
                    bindings=bindings,
                    callbacks=callbacks,
                    error=error,
                    operation=operation,
                    continuous=continuous,
                )
                return

            def on_preparation_completed(
                result: GenerationPreparationResult,
                *,
                job: QueuedGenerationPreparationJob = preparation_job,
            ) -> None:
                """Enqueue one completed preparation batch on the UI thread."""

                self._enqueue_prepared_snapshots(
                    bindings=bindings,
                    callbacks=callbacks,
                    preparation_job=job,
                    result=result,
                    continuous=continuous,
                )

            def on_preparation_failed(
                error: BaseException,
            ) -> None:
                """Route one failed preparation batch on the UI thread."""

                self._handle_preparation_task_error(
                    bindings=bindings,
                    callbacks=callbacks,
                    error=error,
                    operation=operation,
                    continuous=continuous,
                )

            self._preparation_executor.submit(
                prepare_snapshots=preparation_job.prepare_snapshots,
                on_completed=on_preparation_completed,
                on_failed=on_preparation_failed,
            )

    def _enqueue_prepared_snapshots(
        self,
        *,
        bindings: GenerationUiBindings,
        callbacks: GenerationCallbacks | None,
        preparation_job: QueuedGenerationPreparationJob,
        result: GenerationPreparationResult,
        continuous: bool,
    ) -> None:
        """Enqueue task-prepared snapshots on the UI thread."""

        if self._job_queue_service is None:
            return
        snapshots = preparation_job.on_prepared(result)
        if continuous and not snapshots:
            self._stop_continuous_after_terminal_failure(bindings)
            bindings.on_failure(
                generation_preflight_failure(
                    GenerationPreflightError(
                        workflow_id="queue",
                        message=app_text("Continuous generation prepared no jobs."),
                    ),
                    operation="continuous_generation",
                )
            )
            return
        final_snapshot_index = len(snapshots) - 1
        entries = tuple(
            GenerationQueueBatchEntry(
                snapshot=snapshot,
                callbacks=self._callbacks_for_prepared_snapshot(
                    bindings=bindings,
                    callbacks=callbacks,
                    continuous=continuous,
                    requeue_on_completed=index == final_snapshot_index,
                ),
            )
            for index, snapshot in enumerate(snapshots)
        )
        self._enqueue_snapshot_entry_batch(
            entries,
        )

    def _callbacks_for_prepared_snapshot(
        self,
        *,
        bindings: GenerationUiBindings,
        callbacks: GenerationCallbacks | None,
        continuous: bool,
        requeue_on_completed: bool,
    ) -> GenerationCallbacks:
        """Return callbacks for one task-prepared snapshot entry."""

        if continuous:
            return self._build_continuous_callbacks(
                bindings,
                requeue_on_completed=requeue_on_completed,
            )
        if callbacks is not None:
            return callbacks
        return self._build_generation_callbacks(bindings)

    def _enqueue_snapshot_entry_batch(
        self,
        entries: tuple[GenerationQueueBatchEntry, ...],
    ) -> None:
        """Enqueue prepared snapshot entries through one queue transaction."""

        if self._job_queue_service is None or not entries:
            return
        self._job_queue_service.enqueue_snapshot_entries(entries)

    def _handle_preparation_preflight_error(
        self,
        *,
        bindings: GenerationUiBindings,
        callbacks: GenerationCallbacks | None,
        error: GenerationPreflightError,
        operation: str,
        continuous: bool,
    ) -> None:
        """Route preflight errors raised during main-thread capture."""

        if continuous:
            self._stop_continuous_after_terminal_failure(bindings)
        failure = generation_preflight_failure(error, operation=operation)
        if callbacks is not None:
            callbacks.on_failure(failure)
        else:
            bindings.on_failure(failure)

    def _handle_preparation_task_error(
        self,
        *,
        bindings: GenerationUiBindings,
        callbacks: GenerationCallbacks | None,
        error: BaseException,
        operation: str,
        continuous: bool,
    ) -> None:
        """Route preparation-task failures through the existing failure path."""

        if continuous:
            self._stop_continuous_after_terminal_failure(bindings)
        if isinstance(error, GenerationPreflightError):
            failure = generation_preflight_failure(error, operation=operation)
        else:
            failure = GenerationFailure(
                stage="preflight",
                workflow_id="queue",
                message=str(error),
                error_report=build_substitute_exception_report(
                    title=app_text("Generation preparation failed"),
                    message=str(error),
                    stage="preflight",
                    error=error,
                    context=SubstituteOperationContext(
                        operation=operation,
                        workflow_id="queue",
                    ),
                ),
            )
        if callbacks is not None:
            callbacks.on_failure(failure)
        else:
            bindings.on_failure(failure)

    def _build_continuous_callbacks(
        self,
        bindings: GenerationUiBindings,
        *,
        requeue_on_completed: bool,
    ) -> GenerationCallbacks:
        """Build queue callbacks for one continuous snapshot."""

        on_completed: Callable[[ListenerCompleted], None]
        if requeue_on_completed:

            def on_completed(event: ListenerCompleted) -> None:
                """Requeue after normal UI completion for the final cycle snapshot."""

                self._handle_continuous_completed(bindings, event)
        else:
            on_completed = bindings.on_completed

        return GenerationCallbacks(
            randomize_seeds=None,
            clear_output=bindings.clear_output_for_workflow,
            on_run_started=bindings.on_run_started,
            on_progress=bindings.on_progress,
            on_model_load_progress=bindings.on_model_load_progress,
            on_preview=bindings.on_preview,
            on_output_image=bindings.on_output_image,
            on_failure=lambda failure: self._handle_continuous_failure(
                bindings,
                failure,
            ),
            on_timing=bindings.on_timing,
            on_completed=on_completed,
        )

    def _handle_continuous_completed(
        self,
        bindings: GenerationUiBindings,
        event: ListenerCompleted,
    ) -> None:
        """Run normal completion handling, then enqueue the next continuous cycle."""

        bindings.on_completed(event)
        if not self._continuous_active:
            return
        try:
            if bindings.capture_queued_generation_preparation is not None:
                self._submit_queued_generation_preparation_batches(
                    bindings=bindings,
                    callbacks=None,
                    batch_count=1,
                    operation="continuous_generation",
                    continuous=True,
                )
            else:
                self._enqueue_next_continuous_snapshot(bindings)
        except GenerationPreflightError as error:
            self._stop_continuous_after_terminal_failure(bindings)
            log_warning(
                _LOGGER,
                "Continuous generation enqueue cycle failed during preflight",
                workflow_id=error.workflow_id,
                failure_message=str(error),
            )
            bindings.on_failure(
                generation_preflight_failure(
                    error,
                    operation="continuous_generation",
                )
            )

    def _handle_continuous_failure(
        self,
        bindings: GenerationUiBindings,
        failure: GenerationFailure,
    ) -> None:
        """Report a terminal continuous failure and stop the loop."""

        bindings.on_failure(failure)
        self._stop_continuous_after_terminal_failure(bindings)
        log_warning(
            _LOGGER,
            "Continuous terminal failure stopped the loop",
            workflow_id=failure.workflow_id,
            stage=failure.stage,
            failure_message=failure.message,
        )

    def _stop_continuous_after_terminal_failure(
        self,
        bindings: GenerationUiBindings,
    ) -> None:
        """Stop continuous mode after a failure path and restore button mode."""

        self._continuous_active = False
        bindings.refresh_generation_actions()

    def _recover_continuous_generation_after_skip(
        self,
        bindings: GenerationUiBindings,
    ) -> None:
        """Continue continuous generation when skip emptied the active cycle."""

        if not self._continuous_active or self._job_queue_service is None:
            return
        if self._job_queue_service.has_cancellable_jobs():
            return
        try:
            self._enqueue_next_continuous_snapshot(bindings)
        except GenerationPreflightError as error:
            self._stop_continuous_after_terminal_failure(bindings)
            log_warning(
                _LOGGER,
                "Continuous generation skip recovery failed during preflight",
                workflow_id=error.workflow_id,
                failure_message=str(error),
            )
            bindings.on_failure(
                generation_preflight_failure(
                    error,
                    operation="continuous_generation",
                )
            )

    def _report_backend_unavailable(self, bindings: GenerationUiBindings) -> None:
        """Route a backend-starting preflight failure through normal UI callbacks."""

        bindings.on_failure(
            GenerationFailure(
                stage="preflight",
                workflow_id="backend",
                message=self._backend_unavailable_message,
                error_report=build_comfy_connection_error_report(
                    title=app_text("Comfy is unavailable"),
                    message=self._backend_unavailable_message,
                    stage="preflight",
                    context=SubstituteOperationContext(
                        operation="start_generation",
                        workflow_id="backend",
                        values={"backend_available": False},
                    ),
                ),
            )
        )

    @staticmethod
    def _build_queued_generation_snapshots(
        bindings: GenerationUiBindings,
    ) -> tuple[GenerationJobSnapshot, ...]:
        """Build queued generation snapshots through explicit UI bindings."""

        if bindings.build_queued_generation_snapshots is None:
            raise GenerationPreflightError(
                workflow_id="queue",
                message=app_text("Generation queue snapshot bindings are unavailable."),
            )
        return bindings.build_queued_generation_snapshots()


def generation_preflight_failure(
    error: GenerationPreflightError,
    *,
    operation: str,
    values: dict[str, object] | None = None,
) -> GenerationFailure:
    """Return a generation failure carrying a Substitute preflight report."""

    error_report = error.error_report
    if error_report is None and error.report_error:
        error_report = build_substitute_exception_report(
            title=app_text("Generation preflight failed"),
            message=str(error),
            stage="preflight",
            error=error,
            context=SubstituteOperationContext(
                operation=operation,
                workflow_id=error.workflow_id,
                values=values or {},
            ),
        )
    return GenerationFailure(
        stage="preflight",
        workflow_id=error.workflow_id,
        message=str(error),
        error_report=error_report,
    )


class _MissingGenerationPreparationExecutor:
    """Reject async generation preparation when composition omitted the executor."""

    def close(self) -> None:
        """Close the missing executor sentinel."""

    def submit(
        self,
        *,
        prepare_snapshots: Callable[[], GenerationPreparationResult],
        on_completed: Callable[[GenerationPreparationResult], None],
        on_failed: Callable[[BaseException], None],
    ) -> None:
        """Reject detached preparation without hidden execution fallback."""

        _ = prepare_snapshots, on_completed, on_failed
        raise RuntimeError("preparation_executor is required for generation.")


__all__ = [
    "GenerationPreparationExecutor",
    "GenerationUiBindings",
    "GenerationPreflightError",
    "QueuedGenerationPreparationJob",
    "WorkspaceGenerationController",
    "WorkflowId",
    "generation_preflight_failure",
]
