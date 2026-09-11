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

"""Provide SugarCubes gateway doubles for graph-backed Cube stack tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace

from substitute.application.cubes import CubeStackService
from substitute.application.cubes.graph_backed_cube_stack_service import (
    CubeGraphGateway,
    GraphBackedCubeStackService,
)
from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis
from substitute.domain.comfy_workflow.cube_analysis import (
    AnalyzedCubeEdge,
    AnalyzedCubeInstance,
    AnalyzedCubeSegment,
    CubeGraphEdgeOrigin,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState


def _graph_stack_service(gateway: CubeGraphGateway) -> CubeStackService:
    """Build the application service around one SugarCubes boundary double."""

    return CubeStackService(GraphBackedCubeStackService(gateway))


class _GraphGateway:
    """Return deterministic canonical analyses for application orchestration tests."""

    def __init__(self, workflow: WorkflowState) -> None:
        """Capture the initial SugarCubes-owned analysis."""

        assert workflow.direct_workflow is not None
        assert workflow.direct_workflow.cube_analysis is not None
        self._analysis = workflow.direct_workflow.cube_analysis
        self.reorder_requests: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Reflect alias and mode fields as if SugarCubes reanalyzed the graph."""

        nodes = workflow.get("nodes")
        node_index = (
            {str(node.get("id")): node for node in nodes if isinstance(node, dict)}
            if isinstance(nodes, list)
            else {}
        )
        instances = []
        for instance in self._analysis.instances:
            node = node_index[instance.node_id]
            properties = node.get("properties")
            marker = (
                properties.get("sugarcubes_cube")
                if isinstance(properties, dict)
                else {}
            )
            alias = marker.get("instance_alias") if isinstance(marker, dict) else None
            mode = node.get("mode", 0)
            instances.append(
                replace(
                    instance,
                    alias=alias if isinstance(alias, str) else instance.alias,
                    execution_mode=mode if isinstance(mode, int) else 0,
                )
            )
        self._analysis = replace(
            self._analysis,
            instances=tuple(instances),
            workflow=deepcopy(workflow),
        )
        return self._analysis

    def reorder(
        self,
        workflow: JsonObject,
        *,
        segment_instance_ids: Sequence[str],
        ordered_instance_ids: Sequence[str],
    ) -> CanonicalCubeGraphAnalysis:
        """Return the requested segment order without reimplementing graph rules."""

        current = tuple(segment_instance_ids)
        requested = tuple(ordered_instance_ids)
        self.reorder_requests.append((current, requested))
        segments = tuple(
            replace(segment, instance_ids=requested)
            if segment.instance_ids == current
            else segment
            for segment in self._analysis.segments
        )
        self._analysis = replace(
            self._analysis,
            segments=segments,
            workflow=deepcopy(workflow),
        )
        return self._analysis

    def append_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        alias: str,
        bypassed: bool,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unused Cube append calls in existing-graph behavior tests."""

        raise AssertionError("This gateway fixture does not append Cubes.")

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unused graph creation calls in existing-graph tests."""

        raise AssertionError("This gateway fixture does not create workflows.")

    def remove_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unused Cube removal calls in existing-graph behavior tests."""

        raise AssertionError("This gateway fixture does not remove Cubes.")


class _InvalidAnalysisGateway(_GraphGateway):
    """Return a response whose Cube instance has no embedded definition."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Corrupt only the response graph to exercise atomic validation."""

        analysis = super().analyze(workflow)
        malformed = deepcopy(analysis.workflow)
        malformed["definitions"] = {"subgraphs": []}
        return replace(analysis, workflow=malformed)


class _StructuralGraphGateway:
    """Project marked Cube identities without interpreting ordinary nodes."""

    def __init__(self) -> None:
        """Initialize analysis-call accounting."""

        self.analyzed_workflows = 0

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return a deterministic projection for composer orchestration tests."""

        self.analyzed_workflows += 1
        nodes = workflow.get("nodes")
        marked = (
            [
                node
                for node in nodes
                if isinstance(node, dict) and _cube_marker(node) is not None
            ]
            if isinstance(nodes, list)
            else []
        )
        instances = tuple(
            AnalyzedCubeInstance(
                instance_id=str(marker["instance_id"]),
                node_id=str(node["id"]),
                definition_id=str(node["type"]),
                cube_id=str(marker["cube_id"]),
                cube_version=str(marker["cube_version"]),
                alias=str(marker["instance_alias"]),
                execution_mode=int(node.get("mode", 0)),
            )
            for node in marked
            if (marker := _cube_marker(node)) is not None
        )
        edges = tuple(
            AnalyzedCubeEdge(
                source_instance_id=source.instance_id,
                source_binding="image",
                target_instance_id=target.instance_id,
                target_binding="image",
                origin=CubeGraphEdgeOrigin.PROXIMITY,
            )
            for source, target in zip(instances, instances[1:])
        )
        return CanonicalCubeGraphAnalysis(
            workflow_semantic_hash=f"structural-{self.analyzed_workflows}",
            instances=instances,
            edges=edges,
            proximity_edges=edges,
            segments=(
                AnalyzedCubeSegment(
                    instance_ids=tuple(instance.instance_id for instance in instances),
                    reorderable=len(instances) > 1,
                    boundary_node_ids=(),
                ),
            )
            if instances
            else (),
            workflow=deepcopy(workflow),
        )

    def reorder(
        self,
        workflow: JsonObject,
        *,
        segment_instance_ids: Sequence[str],
        ordered_instance_ids: Sequence[str],
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unused reorder calls in structural mutation tests."""

        raise AssertionError("Structural mutation tests do not reorder Cubes.")

    def append_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        alias: str,
        bypassed: bool,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Return one server-shaped graph after a simulated append response."""

        return self.analyze(
            _append_test_cube(
                workflow,
                alias=alias,
                instance_id=instance_id,
                bypassed=bypassed,
                document=document,
            )
        )

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Reject unused graph creation calls in structural mutation tests."""

        raise AssertionError("Structural mutation tests do not create workflows.")

    def remove_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Return one server-shaped graph after a simulated removal response."""

        analysis = self.analyze(workflow)
        instance = next(
            candidate
            for candidate in analysis.instances
            if candidate.instance_id == instance_id
        )
        return self.analyze(_remove_test_cube(workflow, node_id=instance.node_id))


def _append_test_cube(
    workflow: JsonObject,
    *,
    alias: str,
    instance_id: str,
    bypassed: bool,
    document: JsonObject,
) -> JsonObject:
    """Build a minimal server response fixture without production graph logic."""

    graph = deepcopy(workflow)
    nodes = graph.setdefault("nodes", [])
    definitions = graph.setdefault("definitions", {})
    if not isinstance(nodes, list) or not isinstance(definitions, dict):
        raise AssertionError("fixture graph is malformed")
    subgraphs = definitions.setdefault("subgraphs", [])
    if not isinstance(subgraphs, list):
        raise AssertionError("fixture definitions are malformed")
    node_id = f"fixture-node-{len(nodes) + 1}"
    definition_id = f"fixture-definition-{len(subgraphs) + 1}"
    marker = {
        "cube_id": document["cube_id"],
        "cube_version": document["version"],
        "instance_id": instance_id,
        "instance_alias": alias,
    }
    nodes.append(
        {
            "id": node_id,
            "type": definition_id,
            "mode": 4 if bypassed else 0,
            "properties": {
                "sugarcubes_kind": "cube",
                "sugarcubes_cube": marker,
            },
        }
    )
    subgraphs.append(
        {
            "id": definition_id,
            "extra": {
                "sugarcubes_kind": "cube",
                "sugarcubes_document": deepcopy(document),
            },
        }
    )
    return graph


def _remove_test_cube(workflow: JsonObject, *, node_id: str) -> JsonObject:
    """Remove fixture records using the already-resolved exact node identity."""

    graph = deepcopy(workflow)
    nodes = graph.get("nodes")
    definitions = graph.get("definitions")
    subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if (
        not isinstance(nodes, list)
        or not isinstance(definitions, dict)
        or not isinstance(subgraphs, list)
    ):
        raise AssertionError("fixture graph is malformed")
    removed = next(node for node in nodes if str(node.get("id")) == node_id)
    definition_id = removed["type"]
    graph["nodes"] = [node for node in nodes if str(node.get("id")) != node_id]
    definitions["subgraphs"] = [
        definition for definition in subgraphs if definition.get("id") != definition_id
    ]
    return graph


def _cube_marker(node: dict[str, object]) -> dict[str, object] | None:
    """Return one test Cube identity marker when present."""

    properties = node.get("properties")
    marker = properties.get("sugarcubes_cube") if isinstance(properties, dict) else None
    return marker if isinstance(marker, dict) else None


def _cube_state(alias: str) -> CubeState:
    """Return one editable Cube accepted by native graph composition."""

    implementation: JsonObject = {
        "nodes": {},
        "inputs": {"image": ["node", 0]},
        "outputs": {"image": ["node", 0]},
    }
    document: JsonObject = {
        "cube_id": f"test/{alias}.cube",
        "version": "1.0.0",
        "implementation": deepcopy(implementation),
    }
    return CubeState(
        cube_id=f"test/{alias}.cube",
        version="1.0.0",
        alias=alias,
        original_cube=deepcopy(document),
        buffer=implementation,
        ui={"canonical_cube": document},
    )
