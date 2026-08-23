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

"""Build deterministic workflow Input-canvas scenarios."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.application.workflows import (
    WorkflowInputCanvasService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState

from tests.application.workflows.input_canvas.fakes import (
    _DefinitionGateway,
    _FakeInputCanvasStateService,
    _FakeCanvasIoService,
)


def _build_workflow(mask_path: str) -> WorkflowState:
    """Build one workflow with a single editable image-mask binding."""

    workflow = WorkflowState()
    workflow.cubes["CubeA"] = CubeState(
        cube_id="CubeA",
        version="1.0.0",
        alias="CubeA",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "input_image": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "E:/images/input.png"},
                },
                "input_mask": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": mask_path},
                },
                "consumer": {
                    "class_type": "Blend",
                    "inputs": {
                        "image": ["input_image", 0],
                        "mask": ["input_mask", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("CubeA")
    return workflow


def _mask_buffer_path(workflow: WorkflowState) -> str:
    """Return the editable mask image input from a single-cube test workflow."""

    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    input_mask_node = nodes["input_mask"]
    assert isinstance(input_mask_node, dict)
    input_values = input_mask_node["inputs"]
    assert isinstance(input_values, dict)
    value = input_values["image"]
    assert isinstance(value, str)
    return value


def _image_buffer_path(workflow: WorkflowState) -> str:
    """Return the editable image input from a single-cube test workflow."""

    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    input_image_node = nodes["input_image"]
    assert isinstance(input_image_node, dict)
    input_values = input_image_node["inputs"]
    assert isinstance(input_values, dict)
    value = input_values["image"]
    assert isinstance(value, str)
    return value


def _mask_asset_payload(workflow: WorkflowState) -> JsonObject:
    """Return the persisted input-mask asset payload from a test workflow."""

    asset_refs = cast(JsonObject, workflow.metadata["asset_refs"])
    input_masks = cast(JsonObject, asset_refs["input_masks"])
    return cast(JsonObject, input_masks["CubeA:input_mask"])


def _workflow_input_service(
    input_canvas_state_service: _FakeInputCanvasStateService,
    canvas_io_service: _FakeCanvasIoService,
) -> WorkflowInputCanvasService:
    """Build the workflow input-canvas service with standard collaborators."""

    return WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(),
        input_canvas_state_service=input_canvas_state_service,
        canvas_io_service=canvas_io_service,
    )


def _input_canvas_plan_service(
    definitions: Mapping[str, JsonObject] | None = None,
) -> InputCanvasPlanService:
    """Build one definition-backed Input canvas planner for service tests."""

    definition_service = WorkflowNodeDefinitionService(
        _DefinitionGateway(definitions or {})
    )
    return InputCanvasPlanService(
        node_definition_service=definition_service,
        endpoint_service=InputAssetEndpointService(definition_service),
    )
