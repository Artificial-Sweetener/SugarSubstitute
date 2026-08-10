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

"""Commit presentable generated results as one durable replacement transaction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
    OutputImageRegistrationResult,
    OutputProjectionSchedulingIntent,
)
from substitute.application.workflows.output_canvas_focus_service import (
    empty_output_focus_result,
)
from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputSceneIdentity,
)
from substitute.domain.workflow import ImageMeta, WorkflowState
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.output_generated_result_service")


class OutputGeneratedResultService:
    """Replace the prior result only while committing a validated presentable image."""

    def __init__(
        self,
        *,
        image_registry: CanvasImageRegistry,
        output_state_service: OutputCanvasStateService,
        navigation_session_service: OutputNavigationSessionService,
    ) -> None:
        """Store durable Output owners used by the replacement transaction."""

        self._image_registry = image_registry
        self._output_state_service = output_state_service
        self._navigation_session_service = navigation_session_service

    def commit_generated_output(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        *,
        event: LiveFinalOutputEvent,
        image: object,
        image_meta: ImageMeta,
    ) -> OutputImageRegistrationResult:
        """Validate, replace an older result if needed, and register one final."""

        workflow_id = event.identity.workflow_id
        workflow = workflows.get(workflow_id)
        if workflow is None:
            return self._rejected_result(event, "missing_workflow")
        rejection_reason = _live_metadata_rejection_reason(event, image_meta)
        if rejection_reason is not None:
            return self._rejected_result(event, rejection_reason)

        retired_image_ids: tuple[UUID, ...] = ()
        if self._starts_new_result(workflow, image_meta):
            prune_result = self._output_state_service.clear_output_for_workflow(
                workflows,
                workflow_id,
            )
            retired_image_ids = prune_result.removed_image_ids
        self._navigation_session_service.present_session_content(
            workflows,
            workflow_id,
            _output_session_id(image_meta),
        )
        result = self._output_state_service.register_output_image(
            workflows,
            workflow_id,
            active_workflow_id,
            image,
            image_meta,
        )
        return replace(result, retired_image_ids=retired_image_ids)

    def _starts_new_result(
        self,
        workflow: WorkflowState,
        incoming: ImageMeta,
    ) -> bool:
        """Return whether no current Output belongs to the incoming result group."""

        if not workflow.output_image_uuids:
            return False
        incoming_key = _result_group_key(incoming)
        for image_id in workflow.output_image_uuids:
            existing = self._image_registry.metadata_for(image_id)
            if existing is not None and _result_group_key(existing) == incoming_key:
                return False
        return True

    @staticmethod
    def _rejected_result(
        event: LiveFinalOutputEvent,
        reason: str,
    ) -> OutputImageRegistrationResult:
        """Log and return one non-mutating live-result rejection."""

        identity = event.identity
        log_warning(
            _LOGGER,
            "Rejected live generated output before replacement",
            workflow_id=identity.workflow_id,
            generation_run_id=identity.generation_run_id,
            prompt_id=identity.prompt_id,
            client_id=identity.client_id,
            node_id=event.node_id,
            source_key=identity.source_key,
            reason=reason,
        )
        return OutputImageRegistrationResult(
            workflow_id=identity.workflow_id,
            image_id=None,
            registered=False,
            focus_change=empty_output_focus_result(),
            preview_close_identity=None,
            projection_intent=OutputProjectionSchedulingIntent.none(
                identity.workflow_id
            ),
        )


def _result_group_key(image_meta: ImageMeta) -> tuple[str, str]:
    """Return the overall result identity shared by scenes in one scene run."""

    if image_meta.scene_run_id:
        return "scene", image_meta.scene_run_id
    return "generation", image_meta.generation_run_id


def _output_session_id(image_meta: ImageMeta) -> str:
    """Return the generation-session identity carried by Output metadata."""

    return image_meta.scene_run_id or image_meta.generation_run_id


def _live_metadata_rejection_reason(
    event: LiveFinalOutputEvent,
    image_meta: ImageMeta,
) -> str | None:
    """Return why prepared metadata no longer matches a live final event."""

    if image_meta.source_key != event.identity.source_key:
        return "source_key_mismatch"
    if image_meta.source_label != event.identity.source_label:
        return "source_label_mismatch"
    if image_meta.prompt_id != event.identity.prompt_id:
        return "prompt_id_mismatch"
    if image_meta.client_id != event.identity.client_id:
        return "client_id_mismatch"
    if image_meta.generation_run_id != event.identity.generation_run_id:
        return "generation_run_id_mismatch"
    if image_meta.node_id != event.node_id:
        return "node_id_mismatch"
    if image_meta.list_index != event.position.list_index:
        return "list_index_mismatch"
    if (image_meta.batch_index or 0) != event.position.batch_index:
        return "batch_index_mismatch"
    if image_meta.width != event.artifact_width:
        return "artifact_width_mismatch"
    if image_meta.height != event.artifact_height:
        return "artifact_height_mismatch"
    if image_meta.path and (
        event.file_path is None or Path(image_meta.path) != event.file_path
    ):
        return "file_path_mismatch"
    scene = event.identity.scene
    if isinstance(scene, OutputSceneIdentity):
        if (
            image_meta.scene_run_id != scene.run_id
            or image_meta.scene_key != scene.key
            or image_meta.scene_title != scene.title
            or image_meta.scene_order != scene.order
            or image_meta.scene_count != scene.count
        ):
            return "scene_identity_mismatch"
        return None
    if (
        image_meta.scene_run_id
        or image_meta.scene_key
        or image_meta.scene_title
        or image_meta.scene_order is not None
        or image_meta.scene_count is not None
    ):
        return "scene_identity_mismatch"
    return None


__all__ = ["OutputGeneratedResultService"]
