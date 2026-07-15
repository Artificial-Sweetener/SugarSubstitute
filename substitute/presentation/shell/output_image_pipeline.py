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
from pathlib import Path
from typing import Protocol
from uuid import UUID

from PySide6.QtCore import QObject

from substitute.application.cubes import cube_alias_body
from substitute.application.ports import OutputImageUpdate
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputSceneIdentity,
)
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
from substitute.presentation.shell.output_image_commit_queue import (
    PreparedOutputCommitQueue,
)
from substitute.presentation.shell.output_image_preparation_dispatcher import (
    OutputImagePreparationDispatcher,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.output_image_pipeline")


class WorkflowSessionProtocol(Protocol):
    """Describe workflow session access needed for output request construction."""

    active_workflow_id: str
    workflows: Mapping[str, object]

    def get_workflow(self, workflow_id: str) -> object | None:
        """Return workflow state for one workflow id."""


class CanvasIoMetadataProtocol(Protocol):
    """Describe metadata helpers needed by the output pipeline."""

    def load_output_image(self, path: Path) -> object | None:
        """Load one output image from disk."""

    def resolve_node_meta_title(self, node_data: object) -> str:
        """Resolve one workflow node title."""

    def resolve_workflow_label(self, workflow_metadata: object) -> str:
        """Resolve one workflow label."""


class GenerationTimingLookupProtocol(Protocol):
    """Describe read-only generation timing lookup used for output metadata."""

    def cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str = "",
        cube_alias: str = "",
    ) -> float | None:
        """Return the latest known cube duration for one output source."""


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
        self._canvas_io_service = canvas_io_service
        self._output_commit_handler = output_commit_handler
        self._output_canvas_projection_coordinator = (
            output_canvas_projection_coordinator
        )
        self._canvas_tabs = canvas_tabs
        self._generation_timing_lookup = generation_timing_lookup
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

        live_event = LiveFinalOutputEvent.from_update(output_update)
        if live_event is None:
            log_warning(
                _LOGGER,
                "Rejected live final output before commit request construction",
                workflow_id=output_update.workflow_id,
                generation_run_id=output_update.generation_run_id,
                prompt_id=output_update.prompt_id,
                client_id=output_update.client_id,
                node_id=output_update.node_id,
                source_key=output_update.source_key,
                reason=_live_final_rejection_reason(output_update),
            )
            return None
        return self.build_live_commit_request(live_event)

    def build_live_commit_request(
        self,
        live_event: LiveFinalOutputEvent,
    ) -> OutputImageCommitRequest:
        """Build a strict immutable live commit request on the GUI thread."""

        return self._build_commit_request(
            workflow_id=live_event.identity.workflow_id,
            workflow_payload=live_event.workflow_payload,
            file_path=live_event.file_path,
            node_id=live_event.node_id,
            source_key=live_event.identity.source_key,
            source_label=live_event.identity.source_label,
            generation_run_id=live_event.identity.generation_run_id,
            prompt_id=live_event.identity.prompt_id,
            client_id=live_event.identity.client_id,
            list_index=live_event.list_index,
            artifact_width=live_event.artifact_width,
            artifact_height=live_event.artifact_height,
            scene_fields=_scene_fields(live_event),
            live_event=live_event,
            allow_source_fallback=False,
        )

    def build_legacy_commit_request(
        self,
        output_update: OutputImageUpdate,
    ) -> OutputImageCommitRequest:
        """Build a non-live commit request that preserves legacy fallback routing."""

        return self._build_commit_request(
            workflow_id=output_update.workflow_id,
            workflow_payload=output_update.workflow_payload,
            file_path=output_update.file_path,
            node_id=output_update.node_id,
            source_key=output_update.source_key,
            source_label=output_update.source_label,
            generation_run_id=output_update.generation_run_id,
            prompt_id=output_update.prompt_id,
            client_id=output_update.client_id,
            list_index=output_update.list_index,
            artifact_width=output_update.artifact_width,
            artifact_height=output_update.artifact_height,
            scene_fields=(
                output_update.scene_run_id,
                output_update.scene_key,
                output_update.scene_title,
                output_update.scene_order,
                output_update.scene_count,
            ),
            live_event=None,
            allow_source_fallback=True,
        )

    def _build_commit_request(
        self,
        *,
        workflow_id: str,
        workflow_payload: object,
        file_path: Path,
        node_id: str,
        source_key: str,
        source_label: str,
        generation_run_id: str | None,
        prompt_id: str | None,
        client_id: str | None,
        list_index: int | None,
        artifact_width: int | None,
        artifact_height: int | None,
        scene_fields: tuple[str | None, str | None, str | None, int | None, int | None],
        live_event: LiveFinalOutputEvent | None,
        allow_source_fallback: bool,
    ) -> OutputImageCommitRequest:
        """Build a narrow immutable commit request on the GUI thread."""

        if not isinstance(workflow_payload, dict):
            workflow_payload = {}
        node_data = workflow_payload.get(node_id, {})
        if not isinstance(node_data, dict):
            node_data = {}
        node_meta_title = self._canvas_io_service.resolve_node_meta_title(node_data)
        workflow_state = self._workflow_session_service.get_workflow(workflow_id)
        workflow_metadata = getattr(workflow_state, "metadata", {})
        if not isinstance(workflow_metadata, dict):
            workflow_metadata = {}
        workflow_name = self._canvas_io_service.resolve_workflow_label(
            workflow_metadata
        )
        fallback_source_label = cube_alias_body(
            node_meta_title.split(".", 1)[0] if node_meta_title else node_id
        )
        if allow_source_fallback:
            source_label = source_label or fallback_source_label
            source_key = source_key or f"{workflow_id}:{node_id}"
        cube_duration_ms = self._cube_execution_duration_ms(
            workflow_id=workflow_id,
            source_key=source_key,
            cube_alias=source_label,
        )
        scene_run_id, scene_key, scene_title, scene_order, scene_count = scene_fields
        return OutputImageCommitRequest(
            workflow_id=workflow_id,
            file_path=file_path,
            node_id=node_id,
            node_meta_title=node_meta_title,
            workflow_name=workflow_name,
            source_key=source_key,
            source_label=source_label,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
            list_index=list_index,
            artifact_width=artifact_width,
            artifact_height=artifact_height,
            live_event=live_event,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
            cube_execution_duration_ms=cube_duration_ms,
        )

    def _cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str,
        cube_alias: str,
    ) -> float | None:
        """Return known cube timing for one output commit request."""

        if self._generation_timing_lookup is None:
            return None
        return self._generation_timing_lookup.cube_execution_duration_ms(
            workflow_id=workflow_id,
            source_key=source_key,
            cube_alias=cube_alias,
        )

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


def _live_final_rejection_reason(output_update: OutputImageUpdate) -> str:
    """Return a compact reason for strict live final update rejection."""

    if not output_update.generation_run_id:
        return "missing_generation_run_id"
    if not output_update.prompt_id:
        return "missing_prompt_id"
    if not output_update.client_id:
        return "missing_client_id"
    if not output_update.source_key:
        return "missing_source_key"
    if not output_update.source_label:
        return "missing_source_label"
    if not output_update.node_id:
        return "missing_node_id"
    if output_update.list_index is None:
        return "missing_list_index"
    if type(output_update.list_index) is not int:
        return "non_integer_list_index"
    if output_update.list_index < 0:
        return "negative_list_index"
    if (
        type(output_update.artifact_width) is not int
        or output_update.artifact_width <= 0
    ):
        return "missing_artifact_width"
    if (
        type(output_update.artifact_height) is not int
        or output_update.artifact_height <= 0
    ):
        return "missing_artifact_height"
    return "partial_scene_identity"


def _scene_fields(
    event: LiveFinalOutputEvent,
) -> tuple[str | None, str | None, str | None, int | None, int | None]:
    """Return request scene fields from a strict live final event."""

    scene = event.identity.scene
    if isinstance(scene, OutputSceneIdentity):
        return scene.run_id, scene.key, scene.title, scene.order, scene.count
    return None, None, None, None, None
