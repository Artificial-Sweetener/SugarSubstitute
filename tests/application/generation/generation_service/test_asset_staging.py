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

"""Test selected-input asset staging and staging failure behavior."""

from __future__ import annotations

from __future__ import annotations
from substitute.application.generation import (
    ComfyAssetStagingResult,
    GenerationRequest,
)
from substitute.application.ports import (
    QueuePromptResult,
)
from substitute.domain.generation import AssetStagingFailure

from tests.application.generation.generation_service.support import (
    _CallbackRecorder,
    _FakeRecipeIoService,
    _FakeWorkflowExportService,
    _FakeGateway,
    _FakeAssetStagingService,
    _build_generation_callbacks,
    _as_json_object,
    _build_generation_service,
    _build_workflow,
)


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
            workflow_payload=_as_json_object(staged_payload),
            staged_assets=(),
            failures=(),
        )
    )
    service = _build_generation_service(
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
    (
        queued_payload,
        queued_client_id,
        execution_targets,
        preview_method,
        sugar_script,
        visual_context,
    ) = fake_gateway.queue_calls[0]
    assert queued_payload == staged_payload
    assert queued_client_id == run_client_id
    assert execution_targets is None
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
    service = _build_generation_service(
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
    service = _build_generation_service(
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
