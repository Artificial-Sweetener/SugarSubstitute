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

"""Build typed node-behavior snapshots from concise test scenarios."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    NodeBehaviorService,
)


class DummyNodeDefinitionGateway:
    """Return deterministic live node definitions for behavior tests."""

    def __init__(
        self, definitions: Mapping[str, Mapping[str, object]] | None = None
    ) -> None:
        """Store optional class-type definitions keyed by node class."""

        self._definitions = dict(definitions or {})

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one class definition in the gateway payload shape."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one required class definition in the gateway payload shape."""

        definition = self._definitions.get(node_class)
        if definition is None:
            return {}
        return {node_class: dict(definition)}


def cube_state(
    *,
    nodes: Mapping[str, object] | None = None,
    definitions: Mapping[str, object] | None = None,
    subgraphs: object | None = None,
    ui: dict[str, object] | None = None,
) -> SimpleNamespace:
    """Build a minimal cube-state double compatible with NodeBehaviorService."""

    return SimpleNamespace(
        buffer={
            "nodes": dict(nodes or {}),
            "definitions": dict(definitions or {}),
            "subgraphs": subgraphs if subgraphs is not None else [],
        },
        dirty=False,
        ui=dict(ui or {}),
    )


def live_definition_for_inputs(
    inputs: Mapping[str, object],
) -> dict[str, object]:
    """Build minimal live metadata for card tests whose concern is not hydration."""

    required: dict[str, object] = {}
    for field_key, value in inputs.items():
        field_type = (
            "BOOLEAN"
            if isinstance(value, bool)
            else "INT"
            if isinstance(value, int)
            else "FLOAT"
            if isinstance(value, float)
            else "STRING"
        )
        required[field_key] = [field_type, {}]
    return {"input": {"required": required}}


def build_behavior_snapshot(
    *,
    cube_states: Mapping[str, Any],
    stack_order: list[str],
    definitions_by_class: Mapping[str, Mapping[str, object]] | None = None,
    workflow_overrides: Mapping[str, object] | None = None,
    search_hidden_keys: set[object] | None = None,
    node_search_text: str | None = None,
    search_matching_nodes: set[tuple[str, str]] | None = None,
) -> EditorBehaviorSnapshot:
    """Build one snapshot with live definitions unless a test overrides them."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            _scenario_live_definitions(cube_states)
            if definitions_by_class is None
            else definitions_by_class
        )
    )
    return service.build_snapshot(
        cube_states=cube_states,
        stack_order=stack_order,
        workflow_overrides=workflow_overrides or {},
        search_hidden_keys=search_hidden_keys,
        node_search_text=node_search_text,
        search_matching_nodes=search_matching_nodes,
    )


def _scenario_live_definitions(
    cube_states: Mapping[str, Any],
) -> dict[str, Mapping[str, object]]:
    """Derive the live-definition baseline for unrelated behavior scenarios."""

    definitions: dict[str, Mapping[str, object]] = {}
    for state in cube_states.values():
        buffer = state if isinstance(state, Mapping) else getattr(state, "buffer", {})
        if not isinstance(buffer, Mapping):
            continue
        authored = buffer.get("definitions", {})
        authored_definitions = authored if isinstance(authored, Mapping) else {}
        _record_node_definitions(
            definitions,
            buffer.get("nodes", {}),
            authored_definitions,
            class_key="class_type",
        )
        subgraphs = buffer.get("subgraphs", ())
        if not isinstance(subgraphs, list):
            continue
        for subgraph in subgraphs:
            if not isinstance(subgraph, Mapping):
                continue
            _record_node_definitions(
                definitions,
                subgraph.get("nodes", ()),
                authored_definitions,
                class_key="type",
            )
    return definitions


def _record_node_definitions(
    target: dict[str, Mapping[str, object]],
    nodes: object,
    authored_definitions: Mapping[object, object],
    *,
    class_key: str,
) -> None:
    """Record available node classes with authored schema when present."""

    values = nodes.values() if isinstance(nodes, Mapping) else nodes
    if not isinstance(values, (list, tuple)) and not hasattr(values, "__iter__"):
        return
    for node in values:
        if not isinstance(node, Mapping):
            continue
        class_type = node.get(class_key)
        if not isinstance(class_type, str) or not class_type:
            continue
        authored = authored_definitions.get(class_type)
        target.setdefault(
            class_type,
            dict(authored) if isinstance(authored, Mapping) else {"input": {}},
        )


__all__ = [
    "DummyNodeDefinitionGateway",
    "build_behavior_snapshot",
    "cube_state",
    "live_definition_for_inputs",
]
