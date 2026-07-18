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

"""Index typed authored graph topology for reusable workflow semantic analysis."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.workflows.workflow_node_definition_service import (
    graph_nodes,
    node_class_type,
)

SPATIAL_SOCKET_TYPES = frozenset({"IMAGE", "LATENT", "MASK"})
CANVAS_SOURCE_SOCKET_TYPES = frozenset({"IMAGE", "LATENT"})


@dataclass(frozen=True, slots=True)
class WorkflowGraphEdge:
    """Describe one authored provider socket connected to a consumer input."""

    provider_name: str
    output_index: int
    output_type: str | None
    consumer_name: str
    consumer_field_key: str
    input_type: str | None

    @property
    def spatial_type(self) -> str | None:
        """Return a trusted spatial carrier type when either socket declares one."""

        if self.output_type in SPATIAL_SOCKET_TYPES:
            return self.output_type
        if self.input_type in SPATIAL_SOCKET_TYPES:
            return self.input_type
        return None


class WorkflowGraphTopology:
    """Provide typed edge, reachability, and spatial-root queries for one section."""

    def __init__(
        self,
        graph: Mapping[str, object],
        node_definitions: Mapping[str, Mapping[str, object]],
    ) -> None:
        """Normalize graph nodes and typed connections once for downstream services."""

        self._nodes = graph_nodes(graph)
        self._definitions = node_definitions
        self._edges = self._build_edges()
        outgoing: dict[str, list[WorkflowGraphEdge]] = {}
        incoming: dict[str, list[WorkflowGraphEdge]] = {}
        for edge in self._edges:
            outgoing.setdefault(edge.provider_name, []).append(edge)
            incoming.setdefault(edge.consumer_name, []).append(edge)
        self._outgoing = {key: tuple(value) for key, value in outgoing.items()}
        self._incoming = {key: tuple(value) for key, value in incoming.items()}

    @property
    def nodes(self) -> Mapping[str, Mapping[str, object]]:
        """Return normalized authored nodes by stable node name."""

        return self._nodes

    @property
    def edges(self) -> tuple[WorkflowGraphEdge, ...]:
        """Return every normalized connection in authored order."""

        return self._edges

    def output_types(self, node_name: str) -> tuple[str, ...]:
        """Return normalized live output types for one node."""

        node = self._nodes.get(node_name, {})
        definition = self._definitions.get(node_class_type(node), {})
        output = definition.get("output")
        if not isinstance(output, (list, tuple)):
            return ()
        return tuple(str(value).upper() for value in output)

    def outgoing_edges(
        self,
        node_name: str,
        output_index: int | None = None,
    ) -> tuple[WorkflowGraphEdge, ...]:
        """Return outgoing connections, optionally restricted to one output socket."""

        edges = self._outgoing.get(node_name, ())
        if output_index is None:
            return edges
        return tuple(edge for edge in edges if edge.output_index == output_index)

    def incoming_edges(self, node_name: str) -> tuple[WorkflowGraphEdge, ...]:
        """Return incoming connections for one node."""

        return self._incoming.get(node_name, ())

    def connected_spatial_inputs(
        self,
        node_name: str,
    ) -> tuple[WorkflowGraphEdge, ...]:
        """Return connected inputs carrying image, latent, or mask spatial state."""

        return tuple(
            edge
            for edge in self.incoming_edges(node_name)
            if edge.spatial_type in SPATIAL_SOCKET_TYPES
        )

    def canvas_source_sockets(self) -> tuple[tuple[str, int, str], ...]:
        """Return IMAGE/LATENT output sockets on nodes that create spatial state."""

        sockets: list[tuple[str, int, str]] = []
        for node_name in self._nodes:
            if self.connected_spatial_inputs(node_name):
                continue
            for output_index, output_type in enumerate(self.output_types(node_name)):
                if output_type in CANVAS_SOURCE_SOCKET_TYPES:
                    sockets.append((node_name, output_index, output_type))
        return tuple(sockets)

    def downstream_distances_from_socket(
        self,
        node_name: str,
        output_index: int,
    ) -> dict[str, int]:
        """Return shortest downstream node distances reached through one output socket."""

        initial = tuple(
            edge.consumer_name for edge in self.outgoing_edges(node_name, output_index)
        )
        distances: dict[str, int] = {}
        pending: deque[tuple[str, int]] = deque((name, 1) for name in initial)
        while pending:
            current, distance = pending.popleft()
            prior = distances.get(current)
            if prior is not None and prior <= distance:
                continue
            distances[current] = distance
            for edge in self.outgoing_edges(current):
                pending.append((edge.consumer_name, distance + 1))
        return distances

    def input_value(self, node_name: str, field_key: str) -> object | None:
        """Return one authored input value from a normalized graph node."""

        node = self._nodes.get(node_name, {})
        inputs = node.get("inputs", {})
        return inputs.get(field_key) if isinstance(inputs, Mapping) else None

    def input_keys(self, node_name: str) -> tuple[str, ...]:
        """Return live-definition input keys in declared order for one node."""

        node = self._nodes.get(node_name, {})
        definition = self._definitions.get(node_class_type(node), {})
        input_groups = definition.get("input", {})
        if not isinstance(input_groups, Mapping):
            return ()
        keys: list[str] = []
        for group_name in ("required", "optional"):
            group = input_groups.get(group_name, {})
            if not isinstance(group, Mapping):
                continue
            keys.extend(str(key) for key in group)
        return tuple(dict.fromkeys(keys))

    def _build_edges(self) -> tuple[WorkflowGraphEdge, ...]:
        """Normalize graph links and attach exact live socket types where available."""

        edges: list[WorkflowGraphEdge] = []
        for consumer_name, node in self._nodes.items():
            raw_inputs = node.get("inputs", {})
            if not isinstance(raw_inputs, Mapping):
                continue
            for raw_field_key, value in raw_inputs.items():
                if not _is_link(value):
                    continue
                provider_name = str(value[0])
                output_index = value[1]
                if provider_name not in self._nodes:
                    continue
                field_key = str(raw_field_key)
                output_types = self.output_types(provider_name)
                output_type = (
                    output_types[output_index]
                    if 0 <= output_index < len(output_types)
                    else None
                )
                edges.append(
                    WorkflowGraphEdge(
                        provider_name=provider_name,
                        output_index=output_index,
                        output_type=output_type,
                        consumer_name=consumer_name,
                        consumer_field_key=field_key,
                        input_type=self._input_type(consumer_name, field_key),
                    )
                )
        return tuple(edges)

    def _input_type(self, node_name: str, field_key: str) -> str | None:
        """Return one declared live input socket type."""

        node = self._nodes.get(node_name, {})
        definition = self._definitions.get(node_class_type(node), {})
        groups = definition.get("input", {})
        if not isinstance(groups, Mapping):
            return None
        for group_name in ("required", "optional"):
            group = groups.get(group_name, {})
            if not isinstance(group, Mapping):
                continue
            field_info = group.get(field_key)
            if not isinstance(field_info, (list, tuple)) or not field_info:
                continue
            declared = field_info[0]
            return declared.upper() if isinstance(declared, str) else None
        return None


def _is_link(value: object) -> bool:
    """Return whether a graph input is a normalized node/output connection."""

    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    )


__all__ = [
    "CANVAS_SOURCE_SOCKET_TYPES",
    "SPATIAL_SOCKET_TYPES",
    "WorkflowGraphEdge",
    "WorkflowGraphTopology",
]
