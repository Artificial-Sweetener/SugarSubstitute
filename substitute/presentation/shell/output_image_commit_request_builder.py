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

"""Build immutable output-image commit requests from transport events."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from substitute.application.cubes import cube_alias_body
from substitute.application.ports import OutputImageUpdate
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputSceneIdentity,
)
from substitute.domain.generation import OutputResultPosition
from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.output_image_commit_request_builder")


class WorkflowSessionProtocol(Protocol):
    """Describe workflow state needed while building commit requests."""

    def get_workflow(self, workflow_id: str) -> object | None:
        """Return workflow state for one workflow id."""


class CanvasIoMetadataProtocol(Protocol):
    """Describe canvas metadata resolution used by commit requests."""

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


class OutputImageCommitRequestBuilder:
    """Own transport validation and GUI-thread commit-request construction."""

    def __init__(
        self,
        *,
        workflow_session_service: WorkflowSessionProtocol,
        canvas_io_service: CanvasIoMetadataProtocol,
        generation_timing_lookup: GenerationTimingLookupProtocol | None = None,
    ) -> None:
        """Store the read-only collaborators used to enrich output metadata."""

        self._workflow_session_service = workflow_session_service
        self._canvas_io_service = canvas_io_service
        self._generation_timing_lookup = generation_timing_lookup

    def build_strict_update(
        self,
        output_update: OutputImageUpdate,
    ) -> OutputImageCommitRequest | None:
        """Validate and build one strict live-output request."""

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
        return self.build_live_event(live_event)

    def build_live_event(
        self,
        live_event: LiveFinalOutputEvent,
    ) -> OutputImageCommitRequest:
        """Build one strict immutable request from a validated live event."""

        return self._build(
            workflow_id=live_event.identity.workflow_id,
            workflow_payload=live_event.workflow_payload,
            image_bytes=live_event.image_bytes,
            file_path=live_event.file_path,
            node_id=live_event.node_id,
            source_key=live_event.identity.source_key,
            source_label=live_event.identity.source_label,
            generation_run_id=live_event.identity.generation_run_id,
            prompt_id=live_event.identity.prompt_id,
            client_id=live_event.identity.client_id,
            position=live_event.position,
            artifact_width=live_event.artifact_width,
            artifact_height=live_event.artifact_height,
            scene_fields=_scene_fields(live_event),
            live_event=live_event,
            allow_source_fallback=False,
        )

    def build_legacy_update(
        self,
        output_update: OutputImageUpdate,
    ) -> OutputImageCommitRequest:
        """Build an explicit non-live request with legacy source fallback."""

        return self._build(
            workflow_id=output_update.workflow_id,
            workflow_payload=output_update.workflow_payload,
            image_bytes=output_update.image_bytes,
            file_path=output_update.file_path,
            node_id=output_update.node_id,
            source_key=output_update.source_key,
            source_label=output_update.source_label,
            generation_run_id=output_update.generation_run_id,
            prompt_id=output_update.prompt_id,
            client_id=output_update.client_id,
            position=_position_from_update(output_update),
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

    def _build(
        self,
        *,
        workflow_id: str,
        workflow_payload: object,
        image_bytes: bytes,
        file_path: Path | None,
        node_id: str,
        source_key: str,
        source_label: str,
        generation_run_id: str | None,
        prompt_id: str | None,
        client_id: str | None,
        position: OutputResultPosition | None,
        artifact_width: int | None,
        artifact_height: int | None,
        scene_fields: tuple[str | None, str | None, str | None, int | None, int | None],
        live_event: LiveFinalOutputEvent | None,
        allow_source_fallback: bool,
    ) -> OutputImageCommitRequest:
        """Resolve presentation metadata and return one narrow request."""

        payload: Mapping[str, object] = (
            workflow_payload if isinstance(workflow_payload, dict) else {}
        )
        node_data = payload.get(node_id, {})
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
        scene_run_id, scene_key, scene_title, scene_order, scene_count = scene_fields
        return OutputImageCommitRequest(
            workflow_id=workflow_id,
            image_bytes=image_bytes,
            file_path=file_path,
            node_id=node_id,
            node_meta_title=node_meta_title,
            workflow_name=workflow_name,
            source_key=source_key,
            source_label=source_label,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
            position=position,
            artifact_width=artifact_width,
            artifact_height=artifact_height,
            live_event=live_event,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
            cube_execution_duration_ms=self._cube_execution_duration_ms(
                workflow_id=workflow_id,
                source_key=source_key,
                cube_alias=source_label,
            ),
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


def _live_final_rejection_reason(output_update: OutputImageUpdate) -> str:
    """Return a compact reason for strict live final update rejection."""

    required_text = (
        (output_update.generation_run_id, "missing_generation_run_id"),
        (output_update.prompt_id, "missing_prompt_id"),
        (output_update.client_id, "missing_client_id"),
        (output_update.source_key, "missing_source_key"),
        (output_update.source_label, "missing_source_label"),
        (output_update.node_id, "missing_node_id"),
    )
    for text_value, reason in required_text:
        if not text_value:
            return reason
    for coordinate, missing, invalid, negative in (
        (
            output_update.list_index,
            "missing_list_index",
            "non_integer_list_index",
            "negative_list_index",
        ),
        (
            output_update.batch_index,
            "missing_batch_index",
            "non_integer_batch_index",
            "negative_batch_index",
        ),
    ):
        if coordinate is None:
            return missing
        if type(coordinate) is not int:
            return invalid
        if coordinate < 0:
            return negative
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


def _position_from_update(
    output_update: OutputImageUpdate,
) -> OutputResultPosition | None:
    """Return a typed result position when both transport coordinates exist."""

    if (
        type(output_update.list_index) is not int
        or output_update.list_index < 0
        or type(output_update.batch_index) is not int
        or output_update.batch_index < 0
    ):
        return None
    return OutputResultPosition(
        list_index=output_update.list_index,
        batch_index=output_update.batch_index,
    )


def _scene_fields(
    event: LiveFinalOutputEvent,
) -> tuple[str | None, str | None, str | None, int | None, int | None]:
    """Return request scene fields from a strict live final event."""

    scene = event.identity.scene
    if isinstance(scene, OutputSceneIdentity):
        return scene.run_id, scene.key, scene.title, scene.order, scene.count
    return None, None, None, None, None


__all__ = [
    "CanvasIoMetadataProtocol",
    "GenerationTimingLookupProtocol",
    "OutputImageCommitRequestBuilder",
    "WorkflowSessionProtocol",
]
