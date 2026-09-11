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

"""Apply stack intent through SugarCubes-owned canonical graph operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from substitute.domain.comfy_workflow import (
    CanonicalCubeGraphAnalysis,
    apply_cached_cube_reorder,
)
from substitute.domain.comfy_workflow.models import DirectWorkflowState
from substitute.domain.common import JsonObject
from substitute.domain.cubes import project_editable_cube_document
from substitute.domain.workflow import CubeState, WorkflowState


class CubeGraphGateway(Protocol):
    """Expose SugarCubes' bounded analysis and graph-mutation contract."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Normalize and analyze one complete native workflow."""

    def reorder(
        self,
        workflow: JsonObject,
        *,
        segment_instance_ids: Sequence[str],
        ordered_instance_ids: Sequence[str],
    ) -> CanonicalCubeGraphAnalysis:
        """Atomically reorder one SugarCubes-authorized segment."""

    def append_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        alias: str,
        bypassed: bool,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Append one exact Cube through SugarCubes' graph owner."""

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Create one native graph from an ordered legacy Cube stack."""

    def remove_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Remove one recognized Cube through SugarCubes' graph owner."""


class GraphBackedCubeStackService:
    """Translate stack actions into authoritative SugarCubes graph operations."""

    def __init__(
        self,
        gateway: CubeGraphGateway,
    ) -> None:
        """Bind the sole owner of Cube topology and graph mutation semantics."""

        self._gateway = gateway

    def add_cube(
        self,
        workflow: WorkflowState,
        cube: CubeState,
    ) -> None:
        """Insert one Cube into the owning graph and re-project all Cube views."""

        direct = workflow.direct_workflow
        if direct is None and workflow.cubes:
            raise ValueError("Legacy Cube state must be migrated before adding a Cube.")
        graph = (
            self._editable_graph(direct.source_workflow)
            if direct is not None
            else _empty_native_graph()
        )
        analysis = self._gateway.append_cube(
            graph,
            instance_id=str(uuid4()),
            alias=cube.alias,
            bypassed=cube.bypassed,
            document=self._document(cube),
        )
        if direct is None:
            workflow.install_canonical_graph(
                DirectWorkflowState(
                    source_path=Path(),
                    source_workflow=analysis.workflow,
                    buffer={"nodes": {}},
                    cube_analysis=analysis,
                    dirty=True,
                ),
                projection_sources={cube.alias: cube},
            )
            return
        self._install_analysis(
            workflow,
            analysis,
            projection_sources={cube.alias: cube},
        )

    def remove_cube(self, workflow: WorkflowState, alias: str) -> None:
        """Remove one projected Cube without altering unrelated native graph content."""

        direct = self._direct_document(workflow)
        cube = workflow.cubes.get(alias)
        ui = cube.ui if cube is not None else None
        node_id = ui.get("graph_node_id") if isinstance(ui, dict) else None
        if node_id is None:
            raise ValueError(f"Cube {alias!r} has no owning Comfy graph node.")
        analysis = self._analysis(workflow)
        instance = next(
            (
                candidate
                for candidate in analysis.instances
                if candidate.node_id == str(node_id)
            ),
            None,
        )
        if instance is None:
            raise ValueError(f"Cube {alias!r} has no canonical instance identity.")
        self._install_analysis(
            workflow,
            self._gateway.remove_cube(
                self._editable_graph(direct.source_workflow),
                instance_id=instance.instance_id,
            ),
        )

    def apply_reordered_aliases(
        self,
        workflow: WorkflowState,
        new_order: Sequence[str],
    ) -> None:
        """Reorder one eligible Cube segment without crossing fixed boundaries."""

        self._direct_document(workflow)
        analysis = self._analysis(workflow)
        current_order = tuple(workflow.stack_order)
        requested = tuple(new_order)
        if len(requested) != len(set(requested)) or set(requested) != set(
            current_order
        ):
            raise ValueError("Cube reorder must be an exact workflow permutation.")
        instances_by_id = {
            instance.instance_id: instance for instance in analysis.instances
        }
        current_analysis = analysis
        changed = False
        for original_segment in analysis.segments:
            aliases = tuple(
                instances_by_id[instance_id].alias
                for instance_id in original_segment.instance_ids
            )
            original_positions = tuple(current_order.index(alias) for alias in aliases)
            requested_aliases = tuple(
                requested[position] for position in original_positions
            )
            if set(requested_aliases) != set(aliases):
                raise ValueError(
                    "Cube reorder cannot cross an ordinary graph boundary."
                )
            if requested_aliases == aliases:
                continue
            if not original_segment.reorderable:
                raise ValueError("Fixed Cube graph segments cannot be reordered.")
            instance_id_by_alias = {
                instances_by_id[instance_id].alias: instance_id
                for instance_id in original_segment.instance_ids
            }
            current_segment = next(
                segment
                for segment in current_analysis.segments
                if set(segment.instance_ids) == set(original_segment.instance_ids)
            )
            current_analysis = apply_cached_cube_reorder(
                current_analysis,
                segment_instance_ids=current_segment.instance_ids,
                ordered_instance_ids=tuple(
                    instance_id_by_alias[alias] for alias in requested_aliases
                ),
            )
            changed = True
        if not changed:
            return
        self._install_analysis(workflow, current_analysis)
        if tuple(workflow.stack_order) != requested:
            raise ValueError(
                "Reordered Cube graph did not produce the requested order."
            )

    def set_bypassed(
        self,
        workflow: WorkflowState,
        alias: str,
        bypassed: bool,
    ) -> bool:
        """Persist one Cube activation change in its owning native node mode."""

        graph, node = self._mutable_graph_and_node(workflow, alias)
        next_mode = 4 if bypassed else 0
        if node.get("mode", 0) == next_mode:
            return False
        node["mode"] = next_mode
        self._install_analysis(workflow, self._gateway.analyze(graph))
        return True

    def rename(
        self,
        workflow: WorkflowState,
        old_alias: str,
        new_alias: str,
    ) -> None:
        """Persist an alias through canonical graph metadata and reanalysis."""

        graph, node = self._mutable_graph_and_node(workflow, old_alias)
        properties = node.get("properties")
        marker = (
            properties.get("sugarcubes_cube") if isinstance(properties, dict) else None
        )
        if not isinstance(marker, dict):
            raise ValueError(f"Cube {old_alias!r} has no canonical identity marker.")
        marker["instance_alias"] = new_alias
        definitions = graph.get("definitions")
        subgraphs = (
            definitions.get("subgraphs") if isinstance(definitions, dict) else None
        )
        if isinstance(subgraphs, list):
            for definition in subgraphs:
                if isinstance(definition, dict) and definition.get("id") == node.get(
                    "type"
                ):
                    definition["name"] = new_alias
                    break
        self._install_analysis(workflow, self._gateway.analyze(graph))

    @staticmethod
    def _direct_document(workflow: WorkflowState) -> DirectWorkflowState:
        """Return the owning direct document for one graph-backed workflow."""

        direct = workflow.direct_workflow
        if direct is None or not workflow.is_graph_backed_cube_workflow:
            raise ValueError("Workflow is not backed by a canonical Cube graph.")
        return direct

    def _analysis(self, workflow: WorkflowState) -> CanonicalCubeGraphAnalysis:
        """Return required SugarCubes analysis for a graph-backed document."""

        analysis = self._direct_document(workflow).cube_analysis
        if analysis is None:
            raise ValueError("Canonical Cube graph analysis is unavailable.")
        return analysis

    def _mutable_graph_and_node(
        self,
        workflow: WorkflowState,
        alias: str,
    ) -> tuple[JsonObject, dict[str, object]]:
        """Copy the full graph and return one projected Cube's owning node."""

        direct = self._direct_document(workflow)
        cube = workflow.cubes.get(alias)
        if cube is None:
            raise ValueError(f"Cube {alias!r} is unavailable.")
        ui = cube.ui
        node_id = ui.get("graph_node_id") if isinstance(ui, dict) else None
        graph = self._editable_graph(direct.source_workflow)
        nodes = graph.get("nodes")
        node = (
            next(
                (
                    candidate
                    for candidate in nodes
                    if isinstance(candidate, dict)
                    and str(candidate.get("id")) == str(node_id)
                ),
                None,
            )
            if isinstance(nodes, list)
            else None
        )
        if not isinstance(node, dict):
            raise ValueError(f"Cube {alias!r} has no owning Comfy graph node.")
        return graph, node

    @staticmethod
    def _editable_graph(source_workflow: JsonObject) -> JsonObject:
        """Copy graph authority for one atomic structural operation."""

        return deepcopy(source_workflow)

    @staticmethod
    def _document(cube: CubeState) -> JsonObject:
        """Project one editable document without interpreting its boundaries."""

        canonical = cube.ui.get("canonical_cube") if isinstance(cube.ui, dict) else None
        return project_editable_cube_document(
            cube_id=cube.cube_id,
            version=cube.version,
            buffer=cube.buffer,
            canonical_metadata=canonical if isinstance(canonical, dict) else None,
        )

    @staticmethod
    def _install_analysis(
        workflow: WorkflowState,
        analysis: CanonicalCubeGraphAnalysis,
        *,
        projection_sources: Mapping[str, CubeState] | None = None,
    ) -> None:
        """Replace graph authority while retaining supplied loaded Cube state."""

        direct = workflow.direct_workflow
        if direct is None:
            raise ValueError("Workflow does not own a canonical Comfy graph.")
        candidate = DirectWorkflowState(
            source_path=direct.source_path,
            source_workflow=analysis.workflow,
            buffer=direct.buffer,
            ui=direct.ui,
            dirty=True,
            cube_analysis=analysis,
        )
        WorkflowState(direct_workflow=candidate)
        workflow.install_canonical_graph(
            candidate,
            projection_sources=projection_sources,
        )


def _empty_native_graph() -> JsonObject:
    """Return the smallest lossless Comfy graph envelope for first insertion."""

    return {
        "version": 0.4,
        "nodes": [],
        "links": [],
        "definitions": {"subgraphs": []},
        "extra": {},
    }


__all__ = ["CubeGraphGateway", "GraphBackedCubeStackService"]
