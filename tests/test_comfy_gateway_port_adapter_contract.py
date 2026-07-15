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

"""Contract tests for the infrastructure Comfy gateway adapter mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from substitute.application.ports import (
    ComfyQueueMutationResult,
    ComfyQueueSnapshot,
    CubeExecutionTiming,
    GenerationExecutionTiming,
    InterruptResult,
    ListenerCallbacks,
    ListenerCompleted,
    ListenerFailure,
    ListenerHandle,
    ListenerSessionConnectRequest,
    ListenerSessionHandle,
    ListenerStartRequest,
    ListenerStartResult,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    OutputSavePlan,
    PreviewImageUpdate,
    ProgressUpdate,
    QueueVisualRunContext,
    QueuePromptResult,
)
from substitute.infrastructure.comfy.gateway_adapter import (
    InfrastructureComfyGatewayAdapter,
)
from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
)
from substitute.infrastructure.comfy.prompt_gateway import (
    ComfyQueueMutationResult as InfraComfyQueueMutationResult,
    ComfyQueueSnapshot as InfraComfyQueueSnapshot,
    InterruptResult as InfraInterruptResult,
    ListenerHandle as InfraListenerHandle,
    ListenerSessionConnectRequest as InfraListenerSessionConnectRequest,
    ListenerSessionConnectResult as InfraListenerSessionConnectResult,
    ListenerStartResult as InfraListenerStartResult,
    QueuePromptResult as InfraQueuePromptResult,
)

InfraCubeExecutionTiming = CubeExecutionTiming
InfraGenerationExecutionTiming = GenerationExecutionTiming
InfraListenerCallbacks = ListenerCallbacks
InfraListenerCompleted = ListenerCompleted
InfraListenerFailure = ListenerFailure
InfraListenerSessionHandle = ListenerSessionHandle
InfraListenerStartRequest = ListenerStartRequest
InfraModelLoadProgressUpdate = ModelLoadProgressUpdate
InfraOutputImageUpdate = OutputImageUpdate
InfraOutputSavePlan = OutputSavePlan
InfraPreviewImageUpdate = PreviewImageUpdate
InfraProgressUpdate = ProgressUpdate


@dataclass
class _FakeInfraGateway:
    """Provide deterministic infrastructure gateway behavior for adapter tests."""

    queue_result: InfraQueuePromptResult
    listener_result: InfraListenerStartResult
    interrupt_result: InfraInterruptResult
    queue_snapshot: InfraComfyQueueSnapshot = InfraComfyQueueSnapshot(
        running_prompt_ids=(),
        pending_prompt_ids=(),
    )
    queue_mutation_result: InfraComfyQueueMutationResult = (
        InfraComfyQueueMutationResult(
            status="deleted",
            status_code=200,
            error=None,
        )
    )

    def __post_init__(self) -> None:
        """Initialize call capture fields used by assertions."""
        self.queue_calls: list[
            tuple[
                dict[str, object],
                str,
                str | None,
                str | None,
                QueueVisualRunContext | None,
            ]
        ] = []
        self.listener_requests: list[InfraListenerStartRequest] = []
        self.listener_callbacks: list[InfraListenerCallbacks] = []
        self.listener_session_requests: list[InfraListenerSessionConnectRequest] = []
        self.closed_listener_sessions: list[object] = []
        self.interrupt_calls = 0
        self.get_queue_calls = 0
        self.deleted_prompt_ids: list[str] = []

    def queue_prompt(
        self,
        workflow_payload: dict[str, object],
        *,
        client_id: str,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> InfraQueuePromptResult:
        """Return configured queue result while recording call inputs."""
        self.queue_calls.append(
            (workflow_payload, client_id, preview_method, sugar_script, visual_context)
        )
        return self.queue_result

    def connect_listener_session(
        self,
        request: InfraListenerSessionConnectRequest,
    ) -> InfraListenerSessionConnectResult:
        """Return a connected listener session while recording the request."""

        self.listener_session_requests.append(request)
        return InfraListenerSessionConnectResult(
            connected=True,
            handle=InfraListenerSessionHandle(
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
                session=object(),
            ),
            error=None,
        )

    def start_listener(
        self,
        request: InfraListenerStartRequest,
        callbacks: InfraListenerCallbacks,
    ) -> InfraListenerStartResult:
        """Return configured listener start result and capture bridged callbacks."""
        self.listener_requests.append(request)
        self.listener_callbacks.append(callbacks)
        return self.listener_result

    def interrupt(self) -> InfraInterruptResult:
        """Return configured interrupt result and record invocation count."""
        self.interrupt_calls += 1
        return self.interrupt_result

    def get_queue(self) -> InfraComfyQueueSnapshot:
        """Return configured queue snapshot and record invocation count."""

        self.get_queue_calls += 1
        return self.queue_snapshot

    def delete_pending_prompt(self, prompt_id: str) -> InfraComfyQueueMutationResult:
        """Return configured mutation result and record the prompt id."""

        self.deleted_prompt_ids.append(prompt_id)
        return self.queue_mutation_result

    def close_listener_session(self, handle: object) -> None:
        """Record one listener session close request."""

        self.closed_listener_sessions.append(handle)


def test_listener_preview_update_is_application_port_dto() -> None:
    """Keep preview event DTO ownership in the application port contract."""

    assert InfraPreviewImageUpdate is PreviewImageUpdate


def test_listener_model_load_update_is_application_port_dto() -> None:
    """Keep model-load event DTO ownership in the application port contract."""

    assert InfraModelLoadProgressUpdate is ModelLoadProgressUpdate


def test_listener_progress_update_is_application_port_dto() -> None:
    """Keep progress event DTO ownership in the application port contract."""

    assert InfraProgressUpdate is ProgressUpdate


def test_listener_timing_updates_are_application_port_dtos() -> None:
    """Keep listener timing DTO ownership in the application port contract."""

    assert InfraCubeExecutionTiming is CubeExecutionTiming
    assert InfraGenerationExecutionTiming is GenerationExecutionTiming


def test_listener_output_contracts_are_application_port_dtos() -> None:
    """Keep listener output DTO ownership in the application port contract."""

    assert InfraOutputImageUpdate is OutputImageUpdate
    assert InfraOutputSavePlan is OutputSavePlan


def test_listener_lifecycle_contracts_are_application_port_dtos() -> None:
    """Keep listener lifecycle DTO ownership in the application port contract."""

    assert InfraListenerFailure is ListenerFailure
    assert InfraListenerCompleted is ListenerCompleted
    assert InfraListenerSessionHandle is ListenerSessionHandle
    assert InfraListenerStartRequest is ListenerStartRequest


def test_queue_prompt_maps_infrastructure_result_to_application_port() -> None:
    """Adapter queue mapping should preserve status, prompt id, payload, and error."""
    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=False, handle=None, error="noop"
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    result: QueuePromptResult = adapter.queue_prompt(
        {"N1": {"class_type": "KSampler"}},
        client_id="client-id",
    )

    assert result == QueuePromptResult(
        status="queued",
        prompt_id="pid-1",
        payload={"prompt_id": "pid-1"},
        error=None,
    )
    assert gateway.queue_calls == [
        ({"N1": {"class_type": "KSampler"}}, "client-id", None, None, None)
    ]


def test_queue_prompt_maps_structured_error_report_to_application_port() -> None:
    """Adapter queue mapping should preserve structured error reports."""

    report = ErrorReport(
        kind=ErrorReportKind.PROMPT_VALIDATION,
        title="Prompt validation failed",
        message="Invalid prompt",
        stage="queue",
    )
    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="error",
            prompt_id=None,
            payload={"error": "bad"},
            error="Invalid prompt",
            error_report=report,
        ),
        listener_result=InfraListenerStartResult(
            started=False, handle=None, error="noop"
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    result = adapter.queue_prompt(
        {"N1": {"class_type": "KSampler"}},
        client_id="client-id",
    )

    assert result.error_report is report


def test_queue_prompt_preserves_preview_method() -> None:
    """Adapter should pass Comfy preview method metadata to infrastructure."""

    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=False, handle=None, error="noop"
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    adapter.queue_prompt(
        {"N1": {"class_type": "KSampler"}},
        client_id="client-id",
        preview_method="taesd",
        sugar_script='use "cube" as A',
    )

    assert gateway.queue_calls == [
        (
            {"N1": {"class_type": "KSampler"}},
            "client-id",
            "taesd",
            'use "cube" as A',
            None,
        )
    ]


def test_connect_listener_session_maps_request_and_handle() -> None:
    """Adapter should bridge pre-queue websocket session connection payloads."""

    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=False, handle=None, error="noop"
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    result = adapter.connect_listener_session(
        ListenerSessionConnectRequest(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-1",
        )
    )

    assert result.connected is True
    assert result.handle is not None
    assert result.handle.workflow_id == "wf-1"
    assert result.handle.generation_run_id == "run-1"
    assert result.handle.client_id == "client-1"
    assert gateway.listener_session_requests == [
        InfraListenerSessionConnectRequest(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-1",
        )
    ]


def test_start_listener_maps_callbacks_and_request_payloads() -> None:
    """Adapter should bridge listener request fields and callback event DTOs."""
    infra_handle = InfraListenerHandle(
        prompt_id="pid-1",
        generation_run_id="run-1",
        client_id="client-id",
        workflow_id="wf-1",
        task=object(),
    )
    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=True,
            handle=infra_handle,
            error=None,
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    progress_events: list[ProgressUpdate] = []
    model_load_events: list[ModelLoadProgressUpdate] = []
    preview_events: list[PreviewImageUpdate] = []
    output_events: list[OutputImageUpdate] = []
    timing_events: list[GenerationExecutionTiming] = []
    failure_events: list[ListenerFailure] = []
    completion_events: list[ListenerCompleted] = []
    callbacks = ListenerCallbacks(
        on_progress=lambda event: progress_events.append(event),
        on_model_load_progress=lambda event: model_load_events.append(event),
        on_preview=lambda event: preview_events.append(event),
        on_output_image=lambda event: output_events.append(event),
        on_failed=lambda event: failure_events.append(event),
        on_timing=lambda event: timing_events.append(event),
        on_completed=lambda event: completion_events.append(event),
    )
    request = ListenerStartRequest(
        prompt_id="pid-1",
        generation_run_id="run-1",
        client_id="client-id",
        listener_session=ListenerSessionHandle(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-id",
            session=object(),
        ),
        output_dir=Path("out"),
        workflow_payload={"N1": {"class_type": "KSampler"}},
        sugar_script='use "cube" as A',
        workflow_id="wf-1",
        workflow_name="Workflow One",
        output_run_number=12,
        output_save_plan=OutputSavePlan(
            output_root=Path("E:/outputs"),
            path_pattern="{workflow}\\{seed}_{source}",
            workflow_name="Workflow One",
            output_run_number=12,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
            seed="1234",
        ),
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
    )

    result = adapter.start_listener(request=request, callbacks=callbacks)

    assert result == ListenerStartResult(
        started=True,
        handle=ListenerHandle(
            prompt_id="pid-1",
            generation_run_id="run-1",
            client_id="client-id",
            workflow_id="wf-1",
            task=infra_handle.task,
        ),
        error=None,
    )
    assert len(gateway.listener_requests) == 1
    bridged_request = gateway.listener_requests[0]
    assert getattr(bridged_request, "prompt_id") == "pid-1"
    assert getattr(bridged_request, "generation_run_id") == "run-1"
    assert getattr(bridged_request, "workflow_id") == "wf-1"
    assert getattr(bridged_request, "workflow_name") == "Workflow One"
    assert getattr(bridged_request, "output_run_number") == 12
    bridged_save_plan = getattr(bridged_request, "output_save_plan")
    assert bridged_save_plan is not None
    assert getattr(bridged_save_plan, "seed") == "1234"
    assert getattr(bridged_request, "scene_run_id") == "run-1"
    assert getattr(bridged_request, "scene_key") == "portrait"
    assert getattr(bridged_request, "scene_title") == "Portrait"
    assert getattr(bridged_request, "scene_order") == 0
    assert getattr(bridged_request, "scene_count") == 2
    assert len(gateway.listener_callbacks) == 1
    bridged_callbacks = gateway.listener_callbacks[0]
    cast_callbacks = bridged_callbacks  # keep local name explicit for readability
    cast_callbacks.on_progress(
        InfraProgressUpdate(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-id",
            workflow_percent=25.0,
            sampler_percent=12.5,
        )
    )
    cast_callbacks.on_model_load_progress(
        InfraModelLoadProgressUpdate(
            workflow_id="wf-1",
            prompt_id="pid-1",
            node_id="24",
            display_node_id="24",
            phase="dynamic_vram_staging",
            state="running",
            percent=42.5,
            value=2048.0,
            maximum=4897.0,
            unit="mb",
            model_class="SDXL",
            model_name=None,
            source_node_id="12",
            source_input_key="ckpt_name",
            source_cube_alias="Cube",
            source_workflow_node_name="checkpoint",
            detail="2048MB of 4897MB staged",
        )
    )
    cast_callbacks.on_preview(
        InfraPreviewImageUpdate(
            workflow_id="wf-1",
            image=object(),
            generation_run_id="run-1",
            prompt_id="pid-1",
            node_id="N2",
            metadata_node_id="N2.raw",
            display_node_id="N2.display",
            parent_node_id="N2.parent",
            real_node_id="N2.real",
            source_key="wf-1:N2",
            source_label="Preview Cube",
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        )
    )
    cast_callbacks.on_output_image(
        InfraOutputImageUpdate(
            workflow_id="wf-1",
            workflow_payload={"N1": {"class_type": "KSampler"}},
            file_path=Path("out.png"),
            node_id="N1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            source_key="wf-1:N1",
            source_label="Output Cube",
            list_index=0,
            artifact_width=640,
            artifact_height=480,
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        )
    )
    cast_callbacks.on_timing(
        InfraGenerationExecutionTiming(
            workflow_id="wf-1",
            prompt_id="pid-1",
            job_duration_ms=3080.0,
            cube_timings=(
                InfraCubeExecutionTiming(
                    cube_alias="Text",
                    source_key="wf-1:N1",
                    duration_ms=900.0,
                ),
            ),
        )
    )
    cast_callbacks.on_failed(
        InfraListenerFailure(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            error="boom",
            detail="traceback",
        )
    )
    cast_callbacks.on_completed(
        InfraListenerCompleted(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )
    )

    assert progress_events == [
        ProgressUpdate(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-id",
            workflow_percent=25.0,
            sampler_percent=12.5,
        )
    ]
    assert model_load_events == [
        ModelLoadProgressUpdate(
            workflow_id="wf-1",
            prompt_id="pid-1",
            node_id="24",
            display_node_id="24",
            phase="dynamic_vram_staging",
            state="running",
            percent=42.5,
            value=2048.0,
            maximum=4897.0,
            unit="mb",
            model_class="SDXL",
            model_name=None,
            source_node_id="12",
            source_input_key="ckpt_name",
            source_cube_alias="Cube",
            source_workflow_node_name="checkpoint",
            detail="2048MB of 4897MB staged",
        )
    ]
    assert len(preview_events) == 1
    assert preview_events[0].workflow_id == "wf-1"
    assert preview_events[0].generation_run_id == "run-1"
    assert preview_events[0].prompt_id == "pid-1"
    assert preview_events[0].node_id == "N2"
    assert preview_events[0].metadata_node_id == "N2.raw"
    assert preview_events[0].display_node_id == "N2.display"
    assert preview_events[0].parent_node_id == "N2.parent"
    assert preview_events[0].real_node_id == "N2.real"
    assert preview_events[0].source_key == "wf-1:N2"
    assert preview_events[0].source_label == "Preview Cube"
    assert preview_events[0].scene_run_id == "run-1"
    assert preview_events[0].scene_key == "portrait"
    assert preview_events[0].scene_title == "Portrait"
    assert preview_events[0].scene_order == 0
    assert preview_events[0].scene_count == 2
    assert len(output_events) == 1
    assert output_events[0].node_id == "N1"
    assert output_events[0].generation_run_id == "run-1"
    assert output_events[0].prompt_id == "pid-1"
    assert output_events[0].source_key == "wf-1:N1"
    assert output_events[0].source_label == "Output Cube"
    assert output_events[0].list_index == 0
    assert output_events[0].artifact_width == 640
    assert output_events[0].artifact_height == 480
    assert output_events[0].scene_run_id == "run-1"
    assert output_events[0].scene_key == "portrait"
    assert output_events[0].scene_title == "Portrait"
    assert output_events[0].scene_order == 0
    assert output_events[0].scene_count == 2
    assert timing_events == [
        GenerationExecutionTiming(
            workflow_id="wf-1",
            prompt_id="pid-1",
            job_duration_ms=3080.0,
            cube_timings=(
                CubeExecutionTiming(
                    cube_alias="Text",
                    source_key="wf-1:N1",
                    duration_ms=900.0,
                ),
            ),
        )
    ]
    assert failure_events == [
        ListenerFailure(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            error="boom",
            detail="traceback",
        )
    ]
    assert completion_events == [
        ListenerCompleted(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )
    ]


def test_start_listener_maps_failed_infrastructure_start() -> None:
    """Adapter should map failed listener start results without creating a handle."""
    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=False,
            handle=None,
            error="listener init failed",
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    result = adapter.start_listener(
        request=ListenerStartRequest(
            prompt_id="pid-1",
            generation_run_id="run-1",
            client_id="client-id",
            listener_session=ListenerSessionHandle(
                workflow_id="wf-1",
                generation_run_id="run-1",
                client_id="client-id",
                session=object(),
            ),
            output_dir=Path("out"),
            workflow_payload={"N1": {"class_type": "KSampler"}},
            sugar_script='use "cube" as A',
            workflow_id="wf-1",
            workflow_name="Workflow One",
        ),
        callbacks=ListenerCallbacks(
            on_progress=lambda _event: None,
            on_model_load_progress=lambda _event: None,
            on_preview=lambda _event: None,
            on_output_image=lambda _event: None,
            on_failed=lambda _event: None,
            on_timing=lambda _event: None,
            on_completed=lambda _event: None,
        ),
    )

    assert result == ListenerStartResult(
        started=False,
        handle=None,
        error="listener init failed",
    )


def test_interrupt_maps_infrastructure_result_to_application_port() -> None:
    """Adapter interrupt mapping should preserve status code and error payload."""
    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=False, handle=None, error="noop"
        ),
        interrupt_result=InfraInterruptResult(
            status="failed",
            status_code=503,
            error="service unavailable",
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    result: InterruptResult = adapter.interrupt()

    assert result == InterruptResult(
        status="failed",
        status_code=503,
        error="service unavailable",
    )
    assert gateway.interrupt_calls == 1


def test_get_queue_maps_infrastructure_result_to_application_port() -> None:
    """Adapter queue inspection mapping should preserve running and pending ids."""

    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=False, handle=None, error="noop"
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
        queue_snapshot=InfraComfyQueueSnapshot(
            running_prompt_ids=("running-1",),
            pending_prompt_ids=("pending-1", "pending-2"),
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    result: ComfyQueueSnapshot = adapter.get_queue()

    assert result == ComfyQueueSnapshot(
        running_prompt_ids=("running-1",),
        pending_prompt_ids=("pending-1", "pending-2"),
    )
    assert gateway.get_queue_calls == 1


def test_delete_pending_prompt_maps_infrastructure_result_to_application_port() -> None:
    """Adapter queue delete mapping should preserve transport status details."""

    gateway = _FakeInfraGateway(
        queue_result=InfraQueuePromptResult(
            status="queued",
            prompt_id="pid-1",
            payload={"prompt_id": "pid-1"},
            error=None,
        ),
        listener_result=InfraListenerStartResult(
            started=False, handle=None, error="noop"
        ),
        interrupt_result=InfraInterruptResult(
            status="sent", status_code=200, error=None
        ),
        queue_mutation_result=InfraComfyQueueMutationResult(
            status="failed",
            status_code=409,
            error="already running",
        ),
    )
    adapter = InfrastructureComfyGatewayAdapter(gateway=gateway)

    result: ComfyQueueMutationResult = adapter.delete_pending_prompt("pending-1")

    assert result == ComfyQueueMutationResult(
        status="failed",
        status_code=409,
        error="already running",
    )
    assert gateway.deleted_prompt_ids == ["pending-1"]
