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

"""Verify effective node activation reaches graph-backed Cube execution."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.application.generation.native_cube_workflow_builder import (
    NativeCubeWorkflowBuilder,
)
from substitute.application.generation.graph_backed_cube_workflow_builder import (
    GraphBackedCubeWorkflowBuilder,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState
from tests.support.canonical_cube_graph import graph_backed_cube_workflow_from_states


class _ManifestAnnotator:
    """Record generation graphs passed through portable metadata annotation."""

    def __init__(self) -> None:
        self.graphs: list[JsonObject] = []

    def annotate(self, graph: JsonObject) -> object:
        """Mark the detached generation graph as annotated."""

        self.graphs.append(graph)
        extra = graph.setdefault("extra", {})
        assert isinstance(extra, dict)
        extra["sugarsubstitute_model_manifest"] = {"schema_version": 1}
        return ()


def test_graph_backed_generation_refreshes_portable_model_metadata() -> None:
    """The graph serialized into generated PNGs must receive fresh model hashes."""

    cube = _cube(
        alias="Cube",
        cube_id="test/Cube.cube",
        node_name="model",
        class_type="CheckpointLoaderSimple",
        node={"inputs": {"ckpt_name": "model.safetensors"}},
    )
    workflow = graph_backed_cube_workflow_from_states(cube)
    annotator = _ManifestAnnotator()
    builder = GraphBackedCubeWorkflowBuilder(
        model_manifest_annotator=annotator,
    )

    graph = builder.build(
        workflow,
        enabled_node_keys_by_alias={"Cube": ("model",)},
        disabled_node_keys_by_alias={},
    )

    assert annotator.graphs == [graph]
    extra = cast(dict[str, object], graph["extra"])
    assert extra["sugarsubstitute_model_manifest"] == {"schema_version": 1}


@pytest.mark.parametrize(
    ("alias", "cube_id", "node_name", "class_type"),
    (
        (
            "Anima Text to Image",
            "Artificial-Sweetener/Base-Cubes/Anima/Text to Image.cube",
            "seed_variation",
            "SimpleSyrup.SeedVariation",
        ),
        (
            "Anima Automask Detailer",
            "Artificial-Sweetener/Base-Cubes/Anima/Automask Detailer.cube",
            "models",
            "SimpleSyrup.SimpleLoadAnima",
        ),
        (
            "SDXL Text to Image",
            "Artificial-Sweetener/Base-Cubes/SDXL/Text to Image.cube",
            "vectorscopecc",
            "VectorscopeCC",
        ),
        (
            "Flux Edit by Prompt",
            "Artificial-Sweetener/Base-Cubes/Flux2 Klein/Edit by Prompt.cube",
            "resize_reference",
            "dda13b93-af69-4af6-a0fa-fd0b1c6b2f84",
        ),
    ),
)
def test_enabled_authored_bypass_is_materialized_for_real_cube_patterns(
    alias: str,
    cube_id: str,
    node_name: str,
    class_type: str,
) -> None:
    """Every enabled Base Cube option must execute instead of retaining mode four."""

    cube = _cube(
        alias=alias,
        cube_id=cube_id,
        node_name=node_name,
        class_type=class_type,
        node={"mode": 4, "enabled": True},
    )
    workflow = graph_backed_cube_workflow_from_states(cube)

    graph = NativeCubeWorkflowBuilder().build(
        workflow,
        enabled_node_keys_by_alias={alias: (node_name,)},
        disabled_node_keys_by_alias={},
    )

    executable = _document_node(graph, node_name)
    assert executable.get("mode", 0) != 4
    assert "enabled" not in executable
    live = _live_node(cube, node_name)
    assert live["mode"] == 4
    assert live["enabled"] is True


def test_persisted_enabled_state_cannot_remain_authored_bypass() -> None:
    """A displayed enabled state must execute even if a delta map is empty."""

    cube = _cube(
        alias="Cube",
        cube_id="test/Cube.cube",
        node_name="optional_transform",
        class_type="OptionalTransform",
        node={"mode": 4, "enabled": True},
    )
    workflow = graph_backed_cube_workflow_from_states(cube)

    graph = NativeCubeWorkflowBuilder().build(
        workflow,
        enabled_node_keys_by_alias={},
        disabled_node_keys_by_alias={},
    )

    executable = _document_node(graph, "optional_transform")
    assert executable["mode"] == 0
    assert "enabled" not in executable


def test_disabled_normally_active_node_is_materialized_as_bypassed() -> None:
    """A visible disabled switch must produce a bypassed executable node."""

    cube = _cube(
        alias="Active Cube",
        cube_id="Artificial-Sweetener/Base-Cubes/Active.cube",
        node_name="optional_transform",
        class_type="OptionalTransform",
        node={"enabled": False},
    )
    workflow = graph_backed_cube_workflow_from_states(cube)

    graph = NativeCubeWorkflowBuilder().build(
        workflow,
        enabled_node_keys_by_alias={},
        disabled_node_keys_by_alias={"Active Cube": ("optional_transform",)},
    )

    executable = _document_node(graph, "optional_transform")
    assert executable["mode"] == 4
    assert "enabled" not in executable


def test_unknown_activation_target_fails_closed() -> None:
    """Generation must reject activation state that cannot reach its graph node."""

    cube = _cube(
        alias="Cube",
        cube_id="test/Cube.cube",
        node_name="known",
        class_type="Known",
        node={"mode": 4},
    )
    workflow = graph_backed_cube_workflow_from_states(cube)

    with pytest.raises(ValueError, match="unknown node"):
        NativeCubeWorkflowBuilder().build(
            workflow,
            enabled_node_keys_by_alias={"Cube": ("missing",)},
            disabled_node_keys_by_alias={},
        )


def test_conflicting_activation_target_fails_closed() -> None:
    """Generation must reject contradictory activation for one graph node."""

    cube = _cube(
        alias="Cube",
        cube_id="test/Cube.cube",
        node_name="known",
        class_type="Known",
        node={"mode": 4},
    )
    workflow = graph_backed_cube_workflow_from_states(cube)

    with pytest.raises(ValueError, match="conflicting activation"):
        NativeCubeWorkflowBuilder().build(
            workflow,
            enabled_node_keys_by_alias={"Cube": ("known",)},
            disabled_node_keys_by_alias={"Cube": ("known",)},
        )


def _cube(
    *,
    alias: str,
    cube_id: str,
    node_name: str,
    class_type: str,
    node: dict[str, object],
) -> CubeState:
    """Build one graph-backed Cube projection with explicit activation state."""

    node_payload: JsonObject = {
        "class_type": class_type,
        "inputs": {},
        **node,
    }
    buffer: JsonObject = {
        "cube_id": cube_id,
        "version": "1.0.0",
        "nodes": {node_name: node_payload},
        "inputs": {},
        "outputs": {},
        "layout": {},
        "definitions": {},
        "subgraphs": [],
    }
    return CubeState(
        cube_id=cube_id,
        version="1.0.0",
        alias=alias,
        original_cube=buffer,
        buffer=buffer,
        ui={
            "canonical_cube": {
                "description": "",
                "metadata": {"default_alias": alias},
            }
        },
    )


def _document_node(graph: JsonObject, node_name: str) -> dict[str, object]:
    """Return one materialized node from the first embedded Cube document."""

    definitions = cast(dict[str, list[dict[str, object]]], graph["definitions"])
    extra = cast(dict[str, object], definitions["subgraphs"][0]["extra"])
    document = cast(dict[str, object], extra["sugarcubes_document"])
    implementation = cast(dict[str, object], document["implementation"])
    nodes = cast(dict[str, dict[str, object]], implementation["nodes"])
    return nodes[node_name]


def _live_node(cube: CubeState, node_name: str) -> dict[str, object]:
    """Return one unchanged live node after detached materialization."""

    return cast(dict[str, dict[str, object]], cube.buffer["nodes"])[node_name]
