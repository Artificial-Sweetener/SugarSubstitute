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

"""Regression tests for inpaint selected-image dispatch through real cube data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from substitute.application.generation import (
    ComfyAssetStagingService,
    GenerationCallbacks,
    GenerationRequest,
    GenerationService,
)
from substitute.application.ports import (
    ComfyQueueMutationResult,
    ComfyQueueSnapshot,
    InterruptResult,
    ListenerCallbacks,
    ListenerHandle,
    ListenerSessionConnectRequest,
    ListenerSessionConnectResult,
    ListenerSessionHandle,
    ListenerStartRequest,
    ListenerStartResult,
    QueuePromptResult,
    QueueVisualRunContext,
)
from substitute.application.recipes import RecipeIoService, WorkflowExportService
from substitute.application.workflows import WorkflowAssetService
from substitute.domain.workflow import WorkflowState
from substitute.domain.workflow.models import CubeState
from substitute.infrastructure.comfy import LocalComfyAssetStager
from substitute.infrastructure.persistence import (
    FileRecipeRepository,
    FileWorkflowRepository,
)
from tests.node_behavior_test_helpers import build_behavior_snapshot
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class _QueueRecorderGateway:
    """Record queued payloads while satisfying the generation gateway contract."""

    def __init__(self) -> None:
        """Initialize call recording."""

        self.queue_calls: list[dict[str, object]] = []

    def connect_listener_session(
        self,
        request: ListenerSessionConnectRequest,
    ) -> ListenerSessionConnectResult:
        """Return a deterministic preconnected listener session."""

        return ListenerSessionConnectResult(
            connected=True,
            handle=ListenerSessionHandle(
                workflow_id=request.workflow_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
                session=object(),
            ),
            error=None,
        )

    def queue_prompt(
        self,
        workflow_payload: dict[str, object],
        *,
        client_id: str,
        execution_targets: tuple[str, ...] | None = None,
        preview_method: str | None = None,
        sugar_script: str | None = None,
        visual_context: QueueVisualRunContext | None = None,
    ) -> QueuePromptResult:
        """Record queued workflow payload and return a prompt id."""

        del client_id, execution_targets, preview_method, sugar_script, visual_context
        self.queue_calls.append(workflow_payload)
        return QueuePromptResult(
            status="queued",
            prompt_id="prompt-1",
            payload={"prompt_id": "prompt-1"},
            error=None,
        )

    def start_listener(
        self,
        request: ListenerStartRequest,
        callbacks: ListenerCallbacks,
    ) -> ListenerStartResult:
        """Return a deterministic listener handle without starting transport."""

        del callbacks
        return ListenerStartResult(
            started=True,
            handle=ListenerHandle(
                prompt_id=request.prompt_id,
                generation_run_id=request.generation_run_id,
                client_id=request.client_id,
                workflow_id=request.workflow_id,
                task=object(),
            ),
            error=None,
        )

    def close_listener_session(self, handle: ListenerSessionHandle) -> None:
        """Close a fake listener session."""

        del handle

    def interrupt(self) -> InterruptResult:
        """Return deterministic interrupt result."""

        return InterruptResult(status="sent", status_code=200, error=None)

    def get_queue(self) -> ComfyQueueSnapshot:
        """Return empty Comfy queue state for generation tests."""

        return ComfyQueueSnapshot(running_prompt_ids=(), pending_prompt_ids=())

    def delete_pending_prompt(self, prompt_id: str) -> ComfyQueueMutationResult:
        """Return deterministic pending prompt deletion result."""

        del prompt_id
        return ComfyQueueMutationResult(status="deleted", status_code=200, error=None)


class _StaticWorkflowCompiler:
    """Return a configured workflow payload for generation dispatch tests."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Store the workflow payload."""

        self._payload = payload

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> dict[str, object]:
        """Return the configured payload."""

        _ = (sugar_script_text, output_dir)
        return self._payload


def _build_real_inpaint_workflow(
    selected_image: str,
    *,
    selected_mask: str | None = None,
) -> WorkflowState:
    """Build a real inpaint workflow and associate the selected image path."""

    cube_state = CubeState(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        version="1.0.0",
        alias="Inpaint",
        original_cube={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Inpaint.cube",
            "version": "1.0.0",
            "nodes": {
                "load_image": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "00282-3430329909-ad-before.png"},
                },
                "load_image_as_mask": {
                    "class_type": "LoadImageMask",
                    "inputs": {
                        "image": "00282-3430329909-ad-before.png",
                        "channel": "red",
                    },
                },
                "consumer": {
                    "class_type": "VAEEncodeForInpaint",
                    "inputs": {
                        "pixels": ["load_image", 0],
                        "mask": ["load_image_as_mask", 0],
                    },
                },
            },
        },
        buffer={
            "nodes": {
                "load_image": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "00282-3430329909-ad-before.png"},
                },
                "load_image_as_mask": {
                    "class_type": "LoadImageMask",
                    "inputs": {
                        "image": "00282-3430329909-ad-before.png",
                        "channel": "red",
                    },
                },
                "consumer": {
                    "class_type": "VAEEncodeForInpaint",
                    "inputs": {
                        "pixels": ["load_image", 0],
                        "mask": ["load_image_as_mask", 0],
                    },
                },
            }
        },
    )
    workflow = WorkflowState(
        cubes={"Inpaint": cube_state},
        stack_order=["Inpaint"],
    )
    asset_service = WorkflowAssetService()
    associated = asset_service.associate_local_input_image(
        workflow,
        section_key="Inpaint",
        node_name="load_image",
        field_key="image",
        image_path=selected_image,
    )
    assert associated is True
    if selected_mask is not None:
        mask_associated = asset_service.associate_project_input_mask(
            workflow,
            section_key="Inpaint",
            node_name="load_image_as_mask",
            field_key="image",
            relative_path=selected_mask,
        )
        assert mask_associated is True
    return workflow


def test_real_inpaint_cube_compiles_selected_load_image_instead_of_default() -> None:
    """The real inpaint cube should compile the selected image after association."""

    default_image = "00282-3430329909-ad-before.png"
    selected_image = "E:/images/selected.png"
    native_selected_image = str(Path(selected_image))
    workflow = _build_real_inpaint_workflow(selected_image)
    sugar_script = RecipeIoService(
        recipe_repository=FileRecipeRepository()
    ).serialize_workflow_to_sugar_script(cast(Any, workflow))
    compiled = WorkflowExportService(
        workflow_repository=FileWorkflowRepository(),
        workflow_payload_compiler=_StaticWorkflowCompiler(
            {
                "1": {
                    "class_type": "LoadImage",
                    "inputs": {"image": native_selected_image},
                }
            }
        ),
    ).compile_workflow_payload(
        sugar_script_text=sugar_script,
        output_dir=Path("user/projects"),
    )
    load_image_nodes = [
        node
        for node in compiled.values()
        if isinstance(node, dict) and node.get("class_type") == "LoadImage"
    ]

    assert (
        f"set Inpaint.load_image.image = {json.dumps(native_selected_image)}"
        in sugar_script
    )
    assert f'set Inpaint.load_image.image = "{default_image}"' not in sugar_script
    assert load_image_nodes
    assert load_image_nodes[0]["inputs"]["image"] == native_selected_image
    assert load_image_nodes[0]["inputs"]["image"] != default_image


def test_real_inpaint_behavior_refresh_preserves_selected_image_and_mask() -> None:
    """Editor behavior refresh must not rewrite Substitute-owned inpaint assets."""

    default_image = "00282-3430329909-ad-before.png"
    selected_image = "E:/images/selected.png"
    native_selected_image = str(Path(selected_image))
    selected_mask = "selected__2160x3072__Inpaint__load_image_as_mask.png"
    workflow = _build_real_inpaint_workflow(
        selected_image,
        selected_mask=selected_mask,
    )

    build_behavior_snapshot(
        cube_states=cast(Any, workflow.cubes),
        stack_order=workflow.stack_order,
    )
    nodes = workflow.cubes["Inpaint"].buffer["nodes"]
    assert isinstance(nodes, dict)
    load_image = cast(dict[str, object], nodes["load_image"])
    load_mask = cast(dict[str, object], nodes["load_image_as_mask"])
    image_inputs = cast(dict[str, object], load_image["inputs"])
    mask_inputs = cast(dict[str, object], load_mask["inputs"])

    assert image_inputs["image"] == native_selected_image
    assert mask_inputs["image"] == selected_mask
    assert image_inputs["image"] != default_image
    assert mask_inputs["image"] != default_image


def test_real_inpaint_generation_queues_selected_load_image_instead_of_default(
    tmp_path: Path,
) -> None:
    """Real inpaint generation should queue the selected image after staging."""

    default_image = "00282-3430329909-ad-before.png"
    selected_image = tmp_path / "selected.png"
    workflow_name = "Inpaint Workflow"
    selected_mask = tmp_path / workflow_name / "masks" / "selected_mask.png"
    selected_image.write_bytes(b"selected image bytes")
    selected_mask.parent.mkdir(parents=True)
    selected_mask.write_bytes(b"selected mask bytes")
    workflow = _build_real_inpaint_workflow(
        str(selected_image),
        selected_mask=selected_mask.name,
    )
    build_behavior_snapshot(
        cube_states=cast(Any, workflow.cubes),
        stack_order=workflow.stack_order,
    )
    gateway = _QueueRecorderGateway()
    service = GenerationService(
        recipe_io_service=RecipeIoService(recipe_repository=FileRecipeRepository()),
        workflow_export_service=WorkflowExportService(
            workflow_repository=FileWorkflowRepository(),
            workflow_payload_compiler=_StaticWorkflowCompiler(
                {
                    "1": {
                        "class_type": "LoadImage",
                        "inputs": {"image": str(selected_image)},
                        "_meta": {"title": "Inpaint.load_image"},
                    },
                    "2": {
                        "class_type": "LoadImageMask",
                        "inputs": {
                            "image": selected_mask.name,
                            "channel": "red",
                        },
                        "_meta": {"title": "Inpaint.load_image_as_mask"},
                    },
                }
            ),
        ),
        comfy_gateway=gateway,
        asset_staging_service=ComfyAssetStagingService.with_projects_dir(
            stager=LocalComfyAssetStager(),
            projects_dir=tmp_path,
        ),
        output_dir=Path("user/projects"),
    )
    failures: list[object] = []

    result = service.run_single_generation(
        request=GenerationRequest(
            workflow_id="wf-inpaint",
            workflow_name=workflow_name,
            workflow=cast(Any, workflow),
        ),
        callbacks=GenerationCallbacks(
            clear_output=lambda _workflow_id: None,
            on_progress=lambda _event: None,
            on_model_load_progress=lambda _event: None,
            on_preview=lambda _event: None,
            on_output_image=lambda _event: None,
            on_failure=lambda failure: failures.append(failure),
            on_timing=lambda _event: None,
        ),
    )
    queued_load_image_nodes = [
        node
        for node in gateway.queue_calls[0].values()
        if isinstance(node, dict) and node.get("class_type") == "LoadImage"
    ]
    queued_load_mask_nodes = [
        node
        for node in gateway.queue_calls[0].values()
        if isinstance(node, dict) and node.get("class_type") == "LoadImageMask"
    ]

    assert result.started is True
    assert failures == []
    assert queued_load_image_nodes
    assert queued_load_mask_nodes
    assert queued_load_image_nodes[0]["inputs"]["image"] == subprocess_path(
        selected_image
    )
    assert queued_load_mask_nodes[0]["inputs"]["image"] == subprocess_path(
        selected_mask
    )
    assert queued_load_mask_nodes[0]["inputs"]["channel"] == "red"
    assert queued_load_image_nodes[0]["inputs"]["image"] != default_image
    assert queued_load_mask_nodes[0]["inputs"]["image"] != default_image
