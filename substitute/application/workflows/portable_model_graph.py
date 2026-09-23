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

"""Access portable model endpoints inside canonical Comfy Cube graphs."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import cast

from substitute.application.model_metadata import model_kind_for_field
from substitute.application.workflows.composed_value_annotation_service import (
    COMPOSITION_METADATA_KEY,
)
from substitute.domain.common import JsonValue
from substitute.domain.recipes import SugarBuffer, SugarBufferMap


@dataclass(frozen=True, slots=True)
class PortableCubeDocumentBinding:
    """Locate one embedded Cube document through its stable instance identity."""

    instance_id: str
    alias: str
    document: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PortableModelField:
    """Describe one literal model picker field in an embedded Cube document."""

    node_symbol: str
    input_name: str
    kind_candidates: tuple[str, ...]
    value: str


_NON_MODEL_CONFIGURATION_FIELDS = frozenset(
    {
        "diffusion_mode",
        "diffusion_weight_dtype",
        "text_encoder_device",
    }
)
_AMBIGUOUS_MODEL_KIND_CANDIDATES = {
    "model_name": ("upscale_models", "ultralytics"),
}


def cube_document_bindings(
    graph: Mapping[str, object],
) -> tuple[PortableCubeDocumentBinding, ...]:
    """Return embedded Cube documents indexed through canonical graph nodes."""

    definitions_value = graph.get("definitions")
    subgraphs = (
        definitions_value.get("subgraphs")
        if isinstance(definitions_value, Mapping)
        else None
    )
    definitions = {
        str(definition.get("id")): definition
        for definition in _mapping_items(subgraphs)
    }
    result: list[PortableCubeDocumentBinding] = []
    for node in _mapping_items(graph.get("nodes")):
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
            and instance_id.strip()
            and isinstance(alias, str)
            and alias.strip()
            and isinstance(document, Mapping)
        ):
            result.append(
                PortableCubeDocumentBinding(
                    instance_id=instance_id.strip(),
                    alias=alias.strip(),
                    document=document,
                )
            )
    return tuple(result)


def model_fields(
    document: Mapping[str, object],
) -> tuple[PortableModelField, ...]:
    """Return model picker fields from one embedded Cube implementation."""

    fields: list[PortableModelField] = []
    for node_symbol, node in _document_nodes(document).items():
        class_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for input_name, value in inputs.items():
            if not isinstance(input_name, str) or not isinstance(value, str):
                continue
            if input_name in _NON_MODEL_CONFIGURATION_FIELDS:
                continue
            kind = model_kind_for_field(
                class_type=class_type if isinstance(class_type, str) else "",
                input_key=input_name,
            )
            kind_candidates = (
                (kind,)
                if kind is not None
                else _AMBIGUOUS_MODEL_KIND_CANDIDATES.get(input_name, ())
            )
            if kind_candidates:
                fields.append(
                    PortableModelField(
                        node_symbol=node_symbol,
                        input_name=input_name,
                        kind_candidates=kind_candidates,
                        value=value,
                    )
                )
    return tuple(fields)


def document_field_value(
    document: Mapping[str, object],
    *,
    node_symbol: str,
    input_name: str,
) -> object:
    """Return the current literal field value for one stable endpoint."""

    node = _document_nodes(document).get(node_symbol)
    inputs = node.get("inputs") if isinstance(node, Mapping) else None
    return inputs.get(input_name) if isinstance(inputs, Mapping) else None


def empty_resolver_buffer(document: Mapping[str, object]) -> SugarBuffer:
    """Build the minimal resolver buffer for one embedded Cube document."""

    cube_id = document.get("cube_id")
    return OrderedDict(
        {
            "cube_id": cast(JsonValue, cube_id if isinstance(cube_id, str) else ""),
            "nodes": {},
        }
    )


def copy_model_field(
    buffer: SugarBuffer,
    *,
    document: Mapping[str, object],
    node_symbol: str,
    input_name: str,
) -> None:
    """Copy one model field and its class identity into a resolver buffer."""

    source = _document_nodes(document).get(node_symbol)
    if not isinstance(source, Mapping):
        return
    source_inputs = source.get("inputs")
    if not isinstance(source_inputs, Mapping) or input_name not in source_inputs:
        return
    nodes = cast(dict[str, object], buffer["nodes"])
    node = cast(
        dict[str, object],
        nodes.setdefault(
            node_symbol,
            {
                "class_type": source.get("class_type", ""),
                "inputs": {},
            },
        ),
    )
    inputs = cast(dict[str, object], node["inputs"])
    inputs[input_name] = deepcopy(source_inputs[input_name])


def resolver_buffer_field_value(
    buffers: SugarBufferMap,
    *,
    alias: str,
    node_symbol: str,
    input_name: str,
) -> str | None:
    """Return one resolved string value from a resolver buffer."""

    buffer = buffers.get(alias)
    nodes = buffer.get("nodes") if isinstance(buffer, Mapping) else None
    node = nodes.get(node_symbol) if isinstance(nodes, Mapping) else None
    inputs = node.get("inputs") if isinstance(node, Mapping) else None
    value = inputs.get(input_name) if isinstance(inputs, Mapping) else None
    return value if isinstance(value, str) else None


def set_document_field_value(
    document: Mapping[str, object],
    *,
    node_symbol: str,
    input_name: str,
    value: str,
) -> None:
    """Update one mutable embedded Cube input after Backend resolution."""

    node = _document_nodes(document).get(node_symbol)
    inputs = node.get("inputs") if isinstance(node, Mapping) else None
    if isinstance(inputs, dict) and input_name in inputs:
        inputs[input_name] = value


def set_composed_override_value(
    graph: Mapping[str, object],
    *,
    instance_id: str,
    node_symbol: str,
    input_name: str,
    value: str,
) -> None:
    """Keep a matching persisted global override aligned with a resolved field."""

    extra = graph.get("extra")
    composition = (
        extra.get(COMPOSITION_METADATA_KEY) if isinstance(extra, Mapping) else None
    )
    relations = (
        composition.get("value_relations") if isinstance(composition, Mapping) else None
    )
    for relation in _mapping_items(relations):
        if relation.get("kind") != "global_override":
            continue
        if not _relation_targets_field(
            relation,
            instance_id=instance_id,
            node_symbol=node_symbol,
            input_name=input_name,
        ):
            continue
        if isinstance(relation, dict):
            relation["value"] = value


def unique_resolver_alias(alias: str, instance_id: str, used: set[str]) -> str:
    """Return a deterministic resolver key without losing a readable alias."""

    candidate = alias
    if candidate in used:
        candidate = f"{alias} [{instance_id[:8]}]"
    used.add(candidate)
    return candidate


def _relation_targets_field(
    relation: Mapping[str, object],
    *,
    instance_id: str,
    node_symbol: str,
    input_name: str,
) -> bool:
    """Return whether one value relation includes a stable model endpoint."""

    return any(
        target.get("instance_id") == instance_id
        and target.get("node_symbol") == node_symbol
        and target.get("input_name") == input_name
        for target in _mapping_items(relation.get("targets"))
    )


def _document_nodes(document: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    """Return implementation nodes indexed by stable Cube symbol."""

    implementation = document.get("implementation")
    nodes = implementation.get("nodes") if isinstance(implementation, Mapping) else None
    if not isinstance(nodes, Mapping):
        return {}
    return {
        str(symbol): node
        for symbol, node in nodes.items()
        if isinstance(symbol, str) and isinstance(node, Mapping)
    }


def _mapping_items(value: object) -> tuple[Mapping[str, object], ...]:
    """Return mapping members from an untrusted JSON array."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


__all__ = [
    "PortableCubeDocumentBinding",
    "PortableModelField",
    "copy_model_field",
    "cube_document_bindings",
    "document_field_value",
    "empty_resolver_buffer",
    "model_fields",
    "resolver_buffer_field_value",
    "set_composed_override_value",
    "set_document_field_value",
    "unique_resolver_alias",
]
