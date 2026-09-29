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

"""Register prepared and restored images with the Output canvas state."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol, cast

from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputImageRegistrationResult,
    OutputProjectionSchedulingIntent,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputFocusMutationResult,
    OutputFocusSnapshot,
)
from substitute.domain.workflow import OutputFocusMode
from substitute.domain.output_media import OutputMediaKind
from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
    PreparedOutputImage,
    generation_visual_identity_for_commit,
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
    """Describe output-canvas behavior used by Output registration."""

    def release_automatic_preview_follow(self) -> None:
        """Let a newly arrived final output become the Automatic frontier."""


class CanvasHostProtocol(Protocol):
    """Expose the mounted Output canvas by route key."""

    def canvas_for(self, route_key: str) -> object | None:
        """Return the configured canvas for a route key."""


class OutputImagePipelineProtocol(Protocol):
    """Schedule projection after Output registration."""

    def schedule_output_projection(
        self,
        intent: OutputProjectionSchedulingIntent,
    ) -> None:
        """Schedule projection requested by a state-only Output registration."""


class CanvasIoServiceProtocol(Protocol):
    """Build metadata for a prepared Output image."""

    def build_output_image_metadata(
        self,
        *,
        workflow_name: str,
        node_meta_title: str,
        file_path: Path | None,
        source_key: str = "",
        source_label: str = "",
        node_id: str = "",
        list_index: int | None = None,
        batch_index: int | None = None,
        generation_run_id: str | None = None,
        output_session_id: str | None = None,
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
        media_kind: OutputMediaKind = OutputMediaKind.IMAGE,
        duration_seconds: float | None = None,
        mime_type: str | None = None,
        temporary: bool = False,
    ) -> object:
        """Build output image metadata payload."""


class OutputCanvasStateServiceProtocol(Protocol):
    """Register one image with durable Output workflow state."""

    def register_output_image(
        self,
        workflows: dict[str, object],
        workflow_id: str,
        active_workflow_id: str,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        """Register one output image without visible projection."""


class OutputGeneratedResultServiceProtocol(Protocol):
    """Commit one validated presentable generated Output result."""

    def commit_generated_output(
        self,
        workflows: dict[str, object],
        active_workflow_id: str,
        *,
        event: object,
        image: object,
        image_meta: object,
    ) -> OutputImageRegistrationResult:
        """Commit one live generated result."""


class OutputProjectionCoordinatorProtocol(Protocol):
    """Retire document payloads released by result replacement."""

    def retire_replaced_output_images(self, image_ids: tuple[uuid.UUID, ...]) -> None:
        """Retire replaced Output document content."""

    def retire_preview_images_after_projection(
        self,
        workflow_id: str,
        image_ids: tuple[uuid.UUID, ...],
    ) -> None:
        """Retire completed preview content after its final is presented."""


class WorkflowSessionServiceProtocol(Protocol):
    """Expose registered workflows and active Output identity."""

    workflows: dict[str, object]
    active_workflow_id: str


class WorkspaceCanvasActionView(Protocol):
    """Describe the shell surface consumed by canvas actions."""

    workflow_session_service: WorkflowSessionServiceProtocol
    workflow_tabbar: object
    canvas_host: CanvasHostProtocol
    canvas_io_service: CanvasIoServiceProtocol
    output_canvas_state_service: OutputCanvasStateServiceProtocol
    output_generated_result_service: OutputGeneratedResultServiceProtocol
    output_canvas_projection_coordinator: OutputProjectionCoordinatorProtocol
    output_image_pipeline: OutputImagePipelineProtocol
    visual_authorization_service: object
    output_preview_registry: OutputPreviewRegistry


class WorkspaceCanvasActions:
    """Own Output image registration and post-registration lifecycle effects."""

    def __init__(
        self,
        view: WorkspaceCanvasActionView,
    ) -> None:
        """Store the state and projection dependencies for Output registration."""

        self._view = view

    def handle_add_output_image(
        self,
        workflow_id: str,
        image: object,
        image_meta: object,
    ) -> None:
        """Register a non-live output image without direct renderer mutation."""

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
            output_session_id=request.output_session_id,
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
            media_kind=request.media_kind,
            duration_seconds=request.duration_seconds,
            mime_type=request.mime_type,
            temporary=request.temporary,
        )
        if request.live_event is not None:
            result = view.output_generated_result_service.commit_generated_output(
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
        if result.retired_image_ids:
            view.output_canvas_projection_coordinator.retire_replaced_output_images(
                result.retired_image_ids
            )
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
        """Close matching preview lanes while their final projection is pending."""

        identity = result.preview_close_identity
        if identity is None:
            return
        view = self._view
        close_result = view.output_preview_registry.close_final_output_lane(identity)
        if result.workflow_id != view.workflow_session_service.active_workflow_id:
            return
        if identity.batch_index in {None, 0}:
            output_canvas = view.canvas_host.canvas_for("Output")
            if output_canvas is None:
                self._log_missing_output_canvas(result.workflow_id)
            else:
                cast(
                    OutputCanvasProtocol, output_canvas
                ).release_automatic_preview_follow()
        if not close_result.closed:
            return
        coordinator = getattr(view, "output_canvas_projection_coordinator", None)
        defer_retirement = getattr(
            coordinator,
            "retire_preview_images_after_projection",
            None,
        )
        if callable(defer_retirement):
            defer_retirement(result.workflow_id, close_result.closed_preview_ids)

    def _log_missing_output_canvas(self, workflow_id: str) -> None:
        """Log missing output canvas state through the feedback presenter."""

        generation_feedback_presenter_for(self._view).log_missing_output_canvas(
            workflow_id
        )

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
        identity = generation_visual_identity_for_commit(request)
        return identity is not None and bool(authorize(identity))

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


__all__ = ["WorkspaceCanvasActions", "WorkspaceCanvasActionView"]
