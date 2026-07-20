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

"""Resolve official Comfy templates and independently inventory source nodes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SourceNodeDisposition(StrEnum):
    """Classify how one serialized Comfy node enters editor projection."""

    PROJECTED = "projected"
    ANNOTATION = "annotation"
    ROUTING = "routing"
    SUBGRAPH_INSTANCE = "subgraph_instance"


@dataclass(frozen=True, slots=True)
class BundledWorkflowCatalogEntry:
    """Describe one workflow named by the official template catalog."""

    name: str
    title: str
    category: str
    path: Path


@dataclass(frozen=True, slots=True)
class BundledWorkflowCatalog:
    """Describe one validated official workflow-template catalog."""

    template_root: Path
    entries: tuple[BundledWorkflowCatalogEntry, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class SourceWorkflowNode:
    """Describe one independently traversed root or instantiated subgraph node."""

    node_id: str
    class_type: str
    title: str
    disposition: SourceNodeDisposition
    reason: str


@dataclass(frozen=True, slots=True)
class SourceWorkflowInventory:
    """Account for every serialized node reached from one workflow root."""

    nodes: tuple[SourceWorkflowNode, ...]

    @property
    def projected_nodes(self) -> tuple[SourceWorkflowNode, ...]:
        """Return nodes expected to enter the editable intermediate graph."""

        return tuple(
            node
            for node in self.nodes
            if node.disposition is SourceNodeDisposition.PROJECTED
        )


def load_bundled_workflow_catalog(template_root: Path) -> BundledWorkflowCatalog:
    """Load and validate every workflow named by the official catalog index."""

    resolved_root = template_root.resolve()
    index = _json_mapping_or_sequence(resolved_root / "index.json")
    if not isinstance(index, Sequence) or isinstance(index, str | bytes):
        raise ValueError("Comfy workflow template index must be an array.")

    entries: list[BundledWorkflowCatalogEntry] = []
    seen_names: set[str] = set()
    for section in index:
        if not isinstance(section, Mapping):
            raise ValueError("Comfy workflow template sections must be objects.")
        category = _required_text(section, "title", "template section")
        templates = section.get("templates")
        if not isinstance(templates, Sequence) or isinstance(templates, str | bytes):
            raise ValueError(f"Template section {category!r} has no template array.")
        for item in templates:
            if not isinstance(item, Mapping):
                raise ValueError(
                    f"Template section {category!r} contains a non-object."
                )
            name = _required_text(item, "name", f"template in {category!r}")
            title = _required_text(item, "title", f"template {name!r}")
            if name in seen_names:
                raise ValueError(f"Duplicate bundled workflow template name: {name}")
            path = resolved_root / f"{name}.json"
            if not path.is_file():
                raise ValueError(f"Bundled workflow template is missing: {path}")
            seen_names.add(name)
            entries.append(
                BundledWorkflowCatalogEntry(
                    name=name,
                    title=title,
                    category=category,
                    path=path,
                )
            )

    fingerprint_payload = "\n".join(
        f"{entry.category}\0{entry.name}\0{entry.title}" for entry in entries
    ).encode("utf-8")
    return BundledWorkflowCatalog(
        template_root=resolved_root,
        entries=tuple(entries),
        fingerprint=hashlib.sha256(fingerprint_payload).hexdigest(),
    )


def load_workflow_document(path: Path) -> dict[str, object]:
    """Load one workflow JSON document as a detached mutable mapping."""

    payload = _json_mapping_or_sequence(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Comfy workflow must be a JSON object: {path}")
    return {str(key): value for key, value in payload.items()}


def inventory_source_workflow(
    workflow: Mapping[str, object],
) -> SourceWorkflowInventory:
    """Independently expand subgraph instances and classify every source node."""

    definitions = _subgraph_definitions(workflow.get("definitions"))
    nodes: list[SourceWorkflowNode] = []
    _inventory_scope(
        raw_nodes=workflow.get("nodes"),
        definitions=definitions,
        namespace="",
        definition_stack=(),
        inventory=nodes,
    )
    return SourceWorkflowInventory(nodes=tuple(nodes))


def _inventory_scope(
    *,
    raw_nodes: object,
    definitions: Mapping[str, Mapping[str, object]],
    namespace: str,
    definition_stack: tuple[str, ...],
    inventory: list[SourceWorkflowNode],
) -> None:
    """Append independently classified nodes from one root or subgraph scope."""

    for node in _node_records(raw_nodes):
        source_id = str(node["id"])
        qualified_id = f"{namespace}:{source_id}" if namespace else source_id
        class_type = str(node.get("type", "")).strip()
        title = _node_title(node, class_type or source_id)
        definition = definitions.get(class_type)
        if definition is not None:
            inventory.append(
                SourceWorkflowNode(
                    node_id=qualified_id,
                    class_type=class_type,
                    title=title,
                    disposition=SourceNodeDisposition.SUBGRAPH_INSTANCE,
                    reason="expanded local subgraph instance",
                )
            )
            if class_type in definition_stack:
                cycle = " -> ".join((*definition_stack, class_type))
                raise ValueError(f"Recursive Comfy subgraph definitions: {cycle}")
            _inventory_scope(
                raw_nodes=definition.get("nodes"),
                definitions=definitions,
                namespace=qualified_id,
                definition_stack=(*definition_stack, class_type),
                inventory=inventory,
            )
            continue
        if class_type in {"MarkdownNote", "Note"}:
            disposition = SourceNodeDisposition.ANNOTATION
            reason = "frontend annotation"
        elif class_type == "Reroute":
            disposition = SourceNodeDisposition.ROUTING
            reason = "frontend routing node"
        else:
            disposition = SourceNodeDisposition.PROJECTED
            reason = "editable graph node"
        inventory.append(
            SourceWorkflowNode(
                node_id=qualified_id,
                class_type=class_type,
                title=title,
                disposition=disposition,
                reason=reason,
            )
        )


def _subgraph_definitions(payload: object) -> dict[str, Mapping[str, object]]:
    """Return local subgraph definitions indexed by their serialized UUID."""

    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("Comfy workflow definitions must be an object.")
    raw_subgraphs = payload.get("subgraphs", ())
    if not isinstance(raw_subgraphs, Sequence) or isinstance(
        raw_subgraphs,
        str | bytes,
    ):
        raise ValueError("Comfy workflow subgraphs must be an array.")
    definitions: dict[str, Mapping[str, object]] = {}
    for definition in raw_subgraphs:
        if not isinstance(definition, Mapping):
            raise ValueError("Comfy subgraph definitions must be objects.")
        definition_id = definition.get("id")
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise ValueError("Comfy subgraph definition has no string id.")
        if definition_id in definitions:
            raise ValueError(f"Duplicate Comfy subgraph definition: {definition_id}")
        definitions[definition_id] = definition
    return definitions


def _node_records(payload: object) -> tuple[Mapping[str, object], ...]:
    """Return validated node mappings from one LiteGraph scope."""

    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        raise ValueError("Comfy workflow nodes must be an array.")
    records: list[Mapping[str, object]] = []
    for node in payload:
        if not isinstance(node, Mapping) or "id" not in node:
            raise ValueError("Every Comfy workflow node must be an object with an id.")
        records.append(node)
    return tuple(records)


def _node_title(node: Mapping[str, object], fallback: str) -> str:
    """Return one authored node title with property and class fallbacks."""

    title = node.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    properties = node.get("properties")
    if isinstance(properties, Mapping):
        search_name = properties.get("Node name for S&R")
        if isinstance(search_name, str) and search_name.strip():
            return search_name.strip()
    return fallback


def _required_text(payload: Mapping[str, object], key: str, owner: str) -> str:
    """Return one required nonempty catalog string."""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner} has no nonempty {key!r} value.")
    return value.strip()


def _json_mapping_or_sequence(path: Path) -> object:
    """Decode one UTF-8 JSON resource with path-aware errors."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not decode JSON resource {path}: {error}") from error


__all__ = [
    "BundledWorkflowCatalog",
    "BundledWorkflowCatalogEntry",
    "SourceNodeDisposition",
    "SourceWorkflowInventory",
    "SourceWorkflowNode",
    "inventory_source_workflow",
    "load_bundled_workflow_catalog",
    "load_workflow_document",
]
