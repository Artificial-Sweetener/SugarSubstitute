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

"""Project embedded canonical Cube nodes for generation-time asset staging."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.domain.common import JsonObject


@dataclass(frozen=True)
class CanonicalCubeAssetProjection:
    """Expose mutable asset-bearing node proxies over embedded Cube documents."""

    prompt: dict[str, object]
    class_type_targets: tuple[tuple[dict[str, object], dict[str, object]], ...]

    def commit_class_types(self) -> None:
        """Commit staged classes and values through canonical Cube identities."""

        for proxy, target in self.class_type_targets:
            class_type = proxy.get("class_type")
            if isinstance(class_type, str):
                target["class_type"] = class_type


def project_canonical_cube_asset_nodes(
    workflow: JsonObject,
) -> CanonicalCubeAssetProjection | None:
    """Return staging proxies when a workflow uses canonical Cube definitions."""

    instances = workflow.get("nodes")
    definitions_container = workflow.get("definitions")
    if not isinstance(instances, list) or not isinstance(
        definitions_container, Mapping
    ):
        return None
    definitions = definitions_container.get("subgraphs")
    if not isinstance(definitions, list):
        return None
    documents = _documents_by_definition(definitions)
    prompt: dict[str, object] = {}
    class_type_targets: list[tuple[dict[str, object], dict[str, object]]] = []
    for instance in instances:
        if not isinstance(instance, Mapping):
            continue
        definition_id = instance.get("type")
        alias = _instance_alias(instance)
        document = (
            documents.get(definition_id) if isinstance(definition_id, str) else None
        )
        nodes = _document_nodes(document)
        if alias is None or nodes is None:
            continue
        for node_name, raw_node in nodes.items():
            if not isinstance(raw_node, dict):
                continue
            inputs = raw_node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            proxy: dict[str, object] = {
                "class_type": raw_node.get("class_type"),
                "inputs": inputs,
                "_meta": {"title": f"{alias}.{node_name}"},
            }
            prompt[f"{alias}:{node_name}"] = proxy
            class_type_targets.append((proxy, raw_node))
    return CanonicalCubeAssetProjection(
        prompt=prompt,
        class_type_targets=tuple(class_type_targets),
    )


def _documents_by_definition(
    definitions: list[object],
) -> dict[str, JsonObject]:
    """Index embedded canonical documents by subgraph definition id."""

    result: dict[str, JsonObject] = {}
    for definition in definitions:
        if not isinstance(definition, Mapping):
            continue
        definition_id = definition.get("id")
        extra = definition.get("extra")
        document = (
            extra.get("sugarcubes_document") if isinstance(extra, Mapping) else None
        )
        if isinstance(definition_id, str) and isinstance(document, dict):
            result[definition_id] = document
    return result


def _instance_alias(instance: Mapping[str, object]) -> str | None:
    """Read the stable authored alias from one marked Cube instance."""

    properties = instance.get("properties")
    marker = (
        properties.get("sugarcubes_cube") if isinstance(properties, Mapping) else None
    )
    alias = marker.get("instance_alias") if isinstance(marker, Mapping) else None
    return alias if isinstance(alias, str) and alias else None


def _document_nodes(document: Mapping[str, object] | None) -> dict[str, object] | None:
    """Return the mutable implementation node map from one embedded document."""

    implementation = document.get("implementation") if document is not None else None
    nodes = implementation.get("nodes") if isinstance(implementation, Mapping) else None
    return nodes if isinstance(nodes, dict) else None


__all__ = ["CanonicalCubeAssetProjection", "project_canonical_cube_asset_nodes"]
