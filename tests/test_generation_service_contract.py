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

"""Characterization tests for Phase 7 generation-service orchestration behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.application.generation import (
    ComfyAssetStagingResult,
    GenerationCallbacks,
    GenerationRequest,
    GenerationService,
    PreparedGenerationRequest,
)
from substitute.application.ports import (
    InterruptResult,
    ListenerCallbacks,
    ListenerHandle,
    ListenerSessionConnectRequest,
    ListenerSessionConnectResult,
    ListenerSessionHandle,
    ListenerStartRequest,
    ListenerStartResult,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
    QueueVisualRunContext,
    QueuePromptResult,
)
from substitute.domain.generation import AssetStagingFailure


@dataclass
class _CallbackRecorder:
    """Collect callback invocations for deterministic assertions."""

    cleared: list[str]
    outputs: list[OutputImageUpdate]
    previews: list[PreviewImageUpdate]
    progress: list[ProgressUpdate]
    failures: list[object]
    run_started: list[object]


class _FakeRecipeIoService:
    """Provide deterministic recipe serialization for generation service tests."""

    def __init__(self) -> None:
        """Initialize call capture for serialization assertions."""

        self.calls: list[dict[str, object]] = []

    def serialize_workflow_to_sugar_script(
        self,
        _workflow: object,
        *,
        enabled_node_keys_by_alias: object | None = None,
        disabled_node_keys_by_alias: object | None = None,
    ) -> str:
        """Return deterministic recipe text while recording disabled-node input."""

        self.calls.append(
            {
                "enabled_node_keys_by_alias": enabled_node_keys_by_alias,
                "disabled_node_keys_by_alias": disabled_node_keys_by_alias,
            }
        )
        return 'use "cube" as A'


class _FakeWorkflowExportService:
    """Provide deterministic workflow payload compilation behavior."""

    def __init__(self, workflow_payload: dict[str, object]) -> None:
        self.workflow_payload = workflow_payload
        self.calls: list[dict[str, object]] = []

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
        workflow: object | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "sugar_script_text": sugar_script_text,
                "output_dir": output_dir,
                "workflow": workflow,
            }
        )
        return self.workflow_payload


class _FakeGateway:
    """Provide queue/listener/interrupt behavior with deterministic recording."""

    def __init__(
        self,
        *,
        queue_results: list[QueuePromptResult],
        listener_start_results: list[ListenerStartResult] | None = None,
        interrupt_result: InterruptResult | None = None,
    ) -> None:
        self.queue_results = list(queue_results)
        self.listener_start_results = list(listener_start_results or [])
        self.interrupt_result = interrupt_result or InterruptResult(
            status="sent",
            status_code=200,
            error=None,
        )
        self.queue_calls: list[
            tuple[
                dict[str, object],
                str,
                str | None,
                str | None,
                QueueVisualRunContext | None,
            ]
        ] = []
        self.connect_calls: list[ListenerSessionConnectRequest] = []
        self.closed_sessions: list[ListenerSessionHandle] = []
        self.listener_requests: list[ListenerStartRequest] = []
        self.listener_callbacks: list[ListenerCallbacks] = []
        self.call_order: list[str] = []

    def connect_listener_session(
        self,
        request: ListenerSessionConnectRequest,
    ) -> ListenerSessionConnectResult:
        self.connect_calls.append(request)
        self.call_order.append("connect")
        return ListenerSessionConnectResult(
            connected=True,
            handle=ListenerSessionHandle(
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
                session=SimpleNamespace(),
            ),
            error=None,
        )

    def queue_prompt(
        self,
        workflow_payload: dict[str, object],
        *,
        client_id: str,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> QueuePromptResult:
        self.call_order.append("queue")
        self.queue_calls.append(
            (workflow_payload, client_id, preview_method, sugar_script, visual_context)
        )
        if self.queue_results:
            return self.queue_results.pop(0)
        return QueuePromptResult(
            status="missing_prompt_id",
            prompt_id=None,
            payload=None,
            error=None,
        )

    def start_listener(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
    ) -> ListenerStartResult:
        self.call_order.append("start")
        self.listener_requests.append(request)
        self.listener_callbacks.append(callbacks)
        if self.listener_start_results:
            return self.listener_start_results.pop(0)
        handle = ListenerHandle(
            prompt_id=request.prompt_id,
            generation_run_id=request.generation_run_id,
            client_id=request.client_id,
            workflow_id=request.workflow_id,
            task=SimpleNamespace(),
        )
        return ListenerStartResult(started=True, handle=handle, error=None)

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        self.call_order.append("close")
        self.closed_sessions.append(handle)

    def interrupt(self) -> InterruptResult:
        return self.interrupt_result


class _FakeAssetStagingService:
    """Provide deterministic generation asset staging behavior."""

    def __init__(self, result: ComfyAssetStagingResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def stage_payload(
        self,
        *,
        workflow_payload: dict[str, object],
        workflow_id: str,
        workflow_name: str,
        workflow: object | None = None,
    ) -> ComfyAssetStagingResult:
        self.calls.append(
            {
                "workflow_payload": workflow_payload,
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "workflow": workflow,
            }
        )
        return self.result


def _build_generation_callbacks(recorder: _CallbackRecorder) -> GenerationCallbacks:
    """Create callback wiring that appends events into recorder lists."""
    return GenerationCallbacks(
        randomize_seeds=lambda: None,
        clear_output=lambda workflow_id: recorder.cleared.append(workflow_id),
        on_run_started=lambda event: recorder.run_started.append(event),
        on_progress=lambda event: recorder.progress.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda event: recorder.previews.append(event),
        on_output_image=lambda event: recorder.outputs.append(event),
        on_failure=lambda failure: recorder.failures.append(failure),
        on_timing=lambda _event: None,
    )


def _build_workflow() -> object:
    """Create minimal workflow state required by generation request."""
    return SimpleNamespace(stack_order=["A"], cubes={}, global_overrides={})


def test_run_single_generation_happy_path_queues_and_starts_listener() -> None:
    """Single generation should queue prompt and defer clear until first visual."""
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    workflow_payload = {"N1": {"class_type": "KSampler"}}
    workflow_export_service = _FakeWorkflowExportService(workflow_payload)
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=workflow_export_service,
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    assert result.prompt_id == "pid-1"
    assert recorder.cleared == []
    assert fake_gateway.call_order == ["connect", "queue", "start"]
    assert len(fake_gateway.connect_calls) == 1
    run_client_id = fake_gateway.connect_calls[0].client_id
    assert run_client_id.startswith("substitute:")
    assert len(fake_gateway.queue_calls) == 1
    queued_payload, queued_client_id, preview_method, sugar_script, visual_context = (
        fake_gateway.queue_calls[0]
    )
    assert queued_payload == workflow_payload
    assert queued_client_id == run_client_id
    assert preview_method == "latent2rgb"
    assert sugar_script == 'use "cube" as A'
    assert visual_context is not None
    assert visual_context.workflow_id == "wf-1"
    assert visual_context.client_id == run_client_id
    assert visual_context.sources["N1"]["sourceKey"] == "wf-1:N1"
    assert len(fake_gateway.listener_requests) == 1
    listener_request = fake_gateway.listener_requests[0]
    assert listener_request.workflow_id == "wf-1"
    assert listener_request.workflow_name == "Workflow 1"
    assert listener_request.prompt_id == "pid-1"
    assert listener_request.generation_run_id == (
        fake_gateway.connect_calls[0].generation_run_id
    )
    assert listener_request.client_id == run_client_id
    assert listener_request.listener_session.client_id == run_client_id
    assert len(recorder.run_started) == 1
    assert getattr(recorder.run_started[0], "client_id") == run_client_id
    assert getattr(recorder.run_started[0], "prompt_id") == "pid-1"
    assert workflow_export_service.calls[0]["output_dir"] == (
        Path.cwd() / "user" / "projects"
    )
    assert len(service.active_listener_handles) == 1

    fake_gateway.listener_callbacks[0].on_preview(
        PreviewImageUpdate(
            workflow_id="wf-1",
            image=object(),
            generation_run_id=listener_request.generation_run_id,
            prompt_id="pid-1",
        )
    )

    assert recorder.cleared == ["wf-1"]
    assert len(recorder.previews) == 1


def test_run_single_generation_passes_activation_overrides_to_serializer() -> None:
    """Generation should serialize workflow snapshots with activation overrides."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    recipe_io_service = _FakeRecipeIoService()
    service = GenerationService(
        recipe_io_service=recipe_io_service,
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
            enabled_node_keys_by_alias={"Upscale": ("load_anima",)},
            disabled_node_keys_by_alias={"Upscale": ("checkpoint",)},
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert recipe_io_service.calls == [
        {
            "enabled_node_keys_by_alias": {"Upscale": ("load_anima",)},
            "disabled_node_keys_by_alias": {"Upscale": ("checkpoint",)},
        }
    ]


def test_run_prepared_generation_passes_reserved_output_number_to_listener() -> None:
    """Prepared queue dispatch should pass reserved output number to listener start."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='use "cube" as A',
            output_run_number=12,
            output_job_started_at=datetime(2026, 5, 12, 0, 0),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    assert fake_gateway.listener_requests[0].output_run_number == 12
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.output_run_number == 12
    assert save_plan.job_started_at == datetime(2026, 5, 12, 0, 0)
    assert save_plan.path_pattern == "{date}\\{run}_{cube#}_{workflow}_{source}"
    assert save_plan.workflow_name == "Workflow 1"


def test_run_prepared_generation_output_save_plan_prefers_global_seed() -> None:
    """Output save plan seed should prefer the prepared Sugar global override."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler", "inputs": {"seed": 999}}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='use "cube" as A\nset *.*.seed = 1234\n',
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.seed == "1234"


def test_run_prepared_generation_output_save_plan_numbers_cubes_from_script() -> None:
    """Prepared SugarScript dispatch should preserve cube order for output names."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text=(
                'use "cube" as "Text to Image"\nuse "cube" as "Diffusion Upscale"\n'
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.cube_numbers_by_alias["Text to Image"] == 1
    assert save_plan.cube_numbers_by_alias["Diffusion Upscale"] == 2


def test_run_prepared_generation_output_save_plan_skips_bypassed_script_cubes() -> None:
    """Prepared SugarScript dispatch should number only active cubes."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text=(
                'use "cube" as A\n'
                '# bypass use "cube" as B\n'
                'use "cube" as C\n'
                "connect A.output.image to C.input.image\n"
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.cube_numbers_by_alias["A"] == 1
    assert "B" not in save_plan.cube_numbers_by_alias
    assert save_plan.cube_numbers_by_alias["C"] == 2


def test_run_prepared_generation_output_save_plan_skips_bypassed_workflow_cubes() -> (
    None
):
    """Live workflow cube numbering should use active execution projection."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='use "cube" as A\nuse "cube" as C\n',
            workflow=SimpleNamespace(
                stack_order=["A", "B", "C"],
                cubes={
                    "A": SimpleNamespace(bypassed=False),
                    "B": SimpleNamespace(bypassed=True),
                    "C": SimpleNamespace(bypassed=False),
                },
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.cube_numbers_by_alias["A"] == 1
    assert "B" not in save_plan.cube_numbers_by_alias
    assert save_plan.cube_numbers_by_alias["C"] == 2


def test_run_prepared_generation_fails_when_all_cubes_are_bypassed() -> None:
    """A prepared workflow with no active cubes should fail before backend compile."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    export_service = _FakeWorkflowExportService({"N1": {"class_type": "KSampler"}})
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=export_service,
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='# bypass use "cube" as Muted\n',
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert export_service.calls == []
    assert "no active cubes" in recorder.failures[0].message


def test_run_prepared_generation_output_save_plan_uses_staged_workflow_seed() -> None:
    """Workflow seed fallback should be resolved after asset staging."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    compiled_payload = {"N1": {"class_type": "KSampler", "inputs": {"seed": 111}}}
    staged_payload = {"N1": {"class_type": "KSampler", "inputs": {"seed": 222}}}
    asset_staging_service = _FakeAssetStagingService(
        ComfyAssetStagingResult(
            workflow_payload=staged_payload,
            staged_assets=(),
            failures=(),
        )
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(compiled_payload),
        comfy_gateway=fake_gateway,
        asset_staging_service=asset_staging_service,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='use "cube" as A\n',
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.seed == "222"


def test_run_prepared_generation_passes_scene_metadata_to_listener() -> None:
    """Prepared scene metadata should reach the listener startup request."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1 - Portrait",
            sugar_script_text='use "cube" as A',
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    listener_request = fake_gateway.listener_requests[0]
    assert listener_request.scene_run_id == "run-1"
    assert listener_request.scene_key == "portrait"
    assert listener_request.scene_title == "Portrait"
    assert listener_request.scene_order == 0
    assert listener_request.scene_count == 2


def test_run_single_generation_queue_failure_calls_failure_callback() -> None:
    """Missing prompt id should fail queue stage and skip listener startup."""
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="missing_prompt_id",
                prompt_id=None,
                payload={"status": "ok"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert result.failure is not None
    assert result.failure.stage == "queue"
    assert result.failure.message == "queue_prompt did not return prompt_id"
    assert recorder.cleared == []
    assert len(recorder.failures) == 1
    assert fake_gateway.listener_requests == []
    assert fake_gateway.call_order == ["connect", "queue", "close"]
    assert len(fake_gateway.closed_sessions) == 1


def test_run_single_generation_queue_failure_uses_gateway_error() -> None:
    """Missing prompt id should preserve gateway error detail when present."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="missing_prompt_id",
                prompt_id=None,
                payload={"status": "error"},
                error="HTTP 500 from /prompt",
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.failure is not None
    assert result.failure.message == "HTTP 500 from /prompt"
    assert recorder.failures[0] == result.failure
    assert fake_gateway.call_order == ["connect", "queue", "close"]


def test_run_single_generation_queue_failure_preserves_error_report() -> None:
    """Queue failures should carry structured reports into generation failures."""

    report = ErrorReport(
        kind=ErrorReportKind.PROMPT_VALIDATION,
        title="Prompt validation failed",
        message="Invalid prompt",
        stage="queue",
    )
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="error",
                prompt_id=None,
                payload={"error": "bad"},
                error="Invalid prompt",
                error_report=report,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.failure is not None
    assert result.failure.error_report is report
    assert recorder.failures[0] == result.failure
    assert fake_gateway.call_order == ["connect", "queue", "close"]


def test_run_single_generation_queues_staged_payload_when_staging_is_configured() -> (
    None
):
    """Generation should queue target-specific staged payload, not authoring payload."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    authoring_payload = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "E:/input.png"}}
    }
    staged_payload = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "substitute/wf/input.png"}}
    }
    asset_staging_service = _FakeAssetStagingService(
        ComfyAssetStagingResult(
            workflow_payload=staged_payload,
            staged_assets=(),
            failures=(),
        )
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(authoring_payload),
        comfy_gateway=fake_gateway,
        asset_staging_service=asset_staging_service,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    assert asset_staging_service.calls[0]["workflow_payload"] == authoring_payload
    run_client_id = fake_gateway.connect_calls[0].client_id
    assert len(fake_gateway.queue_calls) == 1
    queued_payload, queued_client_id, preview_method, sugar_script, visual_context = (
        fake_gateway.queue_calls[0]
    )
    assert queued_payload == staged_payload
    assert queued_client_id == run_client_id
    assert preview_method == "latent2rgb"
    assert sugar_script == 'use "cube" as A'
    assert visual_context is not None
    assert visual_context.sources["1"]["sourceKey"] == "wf-1:1"


def test_run_single_generation_queues_selected_image_not_cube_default() -> None:
    """Generation should queue the selected inpaint image value after staging."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    default_image = "00282-3430329909-ad-before.png"
    selected_image = "E:/images/selected.png"
    staged_image = "substitute/wf-1/selected.png"
    asset_staging_service = _FakeAssetStagingService(
        ComfyAssetStagingResult(
            workflow_payload={
                "1": {
                    "class_type": "LoadImage",
                    "inputs": {"image": staged_image},
                }
            },
            staged_assets=(),
            failures=(),
        )
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {
                "1": {
                    "class_type": "LoadImage",
                    "inputs": {"image": selected_image},
                }
            }
        ),
        comfy_gateway=fake_gateway,
        asset_staging_service=asset_staging_service,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    queued_payload = fake_gateway.queue_calls[0][0]
    assert queued_payload["1"]["inputs"]["image"] == staged_image
    assert queued_payload["1"]["inputs"]["image"] != default_image


def test_run_single_generation_staging_failure_skips_queue() -> None:
    """Generation should fail before queueing when required assets cannot be staged."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-ignored",
                payload={"prompt_id": "pid-ignored"},
                error=None,
            )
        ]
    )
    asset_staging_service = _FakeAssetStagingService(
        ComfyAssetStagingResult(
            workflow_payload={"1": {"class_type": "LoadImage"}},
            staged_assets=(),
            failures=(
                AssetStagingFailure(
                    node_id="1",
                    node_class="LoadImage",
                    input_name="image",
                    source_value="E:/missing.png",
                    message="Referenced local image file does not exist.",
                ),
            ),
        )
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"1": {"class_type": "LoadImage"}}
        ),
        comfy_gateway=fake_gateway,
        asset_staging_service=asset_staging_service,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert result.failure is not None
    assert result.failure.stage == "stage"
    assert fake_gateway.queue_calls == []


def test_run_single_generation_rejects_unresolved_uuid_wrapper_nodes() -> None:
    """UUID wrapper class_type values should fail build stage before queueing."""
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-ignored",
                payload={"prompt_id": "pid-ignored"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"1": {"class_type": "94f725d5-39bf-4060-be68-f573214a2055"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert result.failure is not None
    assert result.failure.stage == "build"
    assert len(recorder.failures) == 1
    assert fake_gateway.queue_calls == []


def test_run_single_generation_rejects_wrapped_unresolved_uuid_nodes() -> None:
    """UUID wrapper validation should inspect wrapped executable prompt nodes."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-ignored",
                payload={"prompt_id": "pid-ignored"},
                error=None,
            )
        ]
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {
                "prompt": {"1": {"class_type": "94f725d5-39bf-4060-be68-f573214a2055"}},
                "workflow": {"nodes": []},
            }
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert result.failure is not None
    assert result.failure.stage == "build"
    assert fake_gateway.queue_calls == []


def test_output_callback_preserves_origin_workflow_id_after_listener_emit() -> None:
    """Output callback payload should retain origin workflow id from start request."""
    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    payload = {"N1": {"class_type": "KSampler"}}
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(payload),
        comfy_gateway=fake_gateway,
    )

    service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-origin",
            workflow_name="Workflow Origin",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )
    listener_request = fake_gateway.listener_requests[0]
    fake_gateway.listener_callbacks[0].on_output_image(
        OutputImageUpdate(
            workflow_id="wf-origin",
            workflow_payload=payload,
            file_path=Path("output.png"),
            node_id="N1",
            generation_run_id=listener_request.generation_run_id,
            prompt_id="pid-1",
        )
    )

    assert recorder.cleared == ["wf-origin"]
    assert len(recorder.outputs) == 1
    assert recorder.outputs[0].workflow_id == "wf-origin"
    assert recorder.outputs[0].node_id == "N1"


def test_first_visual_clears_output_only_once() -> None:
    """Preview and output events should clear old output once per generation run."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    payload = {"N1": {"class_type": "KSampler"}}
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(payload),
        comfy_gateway=fake_gateway,
    )

    service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-origin",
            workflow_name="Workflow Origin",
            workflow=_build_workflow(),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )
    listener_request = fake_gateway.listener_requests[0]

    fake_gateway.listener_callbacks[0].on_preview(
        PreviewImageUpdate(workflow_id="wf-other", image=object())
    )
    fake_gateway.listener_callbacks[0].on_preview(
        PreviewImageUpdate(
            workflow_id="wf-origin",
            image=object(),
            generation_run_id=listener_request.generation_run_id,
            prompt_id="pid-1",
        )
    )
    fake_gateway.listener_callbacks[0].on_output_image(
        OutputImageUpdate(
            workflow_id="wf-origin",
            workflow_payload=payload,
            file_path=Path("output.png"),
            node_id="N1",
            generation_run_id=listener_request.generation_run_id,
            prompt_id="pid-1",
        )
    )

    assert recorder.cleared == ["wf-origin"]
    assert [event.workflow_id for event in recorder.previews] == [
        "wf-other",
        "wf-origin",
    ]
    assert len(recorder.outputs) == 1


def test_interrupt_generation_returns_gateway_result() -> None:
    """Interrupt call should delegate to gateway and return typed result."""
    interrupt_result = InterruptResult(
        status="failed",
        status_code=500,
        error="HTTP 500",
    )
    fake_gateway = _FakeGateway(
        queue_results=[],
        interrupt_result=interrupt_result,
    )
    service = GenerationService(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.interrupt_generation()

    assert result == interrupt_result
