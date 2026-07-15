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

"""Build generation action bindings from shell collaborators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from substitute.application.generation import (
    GenerationJobSnapshot,
    GenerationRequest,
    SeedRandomizationResult,
    SeedRandomizationService,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)
from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
)
from substitute.presentation.shell.workspace_generation_request_builder import (
    active_behavior_snapshot,
)
from substitute.presentation.shell.workspace_ports import (
    GenerationActionRefreshProtocol,
    GenerationFeedbackDispatcherProtocol,
    GenerationInterruptFailurePresenterProtocol,
    GenerationQueueProgressState,
    WorkspaceGenerationControllerProtocol,
    WorkflowSessionState,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.shell.workspace_generation_action_adapter")


class GenerationActionBindingView(Protocol):
    """Describe shell collaborators needed to build generation bindings."""

    workflow_session_service: WorkflowSessionState
    generation_feedback_dispatcher: GenerationFeedbackDispatcherProtocol
    generation_action_controller: GenerationActionRefreshProtocol


class GenerationActionIntentView(Protocol):
    """Describe shell collaborators needed for generation button intents."""

    _current_generate_mode: str
    workspace_generation_controller: WorkspaceGenerationControllerProtocol
    generation_feedback_dispatcher: GenerationFeedbackDispatcherProtocol
    generation_action_controller: GenerationActionRefreshProtocol
    generation_interrupt_failure_presenter: GenerationInterruptFailurePresenterProtocol
    generation_job_queue_service: object


class GenerationRequestSeedRandomizer(Protocol):
    """Randomize live workflow seeds before request serialization."""

    def __call__(
        self,
        *,
        request: GenerationRequest,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> SeedRandomizationResult:
        """Apply seed randomization to one generation request."""


class SeedRandomizationServiceProtocol(Protocol):
    """Describe workflow seed-randomization service behavior."""

    def randomize_workflow_seeds(
        self,
        *,
        workflow: Any,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> SeedRandomizationResult:
        """Randomize eligible seeds in one workflow."""


class WorkspaceGenerationActions:
    """Own shell generation button intents for host-facing wiring."""

    def __init__(
        self,
        view: GenerationActionIntentView,
        *,
        build_generation_bindings: Callable[[], GenerationUiBindings],
    ) -> None:
        """Store generation collaborators required by action intents."""

        self._view = view
        self._build_generation_bindings = build_generation_bindings

    def on_generate_clicked(self) -> None:
        """Handle Generate and Continuous button clicks."""

        handle_generate_clicked(
            view=self._view,
            build_generation_bindings=self._build_generation_bindings,
        )

    def on_interrupt_clicked(self) -> None:
        """Interrupt active generation."""

        handle_interrupt_clicked(view=self._view)

    def on_skip_generation_clicked(self) -> None:
        """Skip the active queued generation job."""

        handle_skip_generation_clicked(
            view=self._view,
            build_generation_bindings=self._build_generation_bindings,
        )

    def on_stop_generation_clicked(self) -> None:
        """Cancel queued generation work and stop active continuous generation."""

        handle_stop_generation_clicked(
            view=self._view,
            build_generation_bindings=self._build_generation_bindings,
        )


def build_generation_action_bindings(
    *,
    view: GenerationActionBindingView,
    build_generation_request: Callable[[], GenerationRequest],
    randomize_generation_request_seeds: GenerationRequestSeedRandomizer,
    build_queued_generation_snapshots: Callable[[], tuple[GenerationJobSnapshot, ...]],
    capture_queued_generation_preparation: Callable[[], object],
) -> GenerationUiBindings:
    """Build shell callbacks required by generation-service orchestration."""

    feedback = view.generation_feedback_dispatcher

    def build_generation_request_with_randomized_seeds() -> GenerationRequest:
        """Build a request and randomize model-owned seeds before serialization."""

        request = build_generation_request()
        randomize_generation_request_seeds(
            request=request,
            behavior_snapshot=active_behavior_snapshot(view, request.workflow_id),
        )
        return request

    return GenerationUiBindings(
        build_generation_request=build_generation_request_with_randomized_seeds,
        randomize_seeds=lambda: None,
        clear_output_for_workflow=(
            generation_feedback_presenter_for(view).request_clear_output_for_workflow
        ),
        on_run_started=feedback.on_run_started,
        on_progress=feedback.on_progress,
        on_model_load_progress=feedback.on_model_load_progress,
        on_preview=feedback.on_preview,
        on_output_image=feedback.on_output_image,
        on_failure=feedback.on_failure,
        on_timing=feedback.on_timing,
        on_completed=feedback.on_completed,
        refresh_generation_actions=(
            view.generation_action_controller.apply_generation_action_availability
        ),
        effective_batch_count=lambda: effective_generation_batch_count(view),
        build_queued_generation_snapshots=build_queued_generation_snapshots,
        capture_queued_generation_preparation=capture_queued_generation_preparation,
    )


def active_workflow_id_for_generation_action(view: object) -> str | None:
    """Return the active workflow id for prompt-safe action diagnostics."""

    workflow_session_service = getattr(view, "workflow_session_service", None)
    workflow_id = getattr(workflow_session_service, "active_workflow_id", None)
    if isinstance(workflow_id, str):
        return workflow_id
    return None


def handle_generate_clicked(
    *,
    view: GenerationActionIntentView,
    build_generation_bindings: Callable[[], GenerationUiBindings],
) -> None:
    """Route Generate/Continuous clicks to the generation controller."""

    bindings = build_generation_bindings()
    workflow_id = active_workflow_id_for_generation_action(view)
    log_debug(
        _LOGGER,
        "Routing workspace generation intent",
        operation="generate_clicked",
        workflow_id=workflow_id,
        generation_mode=view._current_generate_mode,
    )
    view.workspace_generation_controller.handle_generate_clicked(
        current_mode=view._current_generate_mode,
        bindings=bindings,
    )


def handle_interrupt_clicked(*, view: GenerationActionIntentView) -> None:
    """Interrupt active generation and clear shell progress on success."""

    workflow_id = active_workflow_id_for_generation_action(view)
    interrupt_result = view.workspace_generation_controller.interrupt_generation()
    log_debug(
        _LOGGER,
        "Workspace interrupt intent completed",
        operation="interrupt_generation",
        workflow_id=workflow_id,
        interrupt_status=interrupt_result.status,
        interrupt_status_code=interrupt_result.status_code,
    )
    if interrupt_result.status != "sent":
        view.generation_interrupt_failure_presenter.log_interrupt_failure(
            interrupt_result
        )
        return
    view.generation_feedback_dispatcher.retire_progress(reason="interrupted")
    generation_feedback_presenter_for(view).clear_all_model_field_load_progress()
    view.generation_action_controller.clear_generation_progress()


def handle_skip_generation_clicked(
    *,
    view: GenerationActionIntentView,
    build_generation_bindings: Callable[[], GenerationUiBindings],
) -> None:
    """Skip the active queued generation job and clear progress if queue is idle."""

    bindings = build_generation_bindings()
    workflow_id = active_workflow_id_for_generation_action(view)
    view.generation_feedback_dispatcher.retire_progress(reason="skipped")
    view.workspace_generation_controller.skip_active_queue_job(bindings=bindings)
    queue_state = cast(
        GenerationQueueProgressState,
        view.generation_job_queue_service,
    )
    queue_has_active_job = queue_state.has_active_job()
    log_debug(
        _LOGGER,
        "Workspace skip-generation intent completed",
        operation="skip_generation",
        workflow_id=workflow_id,
        queue_has_active_job=queue_has_active_job,
    )
    if not queue_has_active_job:
        view.generation_action_controller.clear_generation_progress()


def handle_stop_generation_clicked(
    *,
    view: GenerationActionIntentView,
    build_generation_bindings: Callable[[], GenerationUiBindings],
) -> None:
    """Cancel queued generation work and clear shell progress on success."""

    bindings = build_generation_bindings()
    workflow_id = active_workflow_id_for_generation_action(view)
    interrupt_result = view.workspace_generation_controller.cancel_generation_queue(
        bindings=bindings,
    )
    log_debug(
        _LOGGER,
        "Workspace stop-generation intent completed",
        operation="stop_generation",
        workflow_id=workflow_id,
        interrupt_status=(
            interrupt_result.status if interrupt_result is not None else "not_needed"
        ),
        interrupt_status_code=(
            interrupt_result.status_code if interrupt_result is not None else None
        ),
    )
    if interrupt_result is not None and interrupt_result.status != "sent":
        view.generation_interrupt_failure_presenter.log_interrupt_failure(
            interrupt_result
        )
        return
    view.generation_feedback_dispatcher.retire_progress(reason="stopped")
    generation_feedback_presenter_for(view).clear_all_model_field_load_progress()
    view.generation_action_controller.clear_generation_progress()


def randomize_generation_request_seeds(
    *,
    seed_randomization_service: SeedRandomizationServiceProtocol,
    request: GenerationRequest,
    behavior_snapshot: EditorBehaviorSnapshot | None,
) -> SeedRandomizationResult:
    """Randomize request workflow seeds through workflow-owned model state."""

    workflow = request.workflow
    if not isinstance(workflow, WorkflowState) and isinstance(
        seed_randomization_service,
        SeedRandomizationService,
    ):
        return SeedRandomizationResult()
    result = seed_randomization_service.randomize_workflow_seeds(
        workflow=cast(Any, workflow),
        behavior_snapshot=behavior_snapshot,
    )
    return result


def effective_generation_batch_count(view: object) -> int:
    """Return the clamped shell batch count from registry or legacy cluster."""

    registry = getattr(view, "generation_titlebar_control_registry", None)
    registry_accessor = getattr(registry, "effective_batch_count", None)
    if callable(registry_accessor):
        return max(1, int(registry_accessor()))
    cluster = getattr(view, "generationActionCluster", None)
    accessor = getattr(cluster, "effective_batch_count", None)
    if not callable(accessor):
        return 1
    return max(1, int(accessor()))


__all__ = [
    "build_generation_action_bindings",
    "active_workflow_id_for_generation_action",
    "effective_generation_batch_count",
    "handle_generate_clicked",
    "handle_interrupt_clicked",
    "handle_skip_generation_clicked",
    "handle_stop_generation_clicked",
    "randomize_generation_request_seeds",
    "GenerationActionBindingView",
    "GenerationActionIntentView",
    "GenerationRequestSeedRandomizer",
    "SeedRandomizationServiceProtocol",
    "WorkspaceGenerationActions",
]
