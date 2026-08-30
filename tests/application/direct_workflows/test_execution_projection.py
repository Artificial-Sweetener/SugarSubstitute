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

"""Verify execution projection for direct Comfy workflow outputs."""

from __future__ import annotations

from copy import deepcopy

from substitute.application.direct_workflows.execution_projection import (
    DirectWorkflowExecutionProjector,
)
from substitute.domain.comfy_workflow.output_manifest import (
    ComfyImageOutputDiscovery,
    ComfyOutputSocket,
    DirectWorkflowGenerationPlan,
)


def test_execution_projection_is_detached_targeted_and_collision_safe() -> None:
    """Keep recovery instrumentation detached from the authored graph."""
    graph: dict[str, object] = {
        "1": {"class_type": "ImageA", "inputs": {}},
        "2": {"class_type": "SaveA", "inputs": {"images": ["1", 0]}},
        "3": {"class_type": "OtherOutput", "inputs": {}},
        "__substitute_image_output_1": {
            "class_type": "AuthoredNode",
            "inputs": {},
        },
    }
    original = deepcopy(graph)
    definitions = {
        "ImageA": {"output_node": False, "input": {}},
        "SaveA": {
            "output_node": True,
            "input": {"required": {"images": ["IMAGE", {}]}},
        },
        "OtherOutput": {"output_node": True, "input": {}},
        "AuthoredNode": {"output_node": False, "input": {}},
    }
    manifest = ComfyImageOutputDiscovery().discover(
        graph,
        node_definitions=definitions,
    )
    plan = DirectWorkflowGenerationPlan(
        authored_api_graph=graph,
        output_manifest=manifest,
    )

    projection = DirectWorkflowExecutionProjector().project(plan)

    assert graph == original
    assert projection.execution_targets == (
        "3",
        "__substitute_image_output_1_2",
    )
    recovery = projection.recovery_outputs[0]
    assert recovery.source_socket == ComfyOutputSocket("1", 0)
    assert recovery.source_key == "direct:1:0"
    assert projection.prompt[recovery.recovery_node_id] == {
        "class_type": "PreviewImage",
        "inputs": {"images": ["1", 0]},
        "_meta": {"title": "1"},
    }
    assert projection.prompt["2"] == graph["2"]
