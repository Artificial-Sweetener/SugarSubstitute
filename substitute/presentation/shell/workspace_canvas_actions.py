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

"""Handle input/output canvas and mask flows for the workspace shell."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

import uuid
from pathlib import Path
from typing import Mapping, Protocol, cast

from PySide6.QtWidgets import QMessageBox

from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    SubstituteOperationContext,
)
from substitute.application.ports.file_manager_gateway import FileRevealResult
from substitute.application.ports import GenerationVisualIdentity, OutputImageUpdate
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewRegistry,
    OutputPreviewRejectionReason,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    LivePreviewEvent,
    OutputSceneIdentity,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputFocusMutationResult,
    OutputFocusSnapshot,
    OutputImageRegistrationResult,
    OutputPreviewCloseIdentity,
    OutputProjectionSchedulingIntent,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.domain.workflow import OutputFocusMode
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.shell.output_image_commit_pipeline import (
    FailedOutputImagePreparation,
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    CANVAS_AND_GENERATION_SURFACES,
    WorkflowInvalidationReason,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.workspace_canvas_actions")


def _mark_canvas_surfaces_dirty(
    view: object,
    workflow_id: str,
    *,
    reason: WorkflowInvalidationReason,
) -> None:
    """Record canvas maintenance intent when the shell exposes tracking."""

    service = getattr(view, "workflow_surface_invalidation_service", None)
    mark_dirty = getattr(service, "mark_dirty", None)
    if callable(mark_dirty):
        mark_dirty(workflow_id, CANVAS_AND_GENERATION_SURFACES, reason)


def _empty_output_focus_change() -> OutputFocusMutationResult:
    """Return an unchanged Output focus result for rejected shell commits."""

    snapshot = OutputFocusSnapshot(
        active_uuid=None,
        set_index=1,
        source_key=None,
        scene_key=None,
        scene_overview=False,
        focus_mode=OutputFocusMode.AUTOMATIC,
    )
    return OutputFocusMutationResult(before=snapshot, after=snapshot)


class OutputCanvasProtocol(Protocol):
    """Describe output-canvas behavior used by canvas actions."""

    def apply_preview_acceptance(
        self,
        acceptance: OutputPreviewAcceptance,
    ) -> None:
        """Display a session-authorized preview acceptance on the output canvas."""

    def clear_previews(
        self,
        source_key: str | None = None,
    ) -> None:
        """Remove transient preview images from the output canvas."""

    def close_final_output_preview_lane(
        self,
        identity: OutputPreviewCloseIdentity,
    ) -> None:
        """Close the transient preview lane replaced by a final output."""


class CanvasTabsProtocol(Protocol):
    """Describe canvas-tab registry behavior used by canvas actions."""

    canvas_map: Mapping[str, object]

    def focus_attached_canvas(self, label: str) -> None:
        """Select one attached canvas tab when it is docked."""


class OutputImagePipelineProtocol(Protocol):
    """Describe output-image pipeline submission used by canvas actions."""

    def submit_output_update(self, output_update: OutputImageUpdate) -> None:
        """Submit a saved output image update to the async pipeline."""

    def submit_legacy_output_update(self, output_update: OutputImageUpdate) -> None:
        """Submit a non-live saved output update to the async pipeline."""

    def schedule_output_projection(
        self,
        intent: OutputProjectionSchedulingIntent,
    ) -> None:
        """Schedule projection requested by a state-only Output registration."""


class GenerationTimingLookupProtocol(Protocol):
    """Describe read-only generation timing lookup for late output commits."""

    def cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str = "",
        cube_alias: str = "",
    ) -> float | None:
        """Return the latest known cube duration for one output source."""


class CanvasIoServiceProtocol(Protocol):
    """Describe canvas IO behavior used by canvas actions."""

    def load_output_image(self, source_path: Path) -> object:
        """Load output image from disk."""

    def open_image_in_external_editor(
        self,
        *,
        image: object,
        image_meta: object,
    ) -> bool:
        """Open one image in an external editor."""

    def open_images_in_external_editor(
        self,
        *,
        images: list[tuple[object, object]],
    ) -> bool:
        """Open multiple images in an external editor."""

    def resolve_node_meta_title(self, node_data: Mapping[str, object]) -> str:
        """Resolve display title for one workflow node."""

    def resolve_workflow_label(self, metadata: Mapping[str, object]) -> str:
        """Resolve workflow display label from metadata."""

    def build_output_image_metadata(
        self,
        *,
        workflow_name: str,
        node_meta_title: str,
        file_path: Path,
        source_key: str = "",
        source_label: str = "",
        node_id: str = "",
        list_index: int | None = None,
        batch_index: int | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
        client_id: str | None = None,
        scene_run_id: str | None = None,
        scene_key: str | None = None,
        scene_title: str | None = None,
        scene_order: int | None = None,
        scene_count: int | None = None,
        width: int | None = None,
        height: int | None = None,
        cube_execution_duration_ms: float | None = None,
    ) -> object:
        """Build output image metadata payload."""


class AssetRevealServiceProtocol(Protocol):
    """Describe application-owned local asset reveal behavior."""

    def reveal_asset(self, asset_path: str) -> FileRevealResult:
        """Reveal one metadata-backed local asset path."""


class OutputCanvasStateServiceProtocol(Protocol):
    """Describe durable Output workflow state behavior used by canvas actions."""

    def set_active_output_uuid(
        self,
        workflow: "WorkflowStateProtocol",
        uuid_str: str,
    ) -> None:
        """Persist selected output image id for one workflow."""

    def set_active_output_grid(
        self,
        workflow: "WorkflowStateProtocol",
        source_key: str | None,
        scene_key: str | None = None,
    ) -> None:
        """Persist selected output grid for one workflow."""

    def set_active_output_scene(
        self,
        workflow: "WorkflowStateProtocol",
        selection: OutputSceneNavigationSelection,
    ) -> None:
        """Persist one complete output scene route for one workflow."""

    def set_output_compare_state(
        self,
        workflow: "WorkflowStateProtocol",
        state: object,
    ) -> None:
        """Persist output compare state for one workflow."""

    def register_output_image(
        self,
        workflows: dict[str, "WorkflowStateProtocol"],
        workflow_id: str,
        active_workflow_id: str,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        """Register one output image without visible projection."""

    def register_generated_output(
        self,
        workflows: dict[str, "WorkflowStateProtocol"],
        active_workflow_id: str,
        *,
        event: LiveFinalOutputEvent,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        """Register one strict live generated output without visible projection."""


class CubeStateProtocol(Protocol):
    """Describe cube state data consumed by canvas actions."""

    buffer: dict[str, object]


class WorkflowCanvasStateProtocol(Protocol):
    """Describe workflow-local canvas state consumed by canvas actions."""

    input_key_map: dict[str, uuid.UUID]
    mask_associations: dict[tuple[str, str], uuid.UUID]
    active_input_mask_uuid: uuid.UUID | None


class WorkflowStateProtocol(Protocol):
    """Describe workflow state data consumed by canvas actions."""

    cubes: dict[str, CubeStateProtocol]
    canvas: WorkflowCanvasStateProtocol
    metadata: dict[str, object]


class WorkspacePathBundleProtocol(Protocol):
    """Describe shell path roots used by canvas actions."""

    projects_dir: Path


class MessageBoxProtocol(Protocol):
    """Describe message-box behavior used by canvas actions."""

    def critical(self, parent: object, title: str, text: str) -> None:
        """Show a critical dialog."""


class OutputImageSignalProtocol(Protocol):
    """Describe Qt-like signal behavior used by canvas actions."""

    def emit(self, workflow_id: str, image: object, image_meta: object) -> None:
        """Emit one output-image payload."""


class WorkflowSessionServiceProtocol(Protocol):
    """Describe workflow session behavior used by canvas actions."""

    workflows: dict[str, WorkflowStateProtocol]
    active_workflow_id: str

    def get_workflow(self, workflow_id: str) -> WorkflowStateProtocol | None:
        """Return workflow for one id."""


class WorkflowTabBarProtocol(Protocol):
    """Describe workflow-tab behavior used by canvas actions."""

    def currentIndex(self) -> int:
        """Return current workflow tab index."""

    def tabText(self, index: int) -> str:
        """Return workflow tab text."""


class WorkspaceCanvasActionView(Protocol):
    """Describe the shell surface consumed by canvas actions."""

    workflow_session_service: WorkflowSessionServiceProtocol
    workflow_tabbar: WorkflowTabBarProtocol
    canvas_tabs: CanvasTabsProtocol
    canvas_io_service: CanvasIoServiceProtocol
    output_canvas_state_service: OutputCanvasStateServiceProtocol
    output_image_pipeline: OutputImagePipelineProtocol
    add_output_image_signal: OutputImageSignalProtocol
    path_bundle: WorkspacePathBundleProtocol
    visual_authorization_service: object
    output_preview_registry: OutputPreviewRegistry

    def get_active_workflow(self) -> WorkflowStateProtocol | None:
        """Return the active workflow state."""

    def _resolve_workflow_name(self, workflow_id: str) -> str:
        """Resolve the display name for one workflow id."""


class WorkspaceCanvasActions:
    """Own input-image, mask, preview, and output canvas orchestration."""

    def __init__(
        self,
        view: WorkspaceCanvasActionView,
        *,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        asset_reveal_service: AssetRevealServiceProtocol | None = None,
    ) -> None:
        """Store shell dependencies for canvas-related user actions."""

        self._view = view
        self._error_presenter = error_presenter
        self._asset_reveal_service = asset_reveal_service

    def on_active_output_changed(self, uuid_str: str) -> None:
        """Persist the currently selected output image id into workflow state."""

        view = self._view
        active_workflow = view.get_active_workflow()
        if active_workflow is not None:
            view.output_canvas_state_service.set_active_output_uuid(
                active_workflow,
                uuid_str,
            )
            self._project_user_selected_output()

    def on_active_output_grid_changed(self, source_key: str) -> None:
        """Persist the currently selected output grid source into workflow state."""

        view = self._view
        active_workflow = view.get_active_workflow()
        if active_workflow is not None:
            view.output_canvas_state_service.set_active_output_grid(
                active_workflow,
                source_key,
            )
            self._project_user_selected_output()

    def on_active_output_scene_changed(
        self,
        selection: OutputSceneNavigationSelection,
    ) -> None:
        """Persist one atomic scene-level Output route selection."""

        view = self._view
        active_workflow = view.get_active_workflow()
        if active_workflow is not None:
            view.output_canvas_state_service.set_active_output_scene(
                active_workflow,
                selection,
            )
            self._project_user_selected_output()

    def on_output_compare_changed(self, state: object) -> None:
        """Persist output compare viewing state into workflow state."""

        view = self._view
        active_workflow = view.get_active_workflow()
        if active_workflow is not None:
            view.output_canvas_state_service.set_output_compare_state(
                active_workflow,
                state,
            )
            self._project_user_selected_output()

    def _project_user_selected_output(self) -> None:
        """Request immediate projection after Output selection intent persists."""

        view = self._view
        session_service = getattr(view, "workflow_session_service", None)
        workflow_id = str(getattr(session_service, "active_workflow_id", "") or "")
        if not workflow_id:
            return
        output_pipeline = getattr(view, "output_image_pipeline", None)
        schedule = getattr(
            output_pipeline,
            "schedule_user_selected_output_projection",
            None,
        )
        if callable(schedule):
            schedule(workflow_id)
        return

    def display_preview_image(
        self,
        preview: object,
    ) -> None:
        """Display preview image only after strict identity and session checks."""

        if not isinstance(preview, LivePreviewEvent):
            return
        view = self._view
        workflow_id = preview.identity.workflow_id
        output_canvas = view.canvas_tabs.canvas_map.get("Output")
        if output_canvas is None:
            self._log_missing_output_canvas(workflow_id)
            return
        session = self._output_session_for_preview(output_canvas, workflow_id)
        if session is None:
            return
        authorization = getattr(view, "visual_authorization_service", None)
        authorize_preview = getattr(authorization, "authorize_preview", None)
        if not callable(authorize_preview):
            return
        acceptance = view.output_preview_registry.accept_preview(
            preview,
            session=session,
            active_workflow_id=view.workflow_session_service.active_workflow_id,
            authorize_preview=authorize_preview,
            is_valid_scene_placeholder=self._valid_scene_preview_placeholder,
        )
        if not acceptance.accepted and not acceptance.retired_preview_ids:
            return
        apply_preview = getattr(output_canvas, "apply_preview_acceptance", None)
        if callable(apply_preview):
            apply_preview(acceptance)
            return
        self._log_missing_output_canvas(workflow_id)

    def _output_session_for_preview(
        self,
        output_canvas: object,
        workflow_id: str,
    ) -> OutputCanvasSession | None:
        """Return or bind the active visible Output session for a preview."""

        session = getattr(output_canvas, "_output_session", None)
        if isinstance(session, OutputCanvasSession):
            return session
        view = self._view
        session_service = getattr(view, "workflow_session_service", None)
        active_workflow_id = str(
            getattr(session_service, "active_workflow_id", "") or ""
        )
        if workflow_id != active_workflow_id:
            return None
        canvas_tabs = getattr(view, "canvas_tabs", None)
        is_canvas_visible = getattr(canvas_tabs, "is_canvas_visible", None)
        if callable(is_canvas_visible) and not bool(is_canvas_visible("Output")):
            return None
        workflows = getattr(session_service, "workflows", None)
        if not isinstance(workflows, Mapping):
            return None
        coordinator = getattr(view, "output_canvas_projection_coordinator", None)
        project_workflow = getattr(coordinator, "project_workflow", None)
        if not callable(project_workflow):
            return None
        project_workflow(workflows, workflow_id)
        session = getattr(output_canvas, "_output_session", None)
        return session if isinstance(session, OutputCanvasSession) else None

    def clear_output_previews(self, workflow_id: str) -> None:
        """Clear transient output previews for the active workflow only."""

        view = self._view
        if workflow_id != view.workflow_session_service.active_workflow_id:
            return
        output_canvas = view.canvas_tabs.canvas_map.get("Output")
        clear_previews = getattr(output_canvas, "clear_previews", None)
        if callable(clear_previews):
            clear_previews()
        else:
            self._log_missing_output_canvas(workflow_id)

    def open_image_in_external_editor(
        self,
        image: object,
        image_meta: object,
    ) -> bool:
        """Open one output image in the configured external editor."""

        return bool(
            self._view.canvas_io_service.open_image_in_external_editor(
                image=image,
                image_meta=image_meta,
            )
        )

    def open_images_in_external_editor(
        self,
        images: list[tuple[object, object]],
    ) -> bool:
        """Open all selected output images in the external editor."""

        return bool(
            self._view.canvas_io_service.open_images_in_external_editor(images=images)
        )

    def reveal_output_asset(self, image_meta: object) -> bool:
        """Reveal one output asset through the application-owned file manager flow."""

        if self._asset_reveal_service is None:
            return False
        asset_path = getattr(image_meta, "path", None)
        if not isinstance(asset_path, str):
            return False
        return self._asset_reveal_service.reveal_asset(asset_path).succeeded

    def handle_add_output_image(
        self,
        workflow_id: str,
        image: object,
        image_meta: object,
    ) -> None:
        """Register a non-live output image without direct QPane mutation."""

        view = self._view
        result = view.output_canvas_state_service.register_output_image(
            view.workflow_session_service.workflows,
            workflow_id,
            view.workflow_session_service.active_workflow_id,
            image,
            image_meta,
        )
        if result.image_id is None:
            return
        self._close_registered_output_preview_lane(result)
        self._schedule_registered_output_projection(result)
        self._record_workflow_output_activity(workflow_id)
        _mark_canvas_surfaces_dirty(
            view,
            workflow_id,
            reason=WorkflowInvalidationReason.GENERATION_RESULT_MATERIALIZED,
        )

    def handle_loaded_output_image(
        self,
        workflow_id: str,
        image: object,
        image_meta: object,
    ) -> None:
        """Register a loaded recipe output and schedule projection only."""

        view = self._view
        result = view.output_canvas_state_service.register_output_image(
            view.workflow_session_service.workflows,
            workflow_id,
            view.workflow_session_service.active_workflow_id,
            image,
            image_meta,
        )
        if result.image_id is None:
            return
        self._schedule_registered_output_projection(result)

    def commit_prepared_output_image(
        self,
        prepared: PreparedOutputImage,
    ) -> OutputImageRegistrationResult:
        """Commit one prepared output through registration-only state mutation."""

        view = self._view
        request = prepared.request
        if not self._prepared_output_is_authorized(request):
            log_warning(
                _LOGGER,
                "Rejected prepared output image before canvas registration",
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                prompt_id=request.prompt_id,
                client_id=request.client_id,
                source_key=request.source_key,
                scene_key=request.scene_key,
                reason="post_prepare_authorization_failed",
            )
            return OutputImageRegistrationResult(
                workflow_id=request.workflow_id,
                image_id=None,
                registered=False,
                focus_change=_empty_output_focus_change(),
                preview_close_identity=None,
                projection_intent=OutputProjectionSchedulingIntent.none(
                    request.workflow_id
                ),
            )
        cube_execution_duration_ms = (
            request.cube_execution_duration_ms
            if request.cube_execution_duration_ms is not None
            else self._cube_execution_duration_for_commit(request)
        )
        image_meta = view.canvas_io_service.build_output_image_metadata(
            workflow_name=request.workflow_name,
            node_meta_title=request.node_meta_title,
            file_path=request.file_path,
            source_key=request.source_key,
            source_label=request.source_label,
            generation_run_id=request.generation_run_id,
            prompt_id=request.prompt_id,
            client_id=request.client_id,
            scene_run_id=request.scene_run_id,
            scene_key=request.scene_key,
            scene_title=request.scene_title,
            scene_order=request.scene_order,
            scene_count=request.scene_count,
            list_index=(
                request.position.list_index if request.position is not None else None
            ),
            batch_index=(
                request.position.batch_index if request.position is not None else None
            ),
            width=request.artifact_width or prepared.image.width(),
            height=request.artifact_height or prepared.image.height(),
            cube_execution_duration_ms=cube_execution_duration_ms,
            node_id=request.node_id,
        )
        if request.live_event is not None:
            result = view.output_canvas_state_service.register_generated_output(
                view.workflow_session_service.workflows,
                view.workflow_session_service.active_workflow_id,
                event=request.live_event,
                image=prepared.image,
                image_meta=image_meta,
            )
        else:
            result = view.output_canvas_state_service.register_output_image(
                view.workflow_session_service.workflows,
                request.workflow_id,
                view.workflow_session_service.active_workflow_id,
                prepared.image,
                image_meta,
            )
        if not result.registered or result.image_id is None:
            return result
        self._close_registered_output_preview_lane(result)
        self._record_workflow_output_activity(request.workflow_id)
        _mark_canvas_surfaces_dirty(
            view,
            request.workflow_id,
            reason=WorkflowInvalidationReason.GENERATION_RESULT_MATERIALIZED,
        )
        return result

    def _close_registered_output_preview_lane(
        self,
        result: OutputImageRegistrationResult,
    ) -> None:
        """Close matching preview lanes after final registration."""

        identity = result.preview_close_identity
        if identity is None:
            return
        view = self._view
        close_result = view.output_preview_registry.close_final_output_lane(identity)
        if result.workflow_id != view.workflow_session_service.active_workflow_id:
            return
        if not close_result.closed:
            return
        output_canvas = view.canvas_tabs.canvas_map.get("Output")
        apply_preview = getattr(output_canvas, "apply_preview_acceptance", None)
        if callable(apply_preview):
            apply_preview(
                OutputPreviewAcceptance.rejected(
                    OutputPreviewRejectionReason.COMPLETED_LANE,
                    retired_preview_ids=close_result.closed_preview_ids,
                )
            )
        else:
            self._log_missing_output_canvas(result.workflow_id)

    def _log_missing_output_canvas(self, workflow_id: str) -> None:
        """Log missing output canvas state through the feedback presenter."""

        generation_feedback_presenter_for(self._view).log_missing_output_canvas(
            workflow_id
        )

    def _valid_scene_preview_placeholder(
        self,
        scene: OutputSceneIdentity,
        identity: GenerationVisualIdentity,
    ) -> bool:
        """Return whether a scene preview is known to the active scene run."""

        scene_run_service = getattr(self._view, "output_scene_run_service", None)
        run_for_id = getattr(scene_run_service, "run_for_id", None)
        if not callable(run_for_id):
            return False
        run = run_for_id(scene.run_id)
        if run is None or getattr(run, "workflow_id", None) != identity.workflow_id:
            return False
        scene_entry = getattr(run, "scene_for_key", lambda _scene_key: None)(scene.key)
        if scene_entry is None:
            return False
        status = getattr(scene_entry, "status", "")
        return status in {"pending", "dispatching", "comfy_pending", "running"}

    def _schedule_registered_output_projection(
        self,
        result: OutputImageRegistrationResult,
    ) -> None:
        """Hand active registration projection work to the Output scheduler."""

        intent = result.projection_intent
        if not intent.should_schedule:
            return
        output_pipeline = getattr(self._view, "output_image_pipeline", None)
        schedule = getattr(output_pipeline, "schedule_output_projection", None)
        if callable(schedule):
            schedule(intent)

    def _prepared_output_is_authorized(
        self,
        request: OutputImageCommitRequest,
    ) -> bool:
        """Return whether one prepared output still belongs to an accepted run."""

        authorization = getattr(self._view, "visual_authorization_service", None)
        authorize = getattr(authorization, "authorize_final_output", None)
        if not callable(authorize):
            return True
        if (
            not request.generation_run_id
            or not request.prompt_id
            or not request.client_id
            or not request.source_key
            or not request.source_label
        ):
            return False
        return bool(
            authorize(
                GenerationVisualIdentity(
                    workflow_id=request.workflow_id,
                    generation_run_id=request.generation_run_id,
                    prompt_id=request.prompt_id,
                    client_id=request.client_id,
                    source_key=request.source_key,
                    source_label=request.source_label,
                    scene_run_id=request.scene_run_id,
                    scene_key=request.scene_key,
                    scene_title=request.scene_title,
                    scene_order=request.scene_order,
                    scene_count=request.scene_count,
                    node_id=request.node_id,
                )
            )
        )

    def _cube_execution_duration_for_commit(
        self,
        request: OutputImageCommitRequest,
    ) -> float | None:
        """Return late-arriving queue timing for one prepared output commit."""

        timing_lookup = getattr(self._view, "generation_job_queue_service", None)
        if timing_lookup is None:
            return None
        lookup = getattr(timing_lookup, "cube_execution_duration_ms", None)
        if not callable(lookup):
            return None
        return cast(
            float | None,
            lookup(
                workflow_id=request.workflow_id,
                source_key=request.source_key,
                cube_alias=request.source_label,
            ),
        )

    def handle_output_image_preparation_failed(
        self,
        failure: FailedOutputImagePreparation,
        *,
        message_box: MessageBoxProtocol | None = None,
    ) -> None:
        """Present one failed asynchronous output image preparation."""

        request = failure.request
        self._show_generated_image_load_error(
            workflow_id=request.workflow_id,
            node_id=request.node_id,
            file_path=str(request.file_path),
            source_key=request.source_key,
            source_label=request.source_label,
            scene_run_id=request.scene_run_id,
            scene_key=request.scene_key,
            scene_title=request.scene_title,
            scene_order=request.scene_order,
            scene_count=request.scene_count,
            fallback_message_box=(
                message_box
                if message_box is not None
                else cast(MessageBoxProtocol, QMessageBox)
            ),
        )

    def prepare_output_image_commit(self, output_update: OutputImageUpdate) -> None:
        """Submit a final output image for asynchronous preparation."""

        submit = getattr(
            getattr(self._view, "output_image_pipeline", None),
            "submit_output_update",
            None,
        )
        if callable(submit):
            submit(output_update)
            return
        log_warning(
            _LOGGER,
            "Output image pipeline unavailable for generated output",
            workflow_id=output_update.workflow_id,
            node_id=output_update.node_id,
            path=output_update.file_path,
        )

    def prepare_legacy_output_image_commit(
        self,
        output_update: OutputImageUpdate,
    ) -> None:
        """Submit a non-live output image through explicit fallback semantics."""

        pipeline = getattr(self._view, "output_image_pipeline", None)
        submit_legacy = getattr(pipeline, "submit_legacy_output_update", None)
        if callable(submit_legacy):
            submit_legacy(output_update)
            return
        log_warning(
            _LOGGER,
            "Output image pipeline unavailable for legacy generated output",
            workflow_id=output_update.workflow_id,
            node_id=output_update.node_id,
            path=output_update.file_path,
        )

    def _record_workflow_output_activity(self, workflow_id: str) -> None:
        """Mark inactive workflow tabs when saved outputs arrive."""

        view = self._view
        activity_service = getattr(view, "workflow_activity_service", None)
        record_output = getattr(activity_service, "record_output", None)
        if not callable(record_output):
            return
        became_unread = bool(
            record_output(
                workflow_id,
                view.workflow_session_service.active_workflow_id,
            )
        )
        if not became_unread:
            return
        set_unread = getattr(view.workflow_tabbar, "set_workflow_unread_result", None)
        if callable(set_unread):
            set_unread(workflow_id, True)

    def update_canvas_callback(
        self,
        workflow_id: str,
        workflow: dict[str, object],
        file_path: str,
        node_id: str,
        *,
        source_key: str = "",
        source_label: str = "",
        scene_run_id: str | None = None,
        scene_key: str | None = None,
        scene_title: str | None = None,
        scene_order: int | None = None,
        scene_count: int | None = None,
        message_box: MessageBoxProtocol | None = None,
    ) -> None:
        """Delegate generated image commits to the asynchronous output pipeline."""

        _ = message_box
        self.prepare_legacy_output_image_commit(
            OutputImageUpdate(
                workflow_id=workflow_id,
                workflow_payload=workflow,
                file_path=Path(file_path),
                node_id=node_id,
                source_key=source_key,
                source_label=source_label,
                scene_run_id=scene_run_id,
                scene_key=scene_key,
                scene_title=scene_title,
                scene_order=scene_order,
                scene_count=scene_count,
            )
        )

    def _show_generated_image_load_error(
        self,
        *,
        workflow_id: str,
        node_id: str,
        file_path: str,
        source_key: str,
        source_label: str,
        scene_run_id: str | None,
        scene_key: str | None,
        scene_title: str | None,
        scene_order: int | None,
        scene_count: int | None,
        fallback_message_box: MessageBoxProtocol,
    ) -> None:
        """Show an output-image load failure through the structured modal surface."""

        message = app_text("Could not load image: %1", file_path)
        if self._error_presenter is None:
            fallback_message_box.critical(
                self._view,
                render_application_text(app_text("Load Error")),
                render_application_text(message),
            )
            return

        self._error_presenter.show_error_report(
            ErrorReport(
                kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
                title=app_text("Generated image load failed"),
                message=message,
                stage="canvas",
                workflow_id=workflow_id,
                technical_detail=message,
                operation_context=SubstituteOperationContext(
                    operation="load_generated_output_image",
                    workflow_id=workflow_id,
                    path=file_path,
                    node_id=node_id,
                    values={
                        "source_key": source_key,
                        "source_label": source_label,
                        "scene_run_id": scene_run_id,
                        "scene_key": scene_key,
                        "scene_title": scene_title,
                        "scene_order": scene_order,
                        "scene_count": scene_count,
                    },
                ),
            )
        )


__all__ = ["WorkspaceCanvasActions", "WorkspaceCanvasActionView"]
