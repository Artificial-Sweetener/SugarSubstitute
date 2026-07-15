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

"""Define generation transport contracts for queue, listen, and interrupt flows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Protocol, runtime_checkable

from substitute.application.errors import ErrorReport
from substitute.domain.common import JsonObject, WorkflowId

QueuePromptStatus = Literal["queued", "missing_prompt_id", "error"]
InterruptStatus = Literal["sent", "failed"]
ComfyQueueMutationStatus = Literal["deleted", "failed"]


@dataclass(frozen=True)
class QueuePromptResult:
    """Capture prompt queueing outcome from Comfy transport adapters."""

    status: QueuePromptStatus
    prompt_id: str | None
    payload: object | None
    error: str | None
    error_report: ErrorReport | None = None


@dataclass(frozen=True)
class InterruptResult:
    """Capture interrupt request outcome for generation stop actions."""

    status: InterruptStatus
    status_code: int | None
    error: str | None


@dataclass(frozen=True)
class ComfyQueueSnapshot:
    """Capture prompt ids currently visible in Comfy's queue."""

    running_prompt_ids: tuple[str, ...]
    pending_prompt_ids: tuple[str, ...]


@dataclass(frozen=True)
class ComfyQueueMutationResult:
    """Capture the outcome of a Comfy queue mutation request."""

    status: ComfyQueueMutationStatus
    status_code: int | None
    error: str | None


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    """Represent progress percentages for one identified generation lifecycle."""

    workflow_id: WorkflowId
    generation_run_id: str
    prompt_id: str
    client_id: str
    workflow_percent: float | None
    sampler_percent: float | None


@dataclass(frozen=True)
class ModelLoadProgressUpdate:
    """Represent model-loading telemetry emitted by Substitute BackEnd."""

    workflow_id: WorkflowId
    prompt_id: str | None
    node_id: str | None
    display_node_id: str | None
    phase: str
    state: str
    percent: float | None
    value: float | None
    maximum: float | None
    unit: str | None
    model_class: str | None
    model_name: str | None
    source_node_id: str | None
    source_input_key: str | None
    source_cube_alias: str | None
    source_workflow_node_name: str | None
    detail: str | None


@dataclass(frozen=True)
class CubeExecutionTiming:
    """Represent total executed node time attributed to one output source."""

    cube_alias: str
    source_key: str
    duration_ms: float


@dataclass(frozen=True)
class GenerationVisualIdentity:
    """Identify one generation visual event before it reaches canvas state."""

    workflow_id: WorkflowId
    generation_run_id: str
    prompt_id: str
    client_id: str
    source_key: str
    source_label: str
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None
    node_id: str | None = None
    display_node_id: str | None = None


@dataclass(frozen=True)
class GenerationExecutionTiming:
    """Represent prompt and cube timing for one completed listener run."""

    workflow_id: WorkflowId
    prompt_id: str
    job_duration_ms: float | None
    cube_timings: tuple[CubeExecutionTiming, ...] = ()


@dataclass(frozen=True)
class PreviewImageUpdate:
    """Represent a preview image payload tied to its origin workflow and source."""

    workflow_id: WorkflowId
    image: object
    generation_run_id: str | None = None
    prompt_id: str | None = None
    client_id: str | None = None
    node_id: str | None = None
    metadata_node_id: str | None = None
    display_node_id: str | None = None
    parent_node_id: str | None = None
    real_node_id: str | None = None
    source_key: str = ""
    source_label: str = ""
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None


@dataclass(frozen=True)
class OutputImageUpdate:
    """Represent a saved output image path tied to workflow and node context."""

    workflow_id: WorkflowId
    workflow_payload: JsonObject
    file_path: Path
    node_id: str
    generation_run_id: str | None = None
    prompt_id: str | None = None
    client_id: str | None = None
    display_node_id: str | None = None
    source_key: str = ""
    source_label: str = ""
    list_index: int | None = None
    artifact_width: int | None = None
    artifact_height: int | None = None
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None


@dataclass(frozen=True)
class OutputSavePlan:
    """Describe immutable output organization settings for one queued prompt."""

    output_root: Path
    path_pattern: str
    workflow_name: str
    output_run_number: int | None
    job_started_at: datetime
    seed: str = ""
    cube_numbers_by_alias: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class QueueVisualRunContext:
    """Carry Substitute visual routing facts through Backend queue metadata."""

    workflow_id: WorkflowId
    generation_run_id: str
    client_id: str
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None
    sources: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        """Return the versioned queue payload consumed by Substitute BackEnd."""

        payload: dict[str, object] = {
            "schemaVersion": 1,
            "workflowId": self.workflow_id,
            "generationRunId": self.generation_run_id,
            "clientId": self.client_id,
            "sources": {
                str(node_id): dict(source) for node_id, source in self.sources.items()
            },
        }
        scene_payload: dict[str, object] = {}
        if self.scene_run_id is not None:
            scene_payload["runId"] = self.scene_run_id
        if self.scene_key is not None:
            scene_payload["key"] = self.scene_key
        if self.scene_title is not None:
            scene_payload["title"] = self.scene_title
        if self.scene_order is not None:
            scene_payload["order"] = self.scene_order
        if self.scene_count is not None:
            scene_payload["count"] = self.scene_count
        if scene_payload:
            payload["scene"] = scene_payload
        return payload


@dataclass(frozen=True)
class ListenerFailure:
    """Represent a listener failure that occurred while awaiting completion."""

    workflow_id: WorkflowId
    generation_run_id: str
    prompt_id: str
    error: str
    detail: str | None = None
    error_report: ErrorReport | None = None


@dataclass(frozen=True)
class ListenerCompleted:
    """Represent listener completion for one queued prompt."""

    workflow_id: WorkflowId
    generation_run_id: str
    prompt_id: str


@dataclass(frozen=True)
class ListenerSessionConnectRequest:
    """Describe the pre-queue websocket session that will own one Comfy run."""

    workflow_id: WorkflowId
    generation_run_id: str
    client_id: str


@dataclass(frozen=True)
class ListenerSessionHandle:
    """Carry the connected websocket session between queueing and listener start."""

    workflow_id: WorkflowId
    generation_run_id: str
    client_id: str
    session: object


@dataclass(frozen=True)
class ListenerSessionConnectResult:
    """Capture preconnected listener websocket startup outcome."""

    connected: bool
    handle: ListenerSessionHandle | None
    error: str | None


@dataclass(frozen=True)
class ListenerStartRequest:
    """Describe the listener start payload for one queued prompt."""

    prompt_id: str
    generation_run_id: str
    client_id: str
    listener_session: ListenerSessionHandle
    output_dir: Path
    workflow_payload: JsonObject
    sugar_script: str
    workflow_id: WorkflowId
    workflow_name: str
    output_run_number: int | None = None
    output_save_plan: OutputSavePlan | None = None
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None


@dataclass
class ListenerCallbacks:
    """Define callback wiring required for websocket listener delivery."""

    on_progress: Callable[[ProgressUpdate], None]
    on_model_load_progress: Callable[[ModelLoadProgressUpdate], None]
    on_preview: Callable[[PreviewImageUpdate], None]
    on_output_image: Callable[[OutputImageUpdate], None]
    on_failed: Callable[[ListenerFailure], None]
    on_timing: Callable[[GenerationExecutionTiming], None]
    on_completed: Callable[[ListenerCompleted], None]


@dataclass(frozen=True)
class ListenerHandle:
    """Describe a started listener task tracked by application services."""

    prompt_id: str
    generation_run_id: str
    client_id: str
    workflow_id: WorkflowId
    task: object


@dataclass(frozen=True)
class ListenerStartResult:
    """Capture listener start outcome from infrastructure gateways."""

    started: bool
    handle: ListenerHandle | None
    error: str | None


@runtime_checkable
class ComfyGateway(Protocol):
    """Define generation transport operations consumed by application services."""

    def connect_listener_session(
        self,
        request: ListenerSessionConnectRequest,
    ) -> ListenerSessionConnectResult:
        """Open and negotiate a run websocket before the prompt is queued."""

    def queue_prompt(
        self,
        workflow_payload: JsonObject,
        *,
        client_id: str,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> QueuePromptResult:
        """Queue workflow payload and return prompt identifier details."""

    def start_listener(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
    ) -> ListenerStartResult:
        """Start websocket listener for one queued prompt."""

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        """Close a preconnected listener session that will not be started."""

    def interrupt(self) -> InterruptResult:
        """Request interruption of active Comfy execution."""

    def get_queue(self) -> ComfyQueueSnapshot:
        """Return Comfy running and pending prompt identifiers."""

    def delete_pending_prompt(self, prompt_id: str) -> ComfyQueueMutationResult:
        """Delete one pending prompt from Comfy's queue."""


__all__ = [
    "ComfyQueueMutationResult",
    "ComfyQueueMutationStatus",
    "ComfyQueueSnapshot",
    "ComfyGateway",
    "CubeExecutionTiming",
    "GenerationExecutionTiming",
    "GenerationVisualIdentity",
    "InterruptResult",
    "InterruptStatus",
    "ListenerCallbacks",
    "ListenerCompleted",
    "ListenerFailure",
    "ListenerHandle",
    "ListenerSessionConnectRequest",
    "ListenerSessionConnectResult",
    "ListenerSessionHandle",
    "ModelLoadProgressUpdate",
    "ListenerStartRequest",
    "ListenerStartResult",
    "OutputImageUpdate",
    "OutputSavePlan",
    "PreviewImageUpdate",
    "ProgressUpdate",
    "QueueVisualRunContext",
    "QueuePromptResult",
    "QueuePromptStatus",
]
