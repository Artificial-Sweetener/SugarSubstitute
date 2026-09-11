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

"""Project Substitute value relationships into canonical Comfy workflow metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy

from substitute.domain.common import GlobalOverrideScope, JsonObject

COMPOSITION_METADATA_KEY = "sugarcubes_composition"
_SUBSTITUTE_OWNER = "substitute"


class ComposedValueAnnotationService:
    """Author stable SugarCubes value relations without changing graph topology."""

    def annotate(
        self,
        graph: JsonObject,
        *,
        global_override_scopes: Mapping[str, GlobalOverrideScope] | None = None,
    ) -> None:
        """Replace Substitute-owned relations on one detached canonical graph."""

        indexed = _cube_documents_by_alias(graph)
        relations = [
            *_node_link_relations(indexed),
            *_global_override_relations(indexed, global_override_scopes or {}),
        ]
        existing_extra = graph.get("extra")
        existing = (
            existing_extra.get(COMPOSITION_METADATA_KEY)
            if isinstance(existing_extra, Mapping)
            else None
        )
        if not relations and not isinstance(existing, Mapping):
            return
        extra = graph.setdefault("extra", {})
        if not isinstance(extra, dict):
            return
        composition = deepcopy(dict(existing)) if isinstance(existing, Mapping) else {}
        existing_relations = composition.get("value_relations")
        retained = [
            deepcopy(dict(relation))
            for relation in _mapping_records(existing_relations)
            if relation.get("owner") != _SUBSTITUTE_OWNER
        ]
        composition["schema_version"] = 1
        composition["value_relations"] = [*retained, *relations]
        extra[COMPOSITION_METADATA_KEY] = composition


def _cube_documents_by_alias(
    graph: Mapping[str, object],
) -> dict[str, tuple[str, Mapping[str, object]]]:
    """Index embedded documents by their user-facing instance alias."""

    definitions_value = graph.get("definitions")
    subgraphs = (
        definitions_value.get("subgraphs")
        if isinstance(definitions_value, Mapping)
        else None
    )
    definitions = {str(value.get("id")): value for value in _mapping_records(subgraphs)}
    result: dict[str, tuple[str, Mapping[str, object]]] = {}
    for node in _mapping_records(graph.get("nodes")):
        properties = node.get("properties")
        cube = (
            properties.get("sugarcubes_cube")
            if isinstance(properties, Mapping)
            else None
        )
        instance_id = cube.get("instance_id") if isinstance(cube, Mapping) else None
        alias = cube.get("instance_alias") if isinstance(cube, Mapping) else None
        definition = definitions.get(str(node.get("type")))
        extra = definition.get("extra") if isinstance(definition, Mapping) else None
        document = (
            extra.get("sugarcubes_document") if isinstance(extra, Mapping) else None
        )
        if (
            isinstance(instance_id, str)
            and instance_id
            and isinstance(alias, str)
            and alias
            and isinstance(document, Mapping)
        ):
            result[alias] = instance_id, document
    return result


def _node_link_relations(
    indexed: Mapping[str, tuple[str, Mapping[str, object]]],
) -> list[dict[str, object]]:
    """Translate whole-node link metadata into stable per-field relations."""

    relations: list[dict[str, object]] = []
    for target_alias, (target_instance_id, target_document) in indexed.items():
        target_nodes = _document_nodes(target_document)
        for target_symbol, target_node in target_nodes.items():
            link = target_node.get("node_link")
            if not isinstance(link, Mapping):
                continue
            source_alias = link.get("from_cube")
            source_symbol = link.get("from_node")
            source_entry = (
                indexed.get(source_alias) if isinstance(source_alias, str) else None
            )
            if source_entry is None or not isinstance(source_symbol, str):
                continue
            source_instance_id, source_document = source_entry
            source_node = _document_nodes(source_document).get(source_symbol)
            if not isinstance(source_node, Mapping):
                continue
            source_inputs = _literal_inputs(
                source_node, _document_nodes(source_document)
            )
            target_inputs = _literal_inputs(target_node, target_nodes)
            for input_name in sorted(source_inputs.keys() & target_inputs.keys()):
                relations.append(
                    {
                        "relation_id": (
                            f"link:{target_instance_id}:{target_symbol}:{input_name}"
                        ),
                        "owner": _SUBSTITUTE_OWNER,
                        "kind": "field_link",
                        "source": _endpoint(
                            source_instance_id,
                            source_symbol,
                            input_name,
                        ),
                        "targets": [
                            _endpoint(target_instance_id, target_symbol, input_name)
                        ],
                    }
                )
    return relations


def _global_override_relations(
    indexed: Mapping[str, tuple[str, Mapping[str, object]]],
    scopes: Mapping[str, GlobalOverrideScope],
) -> list[dict[str, object]]:
    """Translate explicit override participation into literal relation groups."""

    relations: list[dict[str, object]] = []
    for override_key, scope in sorted(scopes.items()):
        targets = [
            _endpoint(indexed[alias][0], node_symbol, input_name)
            for alias, node_symbol, input_name in sorted(scope.participant_fields)
            if alias in indexed
        ]
        if not targets:
            continue
        relations.append(
            {
                "relation_id": f"override:{override_key}",
                "owner": _SUBSTITUTE_OWNER,
                "kind": "global_override",
                "override_key": scope.override_key,
                "value": deepcopy(scope.value),
                "targets": targets,
            }
        )
    return relations


def _endpoint(instance_id: str, node_symbol: str, input_name: str) -> dict[str, str]:
    """Build one stable SugarCubes field endpoint."""

    return {
        "instance_id": instance_id,
        "node_symbol": node_symbol,
        "input_name": input_name,
    }


def _document_nodes(document: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    """Return Cube implementation nodes indexed by stable symbol."""

    implementation = document.get("implementation")
    nodes = implementation.get("nodes") if isinstance(implementation, Mapping) else None
    if not isinstance(nodes, Mapping):
        return {}
    return {
        str(symbol): node
        for symbol, node in nodes.items()
        if isinstance(symbol, str) and isinstance(node, Mapping)
    }


def _literal_inputs(
    node: Mapping[str, object],
    nodes: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Return node-local values while excluding intra-Cube graph connections."""

    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return {}
    return {
        str(name): value
        for name, value in inputs.items()
        if isinstance(name, str) and not _is_graph_link(value, nodes)
    }


def _is_graph_link(
    value: object,
    nodes: Mapping[str, Mapping[str, object]],
) -> bool:
    """Return whether a value points to another node in the same Cube document."""

    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and len(value) == 2
        and isinstance(value[0], str)
        and value[0] in nodes
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    )


def _mapping_records(value: object) -> tuple[Mapping[str, object], ...]:
    """Return mapping entries from one JSON-like array."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


__all__ = ["COMPOSITION_METADATA_KEY", "ComposedValueAnnotationService"]
