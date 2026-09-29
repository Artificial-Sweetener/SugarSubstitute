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

"""Inventory executable nodes from persisted Comfy workflow facts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeGuard

from .node_roles import WorkflowNodeExecutionRole, known_execution_role


@dataclass(frozen=True, slots=True)
class PersistedNodepackHint:
    """Carry a workflow-authored package identity without asserting validity."""

    registry_id: str | None
    auxiliary_id: str | None
    version: str | None


@dataclass(frozen=True, slots=True)
class WorkflowNodeInventoryItem:
    """Describe one executable node using only serialized workflow evidence."""

    node_id: str
    class_type: str
    title: str
    cube_alias: str | None
    nodepack_hint: PersistedNodepackHint | None


def workflow_node_inventory(
    workflow: Mapping[str, object],
) -> tuple[WorkflowNodeInventoryItem, ...]:
    """Return deterministic executable-node facts from root and embedded graphs."""

    items: list[WorkflowNodeInventoryItem] = []
    seen: set[tuple[str | None, str, str]] = set()
    _append_ui_graph_items(
        workflow,
        scope="root",
        cube_alias=None,
        items=items,
        seen=seen,
    )
    for document_index, document in enumerate(_embedded_cube_documents(workflow)):
        alias = _cube_alias(document)
        implementation = document.get("implementation")
        if not isinstance(implementation, Mapping):
            continue
        hints_by_class = _unambiguous_hints_by_class(implementation)
        local_subgraph_ids = _local_subgraph_ids(implementation)
        raw_nodes = implementation.get("nodes")
        if isinstance(raw_nodes, Mapping):
            for node_name, raw_node in raw_nodes.items():
                if not isinstance(node_name, str) or not isinstance(raw_node, Mapping):
                    continue
                class_type = _text(raw_node.get("class_type"))
                if class_type in local_subgraph_ids or not _is_executable_class(
                    class_type
                ):
                    continue
                hint = _nodepack_hint(raw_node) or hints_by_class.get(class_type)
                _append_item(
                    WorkflowNodeInventoryItem(
                        node_id=_text(raw_node.get("original_id")) or node_name,
                        class_type=class_type,
                        title=(
                            _text(raw_node.get("label"))
                            or _text(raw_node.get("title"))
                            or node_name
                        ),
                        cube_alias=alias,
                        nodepack_hint=hint,
                    ),
                    items=items,
                    seen=seen,
                )
        _append_ui_graph_items(
            implementation,
            scope=f"cube:{document_index}",
            cube_alias=alias,
            items=items,
            seen=seen,
        )
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.cube_alias or "",
                item.node_id,
                item.class_type,
                item.title,
            ),
        )
    )


def _append_ui_graph_items(
    graph: Mapping[str, object],
    *,
    scope: str,
    cube_alias: str | None,
    items: list[WorkflowNodeInventoryItem],
    seen: set[tuple[str | None, str, str]],
) -> None:
    """Append root and local-subgraph UI nodes without treating wrappers as nodes."""

    definitions = graph.get("definitions")
    subgraphs = (
        _mapping_sequence(definitions.get("subgraphs"))
        if isinstance(definitions, Mapping)
        else ()
    )
    direct_subgraphs = _mapping_sequence(graph.get("subgraphs"))
    all_subgraphs = (*subgraphs, *direct_subgraphs)
    subgraph_ids = {
        subgraph_id
        for subgraph in all_subgraphs
        if (subgraph_id := _text(subgraph.get("id")))
    }
    scopes = ((scope, graph),) + tuple(
        (f"{scope}/subgraph:{index}", subgraph)
        for index, subgraph in enumerate(all_subgraphs)
    )
    for graph_scope, scoped_graph in scopes:
        for index, node in enumerate(_mapping_sequence(scoped_graph.get("nodes"))):
            class_type = _text(node.get("type"))
            if class_type in subgraph_ids or not _is_executable_class(class_type):
                continue
            raw_node_id = node.get("id")
            node_id = (
                str(raw_node_id)
                if isinstance(raw_node_id, str | int)
                and not isinstance(raw_node_id, bool)
                else f"{graph_scope}/node:{index}"
            )
            _append_item(
                WorkflowNodeInventoryItem(
                    node_id=f"{graph_scope}:{node_id}",
                    class_type=class_type,
                    title=_text(node.get("title")) or class_type,
                    cube_alias=cube_alias,
                    nodepack_hint=_nodepack_hint(node),
                ),
                items=items,
                seen=seen,
            )


def _local_subgraph_ids(graph: Mapping[str, object]) -> frozenset[str]:
    """Return class ids implemented by subgraphs embedded in this graph."""

    definitions = graph.get("definitions")
    nested = (
        _mapping_sequence(definitions.get("subgraphs"))
        if isinstance(definitions, Mapping)
        else ()
    )
    direct = _mapping_sequence(graph.get("subgraphs"))
    return frozenset(
        subgraph_id
        for subgraph in (*nested, *direct)
        if (subgraph_id := _text(subgraph.get("id")))
    )


def _append_item(
    item: WorkflowNodeInventoryItem,
    *,
    items: list[WorkflowNodeInventoryItem],
    seen: set[tuple[str | None, str, str]],
) -> None:
    """Append one item unless the same persisted node was already observed."""

    identity = (item.cube_alias, item.node_id, item.class_type)
    if identity in seen:
        return
    seen.add(identity)
    items.append(item)


def _unambiguous_hints_by_class(
    payload: Mapping[str, object],
) -> dict[str, PersistedNodepackHint]:
    """Return class hints only where serialized evidence agrees."""

    hints: dict[str, set[PersistedNodepackHint]] = {}
    for value in _walk_mappings(payload):
        class_type = _text(value.get("type")) or _text(value.get("class_type"))
        hint = _nodepack_hint(value)
        if class_type and hint is not None:
            hints.setdefault(class_type, set()).add(hint)
    return {
        class_type: next(iter(class_hints))
        for class_type, class_hints in hints.items()
        if len(class_hints) == 1
    }


def _embedded_cube_documents(
    workflow: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    """Return each distinct embedded SugarCubes document from a workflow."""

    documents: list[Mapping[str, object]] = []
    observed: set[int] = set()
    for mapping in _walk_mappings(workflow):
        document = mapping.get("sugarcubes_document")
        if not isinstance(document, Mapping) or id(document) in observed:
            continue
        observed.add(id(document))
        documents.append(document)
    return tuple(documents)


def _walk_mappings(value: object) -> Iterable[Mapping[str, object]]:
    """Yield nested mappings without interpreting their schema."""

    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for child in value:
            yield from _walk_mappings(child)


def _cube_alias(document: Mapping[str, object]) -> str | None:
    """Return the embedded Cube's saved alias when present."""

    metadata = document.get("metadata")
    if isinstance(metadata, Mapping):
        alias = _text(metadata.get("default_alias"))
        if alias:
            return alias
    return _text(document.get("cube_id"))


def _nodepack_hint(node: Mapping[str, object]) -> PersistedNodepackHint | None:
    """Read standard Comfy node-package properties without validating them."""

    properties = node.get("properties")
    source = properties if isinstance(properties, Mapping) else node
    registry_id = _text(source.get("cnr_id"))
    auxiliary_id = _text(source.get("aux_id"))
    version = _text(source.get("ver")) or _text(source.get("version"))
    if registry_id is None and auxiliary_id is None:
        return None
    return PersistedNodepackHint(
        registry_id=registry_id,
        auxiliary_id=auxiliary_id,
        version=version,
    )


def _mapping_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    """Return mapping members of one serialized sequence."""

    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _is_executable_class(class_type: str | None) -> TypeGuard[str]:
    """Return whether a persisted class represents backend execution."""

    return bool(
        class_type
        and known_execution_role(class_type) is WorkflowNodeExecutionRole.EXECUTABLE
    )


def _text(value: object) -> str | None:
    """Return one stripped non-empty string."""

    return value.strip() if isinstance(value, str) and value.strip() else None


__all__ = [
    "PersistedNodepackHint",
    "WorkflowNodeInventoryItem",
    "workflow_node_inventory",
]
