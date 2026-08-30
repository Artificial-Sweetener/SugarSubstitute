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

"""Test prepared generation execution and graph dispatch."""

from __future__ import annotations

from __future__ import annotations
from datetime import datetime
from pathlib import Path

from substitute.application.generation import (
    GenerationRequest,
    PreparedGenerationRequest,
)
from substitute.application.ports import (
    ListenerOutputSource,
    PreviewImageUpdate,
    QueuePromptResult,
)
from substitute.domain.comfy_workflow import (
    ComfyImageOutputDiscovery,
    DirectWorkflowGenerationPlan,
    DirectWorkflowOutputManifest,
)

from tests.application.generation.generation_service.support import (
    _CallbackRecorder,
    _FakeRecipeIoService,
    _FakeWorkflowExportService,
    _FakeGateway,
    _build_generation_callbacks,
    _as_json_object,
    _build_generation_service,
    _build_workflow,
)


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
    service = _build_generation_service(
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
    (
        queued_payload,
        queued_client_id,
        execution_targets,
        preview_method,
        sugar_script,
        visual_context,
    ) = fake_gateway.queue_calls[0]
    assert queued_payload == workflow_payload
    assert queued_client_id == run_client_id
    assert execution_targets is None
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
    assert getattr(recorder.run_started[0], "output_session_id") == (
        listener_request.generation_run_id
    )
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

    assert recorder.cleared == []
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
    service = _build_generation_service(
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
    service = _build_generation_service(
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


def test_run_prepared_generation_queues_direct_graph_without_compiler() -> None:
    """Prepared direct graphs should reach Comfy without entering Sugar compilation."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-direct",
                payload={"prompt_id": "pid-direct"},
                error=None,
            )
        ]
    )
    exporter = _FakeWorkflowExportService(
        {"wrong": {"class_type": "CompilerShouldNotRun", "inputs": {}}}
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=exporter,
        comfy_gateway=fake_gateway,
    )
    graph = {
        "9": {
            "class_type": "KSampler",
            "inputs": {"seed": 123},
        }
    }

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-direct",
            workflow_name="Direct Workflow",
            sugar_script_text="",
            direct_workflow_plan=DirectWorkflowGenerationPlan(
                authored_api_graph=_as_json_object(graph),
                output_manifest=DirectWorkflowOutputManifest(
                    sources=(),
                    hijacked_sink_node_ids=frozenset(),
                    preserved_output_node_ids=(),
                ),
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    assert exporter.calls == []
    assert fake_gateway.queue_calls[0][0] == graph
    assert fake_gateway.queue_calls[0][4] == ""


def test_direct_plan_queues_recovery_node_as_partial_execution_target() -> None:
    """Direct execution should target recovery output instead of authored saver."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-direct",
                payload={"prompt_id": "pid-direct"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService({}),
        comfy_gateway=fake_gateway,
    )
    graph: dict[str, object] = {
        "1": {"class_type": "EmptyImage", "inputs": {}},
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0]},
        },
    }
    manifest = ComfyImageOutputDiscovery().discover(
        graph,
        node_definitions={
            "EmptyImage": {"output_node": False, "input": {}},
            "SaveImage": {
                "output_node": True,
                "input": {"required": {"images": ["IMAGE", {}]}},
            },
        },
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-direct",
            workflow_name="Direct Workflow",
            sugar_script_text="",
            direct_workflow_plan=DirectWorkflowGenerationPlan(
                authored_api_graph=_as_json_object(graph),
                output_manifest=manifest,
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    queued_payload = fake_gateway.queue_calls[0][0]
    execution_targets = fake_gateway.queue_calls[0][2]
    assert queued_payload["2"] == graph["2"]
    assert queued_payload["__substitute_image_output_1"] == {
        "class_type": "PreviewImage",
        "inputs": {"images": ["1", 0]},
        "_meta": {"title": "1"},
    }
    assert execution_targets == ("__substitute_image_output_1",)
    visual_context = fake_gateway.queue_calls[0][5]
    assert visual_context is not None
    assert visual_context.sources["__substitute_image_output_1"] == {
        "sourceKey": "direct:1:0",
        "sourceLabel": "1",
        "cubeAlias": "1",
    }
    assert fake_gateway.listener_requests[0].standard_output_sources == (
        ListenerOutputSource(
            node_id="__substitute_image_output_1",
            source_key="direct:1:0",
            source_label="1",
        ),
    )


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
    service = _build_generation_service(
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
    assert len(recorder.run_started) == 1
    assert getattr(recorder.run_started[0], "output_session_id") == "run-1"
