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

"""Collect normalized live Comfy definitions for one authored graph section."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.ports import NodeDefinitionGateway


class WorkflowNodeDefinitionService:
    """Own graph-scoped live node-definition collection without refreshing UI state."""

    def __init__(
        self,
        node_definition_gateway: NodeDefinitionGateway | None = None,
    ) -> None:
        """Store the cached definition gateway used outside deterministic tests."""

        self._node_definition_gateway = node_definition_gateway

    def definitions_for_graph(
        self,
        graph: Mapping[str, object],
        supplied: Mapping[str, Mapping[str, object]] | None = None,
    ) -> dict[str, Mapping[str, object]]:
        """Return normalized definitions for every class represented in the graph."""

        definitions = dict(supplied or {})
        gateway = self._node_definition_gateway
        if gateway is None:
            return definitions
        for class_type in _graph_class_types(graph):
            if class_type in definitions:
                continue
            payload = gateway.get_node_definition(class_type)
            definition = unwrap_node_definition(payload, class_type)
            if definition:
                definitions[class_type] = definition
        return definitions


def unwrap_node_definition(
    payload: Mapping[str, object],
    class_type: str,
) -> Mapping[str, object]:
    """Accept gateway payloads containing either one definition or a class map."""

    nested = payload.get(class_type)
    if isinstance(nested, Mapping):
        return nested
    return payload if "input" in payload or "output" in payload else {}


def node_class_type(node: Mapping[str, object]) -> str:
    """Return the normalized backend class name for one authored node."""

    value = node.get("class_type")
    return value.strip() if isinstance(value, str) else ""


def graph_nodes(graph: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    """Return a normalized node mapping from one graph section."""

    raw_nodes = graph.get("nodes", {})
    if not isinstance(raw_nodes, Mapping):
        return {}
    return {
        str(node_name): node
        for node_name, node in raw_nodes.items()
        if isinstance(node, Mapping)
    }


def _graph_class_types(graph: Mapping[str, object]) -> tuple[str, ...]:
    """Return ordered unique class names represented by the graph."""

    return tuple(
        dict.fromkeys(
            class_type
            for node in graph_nodes(graph).values()
            if (class_type := node_class_type(node))
        )
    )


__all__ = [
    "WorkflowNodeDefinitionService",
    "graph_nodes",
    "node_class_type",
    "unwrap_node_definition",
]
