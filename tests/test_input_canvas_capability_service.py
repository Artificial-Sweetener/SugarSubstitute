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

"""Contract tests for workflow input-canvas capability detection."""

from __future__ import annotations

from pathlib import Path

from substitute.application.workflows import (
    InputCanvasCapabilityService,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState


def _cube_state(nodes: dict[str, object]) -> CubeState:
    """Build one cube state with the supplied graph nodes."""

    return CubeState(
        cube_id="CubeA",
        version="1.0.0",
        alias="CubeA",
        original_cube={"nodes": {}},
        buffer={"nodes": nodes},
    )


def _service() -> InputCanvasCapabilityService:
    """Build the capability service with production binding rules."""

    definitions = WorkflowNodeDefinitionService()
    return InputCanvasCapabilityService(
        InputCanvasPlanService(
            node_definition_service=definitions,
            endpoint_service=InputAssetEndpointService(definitions),
        ),
        WorkflowGraphSectionService(),
    )


def test_workflow_needs_input_canvas_for_used_load_image() -> None:
    """A connected LoadImage output should expose the Input canvas."""

    workflow = WorkflowState(
        cubes={
            "CubeA": _cube_state(
                {
                    "input_image": {
                        "class_type": "LoadImage",
                        "inputs": {"image": ""},
                    },
                    "consumer": {
                        "class_type": "Consumer",
                        "inputs": {"pixels": ["input_image", 0]},
                    },
                }
            )
        },
        stack_order=["CubeA"],
    )

    assert _service().workflow_needs_input_canvas(workflow) is True


def test_direct_workflow_uses_same_input_canvas_capability_path() -> None:
    """A direct graph should expose input capability through the shared projection."""

    graph: JsonObject = {
        "nodes": {
            "input_image": {
                "class_type": "LoadImage",
                "inputs": {"image": "photo.png"},
            },
            "consumer": {
                "class_type": "Consumer",
                "inputs": {"pixels": ["input_image", 0]},
            },
        }
    }
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("workflow.json"),
            source_workflow=graph,
            buffer=graph,
        )
    )

    assert _service().workflow_needs_input_canvas(workflow) is True


def test_workflow_needs_input_canvas_for_editable_mask_binding() -> None:
    """Editable LoadImageMask bindings should expose the Input canvas."""

    workflow = WorkflowState(
        cubes={
            "CubeA": _cube_state(
                {
                    "input_image": {
                        "class_type": "LoadImage",
                        "inputs": {"image": "input.png"},
                    },
                    "input_mask": {
                        "class_type": "LoadImageMask",
                        "inputs": {"image": "mask.png"},
                    },
                    "consumer": {
                        "class_type": "Blend",
                        "inputs": {
                            "image": ["input_image", 0],
                            "mask": ["input_mask", 0],
                        },
                    },
                }
            )
        },
        stack_order=["CubeA"],
    )

    assert _service().workflow_needs_input_canvas(workflow) is True


def test_workflow_without_cubes_does_not_need_input_canvas() -> None:
    """An empty workflow should not expose the Input canvas."""

    assert _service().workflow_needs_input_canvas(WorkflowState()) is False


def test_workflow_with_plain_nodes_does_not_need_input_canvas() -> None:
    """Non-image nodes should not expose the Input canvas."""

    workflow = WorkflowState(
        cubes={
            "CubeA": _cube_state(
                {
                    "sampler": {
                        "class_type": "KSampler",
                        "inputs": {"seed": 123},
                    }
                }
            )
        },
        stack_order=["CubeA"],
    )

    assert _service().workflow_needs_input_canvas(workflow) is False


def test_standalone_load_image_mask_does_not_need_input_canvas() -> None:
    """An unbound standalone LoadImageMask should fail closed."""

    workflow = WorkflowState(
        cubes={
            "CubeA": _cube_state(
                {
                    "input_mask": {
                        "class_type": "LoadImageMask",
                        "inputs": {"image": "mask.png"},
                    }
                }
            )
        },
        stack_order=["CubeA"],
    )

    assert _service().workflow_needs_input_canvas(workflow) is False
