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

"""Coordinate asynchronous final-output preparation, commit, and projection."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol
from uuid import UUID

from PySide6.QtCore import QObject

from substitute.application.ports import OutputImageUpdate
from substitute.application.workflows.output_visual_events import LiveFinalOutputEvent
from substitute.application.workflows.output_canvas_state_service import (
    OutputImageRegistrationResult,
    OutputProjectionSchedulingIntent,
)
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
    ProjectionReason,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    FailedOutputImagePreparation,
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.presentation.shell.output_image_commit_request_builder import (
    CanvasIoMetadataProtocol,
    GenerationTimingLookupProtocol,
    OutputImageCommitRequestBuilder,
    WorkflowSessionProtocol as CommitWorkflowSessionProtocol,
)
from substitute.presentation.shell.output_image_commit_queue import (
    PreparedOutputCommitQueue,
)
from substitute.presentation.shell.output_image_preparation_dispatcher import (
    OutputImagePreparationDispatcher,
)


class WorkflowSessionProtocol(CommitWorkflowSessionProtocol, Protocol):
    """Describe workflow session access needed for output request construction."""

    active_workflow_id: str
    workflows: Mapping[str, object]


class OutputCommitHandlerProtocol(Protocol):
    """Describe GUI-thread output commit hooks."""

    def commit_prepared_output_image(
        self,
        prepared: PreparedOutputImage,
    ) -> OutputImageRegistrationResult:
        """Commit one prepared output to application state."""

    def handle_output_image_preparation_failed(
        self,
        failure: FailedOutputImagePreparation,
    ) -> None:
        """Present a failed output-image preparation."""


class OutputCanvasProjectionCoordinatorProtocol(Protocol):
    """Describe visible Output projection owned by the projection coordinator."""

    def project_workflow(
        self,
        workflows: Mapping[str, object],
        active_workflow_id: str,
        *,
        registered_image_id: UUID | None = None,
    ) -> None:
        """Project the active Output workflow state."""


class CanvasTabsVisibilityProtocol(Protocol):
    """Describe canvas-tab state needed for projection scheduling."""

    canvas_map: object


class OutputImagePipeline(QObject):
    """Facade for final-output preparation, bounded commit, and projection."""

    def __init__(
        self,
        *,
        workflow_session_service: WorkflowSessionProtocol,
        canvas_io_service: CanvasIoMetadataProtocol,
        output_commit_handler: OutputCommitHandlerProtocol,
        output_canvas_projection_coordinator: OutputCanvasProjectionCoordinatorProtocol,
        canvas_tabs: object,
        parent: QObject | None = None,
        generation_timing_lookup: GenerationTimingLookupProtocol | None = None,
        preparation_dispatcher: OutputImagePreparationDispatcher,
        commit_queue: PreparedOutputCommitQueue | None = None,
        projection_scheduler: CanvasProjectionScheduler | None = None,
        output_canvas_visible: Callable[[], bool] | None = None,
        prompt_interaction_active: Callable[[], bool] | None = None,
        prompt_interaction_elapsed_ms: Callable[[], float | None] | None = None,
    ) -> None:
        """Wire final-output collaborators behind one shell dependency."""

        super().__init__(parent)
        self._workflow_session_service = workflow_session_service
        self._output_commit_handler = output_commit_handler
        self._output_canvas_projection_coordinator = (
            output_canvas_projection_coordinator
        )
        self._canvas_tabs = canvas_tabs
        self._commit_request_builder = OutputImageCommitRequestBuilder(
            workflow_session_service=workflow_session_service,
            canvas_io_service=canvas_io_service,
            generation_timing_lookup=generation_timing_lookup,
        )
        self._output_canvas_visible = (
            output_canvas_visible or self._output_canvas_is_visible
        )
        self._projection_scheduler = projection_scheduler or CanvasProjectionScheduler(
            project_workflow=self._project_active_output_projection,
            active_workflow_id=lambda: (
                self._workflow_session_service.active_workflow_id
            ),
            output_canvas_visible=self._output_canvas_visible,
            prompt_interaction_active=prompt_interaction_active,
            prompt_interaction_elapsed_ms=prompt_interaction_elapsed_ms,
            parent=self,
        )
        self._commit_queue = commit_queue or PreparedOutputCommitQueue(
            commit_prepared=output_commit_handler.commit_prepared_output_image,
            handle_failure=output_commit_handler.handle_output_image_preparation_failed,
            projection_scheduler=self._projection_scheduler,
            parent=self,
        )
        self._preparation_dispatcher = preparation_dispatcher
        self._preparation_dispatcher.prepared.connect(
            self._commit_queue.enqueue_prepared
        )
        self._preparation_dispatcher.failed.connect(self._commit_queue.enqueue_failed)
        self._connect_canvas_route_changes()

    def _project_active_output_projection(
        self,
        workflow_id: str,
        registered_image_id: UUID | None = None,
    ) -> None:
        """Project through the Output coordinator when the workflow is active."""

        active_workflow_id = self._workflow_session_service.active_workflow_id
        if workflow_id != active_workflow_id:
            return
        self._output_canvas_projection_coordinator.project_workflow(
            self._workflow_session_service.workflows,
            active_workflow_id,
            registered_image_id=registered_image_id,
        )

    def submit_output_update(self, output_update: OutputImageUpdate) -> None:
        """Submit one saved generation output to the asynchronous commit pipeline."""

        request = self.build_commit_request(output_update)
        if request is None:
            return
        self._preparation_dispatcher.submit(request)

    def submit_live_output_event(self, event: LiveFinalOutputEvent) -> None:
        """Submit one strict live final output to the asynchronous commit pipeline."""

        self._preparation_dispatcher.submit(self.build_live_commit_request(event))

    def submit_legacy_output_update(self, output_update: OutputImageUpdate) -> None:
        """Submit an explicit non-live output update with legacy source fallback."""

        self._preparation_dispatcher.submit(
            self.build_legacy_commit_request(output_update)
        )

    def build_commit_request(
        self,
        output_update: OutputImageUpdate,
    ) -> OutputImageCommitRequest | None:
        """Build a strict immutable live commit request on the GUI thread."""

        return self._commit_request_builder.build_strict_update(output_update)

    def build_live_commit_request(
        self,
        live_event: LiveFinalOutputEvent,
    ) -> OutputImageCommitRequest:
        """Build a strict immutable live commit request on the GUI thread."""

        return self._commit_request_builder.build_live_event(live_event)

    def build_legacy_commit_request(
        self,
        output_update: OutputImageUpdate,
    ) -> OutputImageCommitRequest:
        """Build a non-live commit request that preserves legacy fallback routing."""

        return self._commit_request_builder.build_legacy_update(output_update)

    def flush_visible_output_projection(self) -> None:
        """Flush pending generated projection for the active workflow."""

        self._projection_scheduler.flush_pending_for_workflow(
            self._workflow_session_service.active_workflow_id
        )

    def schedule_output_projection(
        self,
        intent: OutputProjectionSchedulingIntent,
    ) -> None:
        """Schedule projection requested by a state-only Output registration."""

        if not intent.should_schedule:
            return
        self._projection_scheduler.request_projection(
            intent.workflow_id,
            reason=ProjectionReason.GENERATED_OUTPUT,
            registered_image_id=intent.registered_image_id,
        )

    def schedule_user_selected_output_projection(self, workflow_id: str) -> None:
        """Project a user-selected Output route immediately through the scheduler."""

        self._projection_scheduler.request_projection(
            workflow_id,
            reason=ProjectionReason.USER_SELECTED_OUTPUT,
        )

    def remove_workflow(self, workflow_id: str) -> None:
        """Discard pending Output projection work for a removed workflow."""

        discard_workflow = getattr(self._projection_scheduler, "discard_workflow", None)
        if callable(discard_workflow):
            discard_workflow(workflow_id)

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Re-key pending Output projection work after workflow rename."""

        rename_workflow = getattr(self._projection_scheduler, "rename_workflow", None)
        if callable(rename_workflow):
            rename_workflow(old_workflow_id, new_workflow_id)

    def _connect_canvas_route_changes(self) -> None:
        """Flush generated projection when the Output canvas becomes visible."""

        route_changed = getattr(self._canvas_tabs, "canvas_activated", None)
        connect = getattr(route_changed, "connect", None)
        if callable(connect):
            connect(self._on_canvas_route_changed)

    def _on_canvas_route_changed(self, route_key: str) -> None:
        """Flush active output projection when the Output route is selected."""

        if route_key != "Output":
            return
        self._projection_scheduler.request_projection(
            self._workflow_session_service.active_workflow_id,
            reason=ProjectionReason.WORKFLOW_ACTIVATED,
        )

    def _output_canvas_is_visible(self) -> bool:
        """Return whether generated output projection should run immediately."""

        is_canvas_visible = getattr(self._canvas_tabs, "is_canvas_visible", None)
        if callable(is_canvas_visible):
            return bool(is_canvas_visible("Output"))
        return True


__all__ = [
    "OutputImagePipeline",
]
