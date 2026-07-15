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

"""Define shell workspace protocols shared by workspace collaborators."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from substitute.application.generation import GenerationFailure, GenerationRunStarted
from substitute.application.generation.workflow_progress_service import (
    GenerationProgressRetirementReason,
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


class InputCanvasPresenterProtocol(Protocol):
    """Describe Input canvas intent ownership required by the shell."""

    def handle_input_image_changed(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> None:
        """Handle editor-panel LoadImage change intent."""

    def handle_input_image_clicked(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> None:
        """Handle editor-panel LoadImage focus intent."""

    def handle_input_canvas_image_loaded(
        self,
        image_id: object,
        image_path: str,
    ) -> None:
        """Handle QPane-confirmed Input image load intent."""

    def refresh_active_mask_pickers(self) -> None:
        """Refresh active editor-panel mask pickers from workflow asset state."""

    def handle_input_mask_changed(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> None:
        """Handle editor-panel LoadImageMask change intent."""

    def handle_input_mask_clicked(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> None:
        """Handle editor-panel LoadImageMask focus intent."""

    def handle_mask_save_completed(self, mask_id: str, path: str) -> None:
        """Handle QPane mask-save completion intent."""

    def materialize_loaded_cube_input_canvas(
        self,
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Materialize loaded-cube Input canvas state."""

    def reconcile_active_input_canvas_image(self) -> None:
        """Reconcile the active QPane Input image before generation."""


class WorkflowSessionState(Protocol):
    """Describe workflow-session state used by controller generation bindings."""

    active_workflow_id: str
    workflows: Mapping[str, object]


class OutputCanvasStateGenerationProtocol(Protocol):
    """Describe run-start output focus APIs used by generation orchestration."""

    def begin_output_generation(
        self,
        workflows: Mapping[str, object],
        workflow_id: str,
        *,
        scene_run_id: str | None = None,
        scene_count: int | None = None,
    ) -> None:
        """Prepare output focus for a generation run."""


class GenerationFeedbackDispatcherProtocol(Protocol):
    """Describe generation feedback callbacks exposed to orchestration."""

    def on_progress(self, update: ProgressUpdate) -> None:
        """Handle generation progress feedback."""

    def on_run_started(self, event: GenerationRunStarted) -> None:
        """Handle prompt-bound generation run registration."""

    def on_model_load_progress(self, update: ModelLoadProgressUpdate) -> None:
        """Handle generation model-load progress feedback."""

    def on_preview(self, update: PreviewImageUpdate) -> None:
        """Handle generation preview feedback."""

    def on_output_image(self, update: OutputImageUpdate) -> None:
        """Handle generation output image feedback."""

    def on_failure(self, failure: GenerationFailure) -> None:
        """Handle generation failure feedback."""

    def on_timing(self, update: GenerationExecutionTiming) -> None:
        """Handle generation timing feedback."""

    def on_completed(self, event: ListenerCompleted) -> None:
        """Handle generation completion feedback."""

    def retire_progress(
        self,
        *,
        reason: GenerationProgressRetirementReason,
        workflow_id: str | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
        client_id: str | None = None,
    ) -> None:
        """Retire shell generation progress for one lifecycle."""


class GenerationQueueProgressState(Protocol):
    """Describe queue state needed for cancellation progress cleanup."""

    def has_active_job(self) -> bool:
        """Return whether queued generation still owns active work."""


class InputMaskGenerationPreflightProtocol(Protocol):
    """Describe Input mask persistence required before generation."""

    def flush_dirty_associated_masks_before_generation(self) -> bool:
        """Persist dirty associated Input masks before generation starts."""


class GenerationActionRefreshProtocol(Protocol):
    """Describe generation action refresh owned by the shell action controller."""

    def apply_generation_action_availability(self) -> None:
        """Refresh projected generation titlebar action state."""

    def clear_generation_progress(self) -> None:
        """Clear shell-level generation progress indicators."""


class GenerationInterruptFailurePresenterProtocol(Protocol):
    """Describe shell diagnostics for failed interrupt requests."""

    def log_interrupt_failure(self, interrupt_result: InterruptResult) -> None:
        """Log interrupt failure context."""


class WorkflowNameResolverProtocol(Protocol):
    """Describe shell workflow-name lookup used for generation metadata."""

    def resolve_workflow_name(self, workflow_id: str) -> str:
        """Resolve one workflow display name."""


class WorkspaceGenerationControllerProtocol(Protocol):
    """Describe generation controller methods used by workspace actions."""

    def handle_generate_clicked(
        self,
        *,
        current_mode: str,
        bindings: object,
    ) -> None:
        """Handle a generate action for the active workflow."""

    def interrupt_generation(self) -> InterruptResult:
        """Interrupt the active backend generation."""

    def skip_active_queue_job(
        self,
        *,
        bindings: object | None = None,
    ) -> None:
        """Skip the active queued generation job."""

    def cancel_generation_queue(
        self,
        *,
        bindings: object | None = None,
    ) -> InterruptResult | None:
        """Cancel queued generation work."""


class WorkspaceSettingsRouteController(Protocol):
    """Describe Settings route behavior required by workspace actions."""

    def project_settings_workspace(self) -> None:
        """Open the shared Settings surface."""


class WorkspaceGenerationView(Protocol):
    """Describe the shell surface consumed by generation-button orchestration."""

    workflow_session_service: WorkflowSessionState
    output_canvas_state_service: OutputCanvasStateGenerationProtocol
    input_mask_save_controller: InputMaskGenerationPreflightProtocol
    workspace_generation_controller: WorkspaceGenerationControllerProtocol
    generation_feedback_dispatcher: GenerationFeedbackDispatcherProtocol
    generation_job_queue_service: object
    generation_result_snapshot_service: object
    recipe_io_service: object
    prompt_wildcard_preprocessing_service: object | None
    generation_action_controller: GenerationActionRefreshProtocol
    generation_interrupt_failure_presenter: GenerationInterruptFailurePresenterProtocol
    input_canvas_shell_adapter: WorkflowNameResolverProtocol
    settings_route_controller: WorkspaceSettingsRouteController
    _current_generate_mode: str

    def get_active_workflow(self) -> object:
        """Return the active workflow state."""

    def request_reconfigure(self) -> None:
        """Open the shared onboarding surface in reconfigure mode."""


__all__ = [
    "GenerationActionRefreshProtocol",
    "GenerationFeedbackDispatcherProtocol",
    "GenerationInterruptFailurePresenterProtocol",
    "GenerationQueueProgressState",
    "InputCanvasPresenterProtocol",
    "InputMaskGenerationPreflightProtocol",
    "OutputCanvasStateGenerationProtocol",
    "WorkflowNameResolverProtocol",
    "WorkflowSessionState",
    "WorkspaceGenerationControllerProtocol",
    "WorkspaceGenerationView",
    "WorkspaceSettingsRouteController",
]
