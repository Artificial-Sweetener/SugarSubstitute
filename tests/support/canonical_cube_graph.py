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

"""Build canonical graph-backed Cube fixtures shared across workflow tests."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.comfy_workflow.cube_analysis import (
    AnalyzedCubeEdge,
    AnalyzedCubeInstance,
    AnalyzedCubeSegment,
    CanonicalCubeGraphAnalysis,
    CubeGraphEdgeOrigin,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.workflow import CubeState
from substitute.domain.cubes import project_editable_cube_document


def graph_backed_cube_workflow(*aliases: str) -> WorkflowState:
    """Return a workflow whose Cube views derive from one canonical Comfy graph."""

    nodes: list[dict[str, object]] = []
    definitions: list[dict[str, object]] = []
    links: list[list[object]] = []
    for node_id, alias in enumerate(aliases, start=1):
        definition_id = f"definition-{node_id}"
        nodes.append(
            {
                "id": node_id,
                "type": definition_id,
                "mode": 0,
                "inputs": [{"name": "input", "type": "*"}],
                "outputs": [{"name": "output", "type": "*"}],
                "properties": {
                    "cnr_id": "sugarcubes",
                    "sugarcubes_kind": "cube",
                    "sugarcubes_cube": {
                        "cube_id": f"test/{alias}.cube",
                        "cube_version": "1.0.0",
                        "instance_id": alias,
                        "instance_alias": alias,
                    },
                },
            }
        )
        definitions.append(
            {
                "id": definition_id,
                "name": alias,
                "nodes": [],
                "links": [],
                "inputs": [{"name": "input", "type": "*"}],
                "outputs": [{"name": "output", "type": "*"}],
                "extra": {
                    "sugarcubes_kind": "cube",
                    "sugarcubes_document": {
                        "cube_id": f"test/{alias}.cube",
                        "version": "1.0.0",
                        "implementation": {
                            "nodes": {},
                            "inputs": {},
                            "outputs": {},
                        },
                    },
                },
            }
        )
        if node_id > 1:
            links.append([node_id - 1, node_id - 1, 0, node_id, 0, "*"])
    source_workflow: dict[str, object] = {
        "version": 0.4,
        "nodes": nodes,
        "links": links,
        "definitions": {"subgraphs": definitions},
    }
    analyzed_instances = tuple(
        AnalyzedCubeInstance(
            instance_id=alias,
            node_id=str(node_id),
            definition_id=f"definition-{node_id}",
            cube_id=f"test/{alias}.cube",
            cube_version="1.0.0",
            alias=alias,
            execution_mode=0,
        )
        for node_id, alias in enumerate(aliases, start=1)
    )
    analyzed_edges = tuple(
        AnalyzedCubeEdge(
            source_instance_id=source,
            source_binding="output",
            target_instance_id=target,
            target_binding="input",
            origin=CubeGraphEdgeOrigin.EXPLICIT,
        )
        for source, target in zip(aliases, aliases[1:])
    )
    analysis = CanonicalCubeGraphAnalysis(
        workflow_semantic_hash="fixture",
        instances=analyzed_instances,
        edges=analyzed_edges,
        proximity_edges=(),
        segments=(
            AnalyzedCubeSegment(
                instance_ids=tuple(aliases),
                reorderable=len(aliases) > 1,
                boundary_node_ids=(),
            ),
        )
        if aliases
        else (),
        workflow=source_workflow,
    )
    return WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("cube-graph.json"),
            source_workflow=source_workflow,
            buffer={"nodes": {}},
            cube_analysis=analysis,
        )
    )


def graph_backed_cube_workflow_from_states(
    *cubes: CubeState,
) -> WorkflowState:
    """Wrap exact Cube states in a canonical native graph test fixture."""

    aliases = tuple(cube.alias for cube in cubes)
    nodes: list[dict[str, object]] = []
    definitions: list[dict[str, object]] = []
    instances: list[AnalyzedCubeInstance] = []
    for node_id, cube in enumerate(cubes, start=1):
        definition_id = f"definition-{node_id}"
        inputs = [
            {"name": str(name), "type": "*"}
            for name in _boundary_names(cube.buffer.get("inputs"))
        ]
        outputs = [
            {"name": str(name), "type": "*"}
            for name in _boundary_names(cube.buffer.get("outputs"))
        ]
        document = project_editable_cube_document(
            cube_id=cube.cube_id,
            version=cube.version,
            buffer=cube.buffer,
            canonical_metadata=cube.original_cube,
        )
        nodes.append(
            {
                "id": node_id,
                "type": definition_id,
                "mode": 4 if cube.bypassed else 0,
                "pos": [(node_id - 1) * 344, 0],
                "size": [320, 200],
                "inputs": inputs,
                "outputs": outputs,
                "properties": {
                    "cnr_id": "sugarcubes",
                    "sugarcubes_kind": "cube",
                    "sugarcubes_cube": {
                        "cube_id": cube.cube_id,
                        "cube_version": cube.version,
                        "instance_id": cube.alias,
                        "instance_alias": cube.alias,
                    },
                },
            }
        )
        definitions.append(
            {
                "id": definition_id,
                "name": cube.alias,
                "nodes": [],
                "links": [],
                "inputs": deepcopy(inputs),
                "outputs": deepcopy(outputs),
                "extra": {
                    "sugarcubes_kind": "cube",
                    "sugarcubes_document": document,
                },
            }
        )
        instances.append(
            AnalyzedCubeInstance(
                instance_id=cube.alias,
                node_id=str(node_id),
                definition_id=definition_id,
                cube_id=cube.cube_id,
                cube_version=cube.version,
                alias=cube.alias,
                execution_mode=4 if cube.bypassed else 0,
            )
        )
    source_workflow: dict[str, object] = {
        "version": 0.4,
        "nodes": nodes,
        "links": [],
        "definitions": {"subgraphs": definitions},
    }
    analysis = CanonicalCubeGraphAnalysis(
        workflow_semantic_hash="fixture-from-states",
        instances=tuple(instances),
        edges=(),
        proximity_edges=(),
        segments=(
            AnalyzedCubeSegment(
                instance_ids=aliases,
                reorderable=len(aliases) > 1,
                boundary_node_ids=(),
            ),
        )
        if aliases
        else (),
        workflow=source_workflow,
    )
    return WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("cube-graph.json"),
            source_workflow=source_workflow,
            buffer={"nodes": {}},
            cube_analysis=analysis,
        )
    )


def _boundary_names(value: object) -> tuple[str, ...]:
    """Return fixture boundary keys in declared order."""

    return tuple(str(name) for name in value) if isinstance(value, dict) else ()


__all__ = [
    "graph_backed_cube_workflow",
    "graph_backed_cube_workflow_from_states",
]
