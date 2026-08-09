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

"""Discover regional prompt and mask relationships from workflow topology."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import InputAssetCardinality, WorkflowState


@dataclass(frozen=True, slots=True)
class RegionalPromptTopology:
    """Bind one ordered mask endpoint to its upstream prompt-source nodes."""

    association_key: MaskAssociationKey
    prompt_node_names: tuple[str, ...]


class RegionalPromptTopologyService:
    """Resolve regional prompt sources through graph/socket identity only."""

    def __init__(
        self,
        graph_sections: WorkflowGraphSectionService | None = None,
        input_endpoints: InputAssetEndpointService | None = None,
    ) -> None:
        """Store the graph-section authority used for relationship discovery."""

        self._graph_sections = graph_sections or WorkflowGraphSectionService()
        self._input_endpoints = input_endpoints or InputAssetEndpointService()

    def topologies(
        self,
        workflow: WorkflowState,
    ) -> tuple[RegionalPromptTopology, ...]:
        """Return topology for every authored ordered mask collection."""

        topologies: list[RegionalPromptTopology] = []
        for association_key in workflow.canvas.regional_mask_collections:
            section_key, mask_node_name = association_key
            graph = self._graph_sections.graph(workflow, section_key)
            if graph is None:
                continue
            prompt_nodes = _prompt_sources_for_mask(graph, mask_node_name)
            topologies.append(
                RegionalPromptTopology(
                    association_key=association_key,
                    prompt_node_names=prompt_nodes,
                )
            )
        return tuple(topologies)

    def topology_for_mask(
        self,
        workflow: WorkflowState,
        association_key: MaskAssociationKey,
    ) -> RegionalPromptTopology | None:
        """Return the topology belonging to one exact ordered mask endpoint."""

        return next(
            (
                topology
                for topology in self.topologies(workflow)
                if topology.association_key == association_key
            ),
            None,
        )

    def topology_for_prompt(
        self,
        workflow: WorkflowState,
        section_key: str,
        prompt_node_name: str,
    ) -> RegionalPromptTopology | None:
        """Return the ordered mask endpoint related to one prompt source node."""

        return next(
            (
                topology
                for topology in self.topologies(workflow)
                if topology.association_key[0] == section_key
                and prompt_node_name in topology.prompt_node_names
            ),
            None,
        )

    def topology_for_prompt_endpoint(
        self,
        workflow: WorkflowState,
        section_key: str,
        prompt_node_name: str,
        field_key: str,
    ) -> RegionalPromptTopology | None:
        """Return regional topology only for one exact graph-backed prompt field."""

        topology = self.topology_for_prompt(
            workflow,
            section_key,
            prompt_node_name,
        )
        if topology is None:
            topology = self._ordered_endpoint_topology_for_prompt(
                workflow,
                section_key,
                prompt_node_name,
            )
        if topology is None:
            return None
        graph = self._graph_sections.graph(workflow, section_key)
        if graph is None:
            return None
        node = _nodes(graph).get(prompt_node_name)
        inputs = node.get("inputs") if node is not None else None
        if (
            field_key not in {"value", "text"}
            or not isinstance(inputs, dict)
            or not isinstance(inputs.get(field_key), str)
        ):
            return None
        return topology

    def _ordered_endpoint_topology_for_prompt(
        self,
        workflow: WorkflowState,
        section_key: str,
        prompt_node_name: str,
    ) -> RegionalPromptTopology | None:
        """Resolve prompt topology before ordered mask state is materialized."""

        graph = self._graph_sections.graph(workflow, section_key)
        if graph is None:
            return None
        endpoints = self._input_endpoints.build_index(section_key, graph)
        for endpoint in endpoints.mask_endpoints:
            if endpoint.cardinality is not InputAssetCardinality.ORDERED:
                continue
            prompt_nodes = _prompt_sources_for_mask(graph, endpoint.node_name)
            if prompt_node_name in prompt_nodes:
                return RegionalPromptTopology(
                    association_key=(section_key, endpoint.node_name),
                    prompt_node_names=prompt_nodes,
                )
        return None


def prompt_text(graph: dict[str, object], node_name: str) -> str | None:
    """Return authored prompt text for one topology-confirmed primitive node."""

    nodes = _nodes(graph)
    node = nodes.get(node_name)
    if node is None or node.get("class_type") != "PrimitiveStringMultiline":
        return None
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        return None
    for field_key in ("value", "text"):
        value = inputs.get(field_key)
        if isinstance(value, str):
            return value
    return None


def _prompt_sources_for_mask(
    graph: dict[str, object],
    mask_node_name: str,
) -> tuple[str, ...]:
    """Return primitive prompt nodes reaching a mask consumer within three hops."""

    nodes = _nodes(graph)
    consumers = tuple(
        node_name
        for node_name, node in nodes.items()
        if mask_node_name in _input_sources(node)
    )
    prompt_nodes: list[str] = []
    visited = set(consumers)
    frontier = list(consumers)
    for _depth in range(3):
        next_frontier: list[str] = []
        for node_name in frontier:
            node = nodes[node_name]
            for source_name in _input_sources(node):
                if source_name in visited or source_name not in nodes:
                    continue
                visited.add(source_name)
                source_node = nodes[source_name]
                if source_node.get("class_type") == "PrimitiveStringMultiline":
                    prompt_nodes.append(source_name)
                    continue
                next_frontier.append(source_name)
        frontier = next_frontier
    return tuple(dict.fromkeys(prompt_nodes))


def _nodes(graph: dict[str, object]) -> dict[str, dict[str, object]]:
    """Return a typed node mapping from one workflow graph payload."""

    raw_nodes = graph.get("nodes")
    if not isinstance(raw_nodes, dict):
        return {}
    return {
        str(node_name): node
        for node_name, node in raw_nodes.items()
        if isinstance(node, dict)
    }


def _input_sources(node: dict[str, object]) -> tuple[str, ...]:
    """Return graph-link source node names from one node input mapping."""

    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        return ()
    sources = tuple(
        source
        for value in inputs.values()
        if (source := _link_source(value)) is not None
    )
    return tuple(dict.fromkeys(sources))


def _link_source(value: object) -> str | None:
    """Return a source node name from supported Comfy link encodings."""

    if (
        isinstance(value, list | tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    ):
        return value[0]
    if isinstance(value, str):
        source, separator, port = value.rpartition(" ")
        if separator and source and port.isdigit():
            return source
    return None


__all__ = [
    "RegionalPromptTopology",
    "RegionalPromptTopologyService",
    "prompt_text",
]
