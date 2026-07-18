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

"""Verify direct Comfy output discovery and execution instrumentation."""

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


def _definition(*, output_node: bool, input_type: str = "IMAGE") -> dict[str, object]:
    """Return one minimal normalized live Comfy definition."""

    return {
        "output_node": output_node,
        "input": {"required": {"images": [input_type, {}]}},
    }


def test_discovery_deduplicates_output_nodes_by_upstream_socket() -> None:
    """Preview and save declarations for one socket should form one source."""

    graph: dict[str, object] = {
        "10": {"class_type": "Decoder", "inputs": {}},
        "20": {
            "class_type": "PreviewImage",
            "inputs": {"images": ["10", 0]},
            "_meta": {"title": "Preview"},
        },
        "21": {
            "class_type": "ArbitrarilyNamedCustomSaver",
            "inputs": {"images": ["10", 0]},
            "_meta": {"title": "Save elsewhere"},
        },
        "22": {
            "class_type": "OtherOutput",
            "inputs": {"value": ["10", 1]},
        },
    }
    definitions = {
        "Decoder": {"output_node": False, "input": {}},
        "PreviewImage": _definition(output_node=True),
        "ArbitrarilyNamedCustomSaver": _definition(output_node=True),
        "OtherOutput": {
            "output_node": True,
            "input": {"required": {"value": ["STRING", {}]}},
        },
    }

    manifest = ComfyImageOutputDiscovery().discover(
        graph,
        node_definitions=definitions,
    )

    assert len(manifest.sources) == 1
    source = manifest.sources[0]
    assert source.socket == ComfyOutputSocket("10", 0)
    assert source.label == "1"
    assert tuple(sink.node_id for sink in source.sinks) == ("20", "21")
    assert manifest.hijacked_sink_node_ids == frozenset({"20", "21"})
    assert manifest.preserved_output_node_ids == ("22",)


def test_discovery_preserves_distinct_source_order_and_rejects_unsafe_nodes() -> None:
    """Only terminal canonical IMAGE sinks should be eligible for takeover."""

    graph = {
        "1": {"class_type": "ImageA", "inputs": {}},
        "2": {"class_type": "ImageB", "inputs": {}},
        "30": {"class_type": "SaveA", "inputs": {"images": ["2", 1]}},
        "31": {"class_type": "SaveB", "inputs": {"images": ["1", 0]}},
        "32": {"class_type": "WildcardSave", "inputs": {"images": ["1", 0]}},
        "33": {"class_type": "SaveA", "inputs": {"images": ["1", 0]}},
        "34": {"class_type": "Consumer", "inputs": {"image": ["33", 0]}},
    }
    definitions = {
        "ImageA": {"output_node": False, "input": {}},
        "ImageB": {"output_node": False, "input": {}},
        "SaveA": _definition(output_node=True),
        "SaveB": _definition(output_node=True),
        "WildcardSave": _definition(output_node=True, input_type="*"),
        "Consumer": {"output_node": False, "input": {}},
    }

    manifest = ComfyImageOutputDiscovery().discover(
        graph,
        node_definitions=definitions,
    )

    assert tuple(source.socket for source in manifest.sources) == (
        ComfyOutputSocket("2", 1),
        ComfyOutputSocket("1", 0),
    )
    assert tuple(source.label for source in manifest.sources) == ("1", "2")
    assert manifest.hijacked_sink_node_ids == frozenset({"30", "31"})
    assert manifest.preserved_output_node_ids == ("32", "33")


def test_execution_projection_is_detached_targeted_and_collision_safe() -> None:
    """Recovery instrumentation must not leak into the authored graph."""

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
        "SaveA": _definition(output_node=True),
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
