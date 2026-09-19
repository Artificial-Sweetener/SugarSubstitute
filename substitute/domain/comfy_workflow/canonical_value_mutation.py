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

"""Apply editor mutations to their canonical Comfy UI graph storage."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, MutableSequence
from copy import deepcopy

from .widget_values import node_widget_projection


def set_canonical_widget_value(
    workflow: MutableMapping[str, object],
    locator: Mapping[str, object],
    value: object,
) -> None:
    """Replace one serialized widget value at its converter-authored origin."""

    node = _canonical_node(workflow, locator)
    input_key = locator.get("input_key")
    if isinstance(input_key, str):
        inputs = node.get("inputs")
        if not isinstance(inputs, MutableMapping) or input_key not in inputs:
            raise ValueError(f"Canonical input mapping has no field {input_key!r}.")
        inputs[input_key] = deepcopy(value)
        return
    widgets = node.get("widgets_values")
    slot = locator.get("widget_slot")
    if isinstance(widgets, MutableMapping) and isinstance(slot, str):
        if slot not in widgets:
            raise ValueError(f"Canonical widget mapping has no field {slot!r}.")
        widgets[slot] = deepcopy(value)
        return
    if (
        isinstance(widgets, MutableSequence)
        and not isinstance(widgets, str | bytes)
        and isinstance(slot, int)
        and not isinstance(slot, bool)
        and 0 <= slot < len(widgets)
    ):
        widgets[slot] = deepcopy(value)
        return
    raise ValueError("Canonical widget locator does not match serialized storage.")


def set_canonical_node_value(
    workflow: MutableMapping[str, object],
    locator: Mapping[str, object],
    field_key: str,
    value: object,
) -> None:
    """Replace one canonical node property at its converter-authored origin."""

    node = _canonical_node(workflow, locator)
    node[field_key] = deepcopy(value)


def infer_canonical_node_origin(
    workflow: MutableMapping[str, object],
    node_name: str,
) -> dict[str, object] | None:
    """Infer a stable canonical node locator for a legacy editor projection."""

    api_node = _api_node(workflow, node_name)
    if api_node is not None:
        return {"definition_id": None, "node_id": node_name}
    resolved = _resolve_qualified_node(workflow, node_name)
    if resolved is None:
        return None
    _node, definition_id, _ancestors = resolved
    return {
        "definition_id": definition_id,
        "node_id": node_name.rsplit(":", 1)[-1],
    }


def infer_canonical_widget_origin(
    workflow: MutableMapping[str, object],
    node_name: str,
    field_key: str,
) -> dict[str, object] | None:
    """Infer one legacy projection field's serialized Comfy widget origin."""

    api_node = _api_node(workflow, node_name)
    api_inputs = api_node.get("inputs") if api_node is not None else None
    if isinstance(api_inputs, Mapping) and field_key in api_inputs:
        return {
            "definition_id": None,
            "node_id": node_name,
            "input_key": field_key,
        }
    resolved = _resolve_qualified_node(workflow, node_name)
    if resolved is None:
        return None
    node, definition_id, ancestors = resolved
    target_node_id = node_name.rsplit(":", 1)[-1]
    for ancestor_definition_id, ancestor in reversed(ancestors):
        properties = ancestor.get("properties")
        proxies = (
            properties.get("proxyWidgets") if isinstance(properties, Mapping) else None
        )
        values = ancestor.get("widgets_values")
        if not isinstance(proxies, list) or not isinstance(values, list):
            continue
        for index, proxy in enumerate(proxies):
            if (
                isinstance(proxy, list | tuple)
                and len(proxy) >= 2
                and str(proxy[0]) == target_node_id
                and str(proxy[1]) == field_key
                and index < len(values)
            ):
                return {
                    "definition_id": ancestor_definition_id,
                    "node_id": str(ancestor.get("id")),
                    "widget_slot": index,
                }
    projection = node_widget_projection(node)
    widget_slot = projection.slots.get(field_key)
    if widget_slot is None:
        return None
    return {
        "definition_id": definition_id,
        "node_id": str(node.get("id")),
        "widget_slot": widget_slot,
    }


def _canonical_node(
    workflow: MutableMapping[str, object],
    locator: Mapping[str, object],
) -> MutableMapping[str, object]:
    """Resolve one root or subgraph-definition node without interpreting topology."""

    node_id = locator.get("node_id")
    definition_id = locator.get("definition_id")
    if not isinstance(node_id, str) or (
        definition_id is not None and not isinstance(definition_id, str)
    ):
        raise ValueError("Canonical node locator is malformed.")
    nodes: object = workflow.get("nodes")
    if definition_id is not None:
        definitions = workflow.get("definitions")
        subgraphs = (
            definitions.get("subgraphs") if isinstance(definitions, Mapping) else None
        )
        if not isinstance(subgraphs, list):
            raise ValueError("Canonical graph has no subgraph definitions.")
        definition = next(
            (
                item
                for item in subgraphs
                if isinstance(item, Mapping) and item.get("id") == definition_id
            ),
            None,
        )
        nodes = definition.get("nodes") if isinstance(definition, Mapping) else None
    if isinstance(nodes, MutableMapping) and definition_id is None:
        candidate = nodes.get(node_id)
        node = candidate if isinstance(candidate, MutableMapping) else None
    elif isinstance(nodes, list):
        node = next(
            (
                item
                for item in nodes
                if isinstance(item, MutableMapping) and str(item.get("id")) == node_id
            ),
            None,
        )
    else:
        raise ValueError("Canonical graph scope has no node collection.")
    if node is None:
        raise ValueError(
            f"Canonical graph has no node {node_id!r} in the requested scope."
        )
    return node


def _api_node(
    workflow: MutableMapping[str, object],
    node_name: str,
) -> MutableMapping[str, object] | None:
    """Return one node from Comfy's API-format prompt graph."""

    nodes = workflow.get("nodes")
    if not isinstance(nodes, MutableMapping):
        return None
    candidate = nodes.get(node_name)
    return candidate if isinstance(candidate, MutableMapping) else None


def _resolve_qualified_node(
    workflow: MutableMapping[str, object],
    node_name: str,
) -> (
    tuple[
        MutableMapping[str, object],
        str | None,
        tuple[tuple[str | None, MutableMapping[str, object]], ...],
    ]
    | None
):
    """Resolve a converter-qualified node and retain its subgraph ancestors."""

    node_parts = node_name.split(":")
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        return None
    definitions = workflow.get("definitions")
    subgraphs_value = (
        definitions.get("subgraphs") if isinstance(definitions, Mapping) else None
    )
    subgraphs = subgraphs_value if isinstance(subgraphs_value, list) else []
    definitions_by_id = {
        str(definition.get("id")): definition
        for definition in subgraphs
        if isinstance(definition, Mapping) and definition.get("id") is not None
    }
    definition_id: str | None = None
    ancestors: list[tuple[str | None, MutableMapping[str, object]]] = []
    for index, node_id in enumerate(node_parts):
        node = next(
            (
                candidate
                for candidate in nodes
                if isinstance(candidate, MutableMapping)
                and str(candidate.get("id")) == node_id
            ),
            None,
        )
        if node is None:
            return None
        if index == len(node_parts) - 1:
            return node, definition_id, tuple(ancestors)
        ancestors.append((definition_id, node))
        next_definition_id = node.get("type")
        definition = definitions_by_id.get(str(next_definition_id))
        nested_nodes = (
            definition.get("nodes") if isinstance(definition, Mapping) else None
        )
        if not isinstance(next_definition_id, str) or not isinstance(
            nested_nodes, list
        ):
            return None
        definition_id = next_definition_id
        nodes = nested_nodes
    return None


__all__ = [
    "infer_canonical_node_origin",
    "infer_canonical_widget_origin",
    "set_canonical_node_value",
    "set_canonical_widget_value",
]
