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

"""Verify native Cube generation graph construction and convenience isolation."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.application.generation.native_cube_workflow_builder import (
    NativeCubeWorkflowBuilder,
)
from substitute.domain.common import JsonObject
from substitute.domain.common import GlobalOverrideScope
from substitute.domain.workflow import CubeState, WorkflowState
from tests.support.canonical_cube_graph import (
    graph_backed_cube_workflow,
    graph_backed_cube_workflow_from_states,
)


def test_builder_rejects_a_workflow_without_a_canonical_graph() -> None:
    """Generation must not reconstruct a graph from legacy Cube buffers."""

    with pytest.raises(ValueError, match="not been migrated"):
        NativeCubeWorkflowBuilder().build(WorkflowState())


def test_builder_projects_stack_order_into_native_cube_geometry() -> None:
    """Stack adjacency must be native geometry interpreted only by SugarCubes."""

    workflow = _workflow()

    graph = NativeCubeWorkflowBuilder().build(workflow)

    assert [node["id"] for node in cast(list[dict[str, object]], graph["nodes"])] == [
        1,
        2,
    ]
    assert graph["links"] == []
    nodes = cast(list[dict[str, object]], graph["nodes"])
    assert [node["pos"] for node in nodes] == [[0, 0], [344, 0]]
    assert all(node["size"] == [320, 200] for node in nodes)
    definitions = cast(dict[str, list[dict[str, object]]], graph["definitions"])[
        "subgraphs"
    ]
    assert cast(dict[str, object], definitions[0]["extra"])["sugarcubes_kind"] == "cube"


def test_builder_defers_anima_boundary_types_and_matching_to_sugarcubes() -> None:
    """Retain stable port order without duplicating SugarCubes type semantics."""

    source = _cube(
        "Prompt by Region",
        inputs={},
        outputs={
            "output.image": ["vae_decode", 0],
            "output.mask": ["load_mask_batch", 0],
        },
    )
    source.buffer["nodes"] = {
        "vae_decode": {"class_type": "VAEDecode", "inputs": {}},
        "load_mask_batch": {"class_type": "LoadMaskBatch", "inputs": {}},
    }
    source.buffer["definitions"] = {
        "VAEDecode": {"output": ["IMAGE"]},
        "LoadMaskBatch": {"output": ["MASK"]},
    }
    target = _cube(
        "Diffusion Upscale",
        inputs={
            "input.value": {"targets": [["upscale", "image"]]},
            "input.mask": {"targets": [["sampler", "region_masks"]]},
        },
        outputs={},
    )
    target.buffer["nodes"] = {
        "upscale": {"class_type": "Upscale", "inputs": {}},
        "sampler": {"class_type": "Sampler", "inputs": {}},
    }
    target.buffer["definitions"] = {
        "Upscale": {"input": {"required": {"image": ["IMAGE", {}]}}},
        "Sampler": {"input": {"optional": {"region_masks": ["MASK", {}]}}},
    }
    workflow = graph_backed_cube_workflow_from_states(source, target)

    graph = NativeCubeWorkflowBuilder().build(workflow)

    assert graph["links"] == []
    nodes = cast(list[dict[str, object]], graph["nodes"])
    assert nodes[0]["outputs"] == [
        {"name": "output.image", "type": "*"},
        {"name": "output.mask", "type": "*"},
    ]
    assert nodes[1]["inputs"] == [
        {"name": "input.value", "type": "*"},
        {"name": "input.mask", "type": "*"},
    ]


def test_builder_authors_links_and_overrides_as_graph_value_relations() -> None:
    """Author conveniences without copying values or crossing Cube boundaries."""

    workflow = _workflow()
    second = workflow.cubes["Second"]
    target_node = cast(
        dict[str, object], cast(dict[str, object], second.buffer["nodes"])["prompt"]
    )
    target_node["node_link"] = {"from_cube": "First", "from_node": "prompt"}
    scopes = {
        "seed": GlobalOverrideScope(
            override_key="seed",
            value=42,
            mode="global",
            full_participation=True,
            participant_fields=frozenset({("Second", "sampler", "seed")}),
        )
    }

    graph = NativeCubeWorkflowBuilder().build(workflow, global_override_scopes=scopes)

    assert graph["links"] == []
    second_document = _document(graph, index=1)
    implementation = cast(dict[str, object], second_document["implementation"])
    nodes = cast(dict[str, dict[str, object]], implementation["nodes"])
    prompt_inputs = cast(dict[str, object], nodes["prompt"]["inputs"])
    sampler_inputs = cast(dict[str, object], nodes["sampler"]["inputs"])
    assert prompt_inputs["text"] == "dormant"
    assert sampler_inputs["seed"] == 1
    flavors = cast(dict[str, list[dict[str, object]]], second_document["flavors"])
    values = cast(dict[str, object], flavors["authored"][0]["values"])
    assert values == {}
    assert nodes["prompt"]["node_link"] == {
        "from_cube": "First",
        "from_node": "prompt",
    }
    relations = _value_relations(graph)
    assert relations == [
        {
            "relation_id": "link:Second:prompt:text",
            "owner": "substitute",
            "kind": "field_link",
            "source": {
                "instance_id": "First",
                "node_symbol": "prompt",
                "input_name": "text",
            },
            "targets": [
                {
                    "instance_id": "Second",
                    "node_symbol": "prompt",
                    "input_name": "text",
                }
            ],
        },
        {
            "relation_id": "override:seed",
            "owner": "substitute",
            "kind": "global_override",
            "override_key": "seed",
            "value": 42,
            "targets": [
                {
                    "instance_id": "Second",
                    "node_symbol": "sampler",
                    "input_name": "seed",
                }
            ],
        },
    ]
    assert cast(dict[str, object], target_node["inputs"])["text"] == "dormant"
    assert "node_link" in target_node


def test_builder_authors_non_prompt_value_links_without_crossing_boundaries() -> None:
    """Every compatible value relation should copy into the target-local node."""

    workflow = _workflow()
    first_sampler = cast(
        dict[str, object],
        cast(dict[str, object], workflow.cubes["First"].buffer["nodes"])["sampler"],
    )
    second_sampler = cast(
        dict[str, object],
        cast(dict[str, object], workflow.cubes["Second"].buffer["nodes"])["sampler"],
    )
    cast(dict[str, object], first_sampler["inputs"])["seed"] = 8675309
    second_sampler["node_link"] = {"from_cube": "First", "from_node": "sampler"}

    graph = NativeCubeWorkflowBuilder().build(workflow)

    assert graph["links"] == []
    second_document = _document(graph, index=1)
    implementation = cast(dict[str, object], second_document["implementation"])
    nodes = cast(dict[str, dict[str, object]], implementation["nodes"])
    assert cast(dict[str, object], nodes["sampler"]["inputs"])["seed"] == 1
    assert nodes["sampler"]["node_link"] == {
        "from_cube": "First",
        "from_node": "sampler",
    }
    assert _value_relations(graph) == [
        {
            "relation_id": "link:Second:sampler:seed",
            "owner": "substitute",
            "kind": "field_link",
            "source": {
                "instance_id": "First",
                "node_symbol": "sampler",
                "input_name": "seed",
            },
            "targets": [
                {
                    "instance_id": "Second",
                    "node_symbol": "sampler",
                    "input_name": "seed",
                }
            ],
        }
    ]
    assert cast(dict[str, object], second_sampler["inputs"])["seed"] == 1
    assert second_sampler["node_link"] == {
        "from_cube": "First",
        "from_node": "sampler",
    }


def test_builder_preserves_changed_seed_in_graph_relation_identity() -> None:
    """Make each selected seed an explicit queued-graph input without mutation."""

    workflow = _workflow()
    participants = frozenset(
        {
            ("First", "sampler", "seed"),
            ("Second", "sampler", "seed"),
        }
    )

    first = NativeCubeWorkflowBuilder().build(
        workflow,
        global_override_scopes={
            "seed": GlobalOverrideScope(
                override_key="seed",
                value=101,
                mode="global",
                full_participation=True,
                participant_fields=participants,
            )
        },
    )
    second = NativeCubeWorkflowBuilder().build(
        workflow,
        global_override_scopes={
            "seed": GlobalOverrideScope(
                override_key="seed",
                value=202,
                mode="global",
                full_participation=True,
                participant_fields=participants,
            )
        },
    )

    first_relation = _value_relations(first)[0]
    second_relation = _value_relations(second)[0]
    assert first_relation["value"] == 101
    assert second_relation["value"] == 202
    assert first != second
    assert _sampler_seed(workflow, "First") == 1
    assert _sampler_seed(workflow, "Second") == 1


def test_builder_preserves_local_values_for_explicitly_unlinked_nodes() -> None:
    """A canonical null link selection must execute with its local node values."""

    workflow = _workflow()
    first_prompt = cast(
        dict[str, object],
        cast(dict[str, object], workflow.cubes["First"].buffer["nodes"])["prompt"],
    )
    first_prompt["node_link"] = {"from_cube": None, "from_node": None}

    graph = NativeCubeWorkflowBuilder().build(workflow)

    first_document = _document(graph, index=0)
    implementation = cast(dict[str, object], first_document["implementation"])
    prompt = cast(dict[str, dict[str, object]], implementation["nodes"])["prompt"]
    assert cast(dict[str, object], prompt["inputs"])["text"] == "anchor"
    assert prompt["node_link"] == {"from_cube": None, "from_node": None}
    assert _value_relations(graph) == []
    assert first_prompt["node_link"] == {"from_cube": None, "from_node": None}


def test_builder_preserves_ordinary_regions_in_graph_backed_cube_workflow() -> None:
    """Graph-backed execution must update Cube documents without rebuilding the graph."""

    workflow = graph_backed_cube_workflow("First", "Second")
    assert workflow.direct_workflow is not None
    source_nodes = cast(
        list[dict[str, object]], workflow.direct_workflow.source_workflow["nodes"]
    )
    source_nodes.append(
        {
            "id": "ordinary",
            "type": "Ordinary",
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "properties": {},
        }
    )
    workflow.cubes["First"].buffer["nodes"] = {
        "prompt": {"class_type": "PrimitiveString", "inputs": {"text": "edited"}}
    }

    graph = NativeCubeWorkflowBuilder().build(workflow)

    nodes = cast(list[dict[str, object]], graph["nodes"])
    assert [node["id"] for node in nodes] == [1, 2, "ordinary"]
    assert graph["links"] == [[1, 1, 0, 2, 0, "*"]]
    first_document = _document(graph, index=0)
    implementation = cast(dict[str, object], first_document["implementation"])
    prompt = cast(dict[str, dict[str, object]], implementation["nodes"])["prompt"]
    assert cast(dict[str, object], prompt["inputs"])["text"] == "edited"
    assert workflow.direct_workflow.source_workflow["nodes"] is source_nodes
    original_document = cast(dict[str, object], workflow.cubes["First"].ui)[
        "canonical_cube"
    ]
    assert (
        cast(dict[str, object], original_document)["implementation"] != implementation
    )


def test_builder_preserves_manually_wired_cube_edges_exactly() -> None:
    """Automatic series policy must not normalize an authoritative Comfy graph."""

    workflow = graph_backed_cube_workflow("First", "Second")
    assert workflow.direct_workflow is not None
    source = workflow.direct_workflow.source_workflow
    nodes = cast(list[dict[str, object]], source["nodes"])
    nodes[0]["outputs"] = [
        {"name": "output.first", "type": "IMAGE"},
        {"name": "output.second", "type": "IMAGE"},
    ]
    nodes[1]["inputs"] = [
        {"name": "input.first", "type": "IMAGE"},
        {"name": "input.second", "type": "IMAGE"},
    ]
    source["links"] = [
        [7, 1, 1, 2, 0, "IMAGE"],
        [8, 1, 0, 2, 1, "IMAGE"],
    ]

    graph = NativeCubeWorkflowBuilder().build(workflow)

    assert graph["links"] == [
        [7, 1, 1, 2, 0, "IMAGE"],
        [8, 1, 0, 2, 1, "IMAGE"],
    ]


def _workflow() -> WorkflowState:
    """Return two compatible canonical Cube runtime states."""

    first = _cube("First", inputs={}, outputs={"image": {"node": "sampler", "slot": 0}})
    second = _cube(
        "Second", inputs={"image": {"targets": [["sampler", "image"]]}}, outputs={}
    )
    return graph_backed_cube_workflow_from_states(first, second)


def _cube(
    alias: str,
    *,
    inputs: dict[str, object],
    outputs: dict[str, object],
) -> CubeState:
    """Build one editor runtime Cube with canonical metadata."""

    buffer: JsonObject = {
        "cube_id": f"test/{alias}.cube",
        "version": "1.0.0",
        "nodes": {
            "prompt": {
                "class_type": "PrimitiveString",
                "inputs": {"text": "anchor" if alias == "First" else "dormant"},
            },
            "sampler": {
                "class_type": "TestSampler",
                "inputs": {"seed": 1},
            },
        },
        "inputs": inputs,
        "outputs": outputs,
        "layout": {},
        "definitions": {},
        "subgraphs": [],
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                {
                    "control_id": "prompt.text",
                    "symbol": "prompt",
                    "input_name": "text",
                    "label": "text",
                    "class_type": "PrimitiveString",
                    "value_type": "string",
                },
                {
                    "control_id": "sampler.seed",
                    "symbol": "sampler",
                    "input_name": "seed",
                    "label": "seed",
                    "class_type": "TestSampler",
                    "value_type": "number",
                },
            ],
        },
        "flavors": {"authored": [{"id": "default", "name": "Default", "values": {}}]},
    }
    return CubeState(
        cube_id=f"test/{alias}.cube",
        version="1.0.0",
        alias=alias,
        original_cube=buffer,
        buffer=buffer,
        ui={
            "canonical_cube": {
                "description": "",
                "metadata": {"default_alias": alias},
                "surface": buffer["surface"],
                "flavors": buffer["flavors"],
            }
        },
    )


def _document(graph: JsonObject, *, index: int) -> dict[str, object]:
    """Return one embedded Cube document from a projected workflow."""

    definitions = cast(dict[str, list[dict[str, object]]], graph["definitions"])[
        "subgraphs"
    ]
    extra = cast(dict[str, object], definitions[index]["extra"])
    return cast(dict[str, object], extra["sugarcubes_document"])


def _sampler_seed(workflow: WorkflowState, alias: str) -> object:
    """Return one live workflow sampler seed."""

    nodes = cast(dict[str, dict[str, object]], workflow.cubes[alias].buffer["nodes"])
    inputs = cast(dict[str, object], nodes["sampler"]["inputs"])
    return inputs["seed"]


def _value_relations(graph: JsonObject) -> list[dict[str, object]]:
    """Return Substitute-authored root value relationships."""

    extra = cast(dict[str, object], graph.get("extra", {}))
    if "sugarcubes_composition" not in extra:
        return []
    composition = cast(dict[str, object], extra["sugarcubes_composition"])
    return cast(list[dict[str, object]], composition["value_relations"])
