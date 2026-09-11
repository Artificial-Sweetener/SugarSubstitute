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

"""Project resolved legacy recipe model identity into its canonical graph."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace

from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis
from substitute.domain.common import JsonObject
from substitute.domain.recipes import ParsedSugarScript

_COMPOSITION_KEY = "sugarcubes_composition"
_MODEL_NAMESPACE = "substitute.model_asset"


def project_resolved_recipe_model_fields(
    analysis: CanonicalCubeGraphAnalysis | None,
    parsed_script: ParsedSugarScript,
) -> CanonicalCubeGraphAnalysis | None:
    """Return a graph carrying resolved filenames and stable model hash annotations."""

    if analysis is None or not parsed_script.model_hashes_by_field:
        return analysis
    graph = deepcopy(analysis.workflow)
    definitions = _definitions_by_id(graph)
    instances = {instance.alias: instance for instance in analysis.instances}
    annotations: list[dict[str, object]] = []
    for (alias, node_symbol, input_name), sha256 in sorted(
        parsed_script.model_hashes_by_field.items()
    ):
        instance = instances.get(alias)
        buffer = parsed_script.buffers.get(alias)
        if instance is None or not isinstance(buffer, Mapping):
            continue
        resolved_value = _buffer_input(buffer, node_symbol, input_name)
        definition = definitions.get(instance.definition_id)
        if resolved_value is _MISSING or definition is None:
            continue
        if not _write_document_input(
            definition,
            node_symbol=node_symbol,
            input_name=input_name,
            value=resolved_value,
        ):
            continue
        annotations.append(
            {
                "annotation_id": (
                    f"{_MODEL_NAMESPACE}:{instance.instance_id}:"
                    f"{node_symbol}:{input_name}"
                ),
                "namespace": _MODEL_NAMESPACE,
                "endpoint": {
                    "instance_id": instance.instance_id,
                    "node_symbol": node_symbol,
                    "input_name": input_name,
                },
                "payload": {"sha256": sha256.upper()},
            }
        )
    if not annotations:
        return analysis
    _replace_model_annotations(graph, annotations)
    return replace(analysis, workflow=graph)


class _Missing:
    """Identify a field absent from the resolved parsed recipe."""


_MISSING = _Missing()


def _definitions_by_id(graph: Mapping[str, object]) -> dict[str, dict[str, object]]:
    """Index mutable embedded definitions by native definition id."""

    envelope = graph.get("definitions")
    subgraphs = envelope.get("subgraphs") if isinstance(envelope, Mapping) else None
    if not isinstance(subgraphs, Sequence) or isinstance(subgraphs, (str, bytes)):
        return {}
    return {
        str(item["id"]): item
        for item in subgraphs
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _buffer_input(
    buffer: Mapping[str, object],
    node_symbol: str,
    input_name: str,
) -> object:
    """Read one resolved field from parsed legacy recipe buffers."""

    nodes = buffer.get("nodes")
    node = nodes.get(node_symbol) if isinstance(nodes, Mapping) else None
    inputs = node.get("inputs") if isinstance(node, Mapping) else None
    return inputs.get(input_name, _MISSING) if isinstance(inputs, Mapping) else _MISSING


def _write_document_input(
    definition: dict[str, object],
    *,
    node_symbol: str,
    input_name: str,
    value: object,
) -> bool:
    """Write one existing stable field without creating unknown Cube structure."""

    extra = definition.get("extra")
    document = extra.get("sugarcubes_document") if isinstance(extra, Mapping) else None
    implementation = (
        document.get("implementation") if isinstance(document, Mapping) else None
    )
    nodes = implementation.get("nodes") if isinstance(implementation, Mapping) else None
    node = nodes.get(node_symbol) if isinstance(nodes, Mapping) else None
    inputs = node.get("inputs") if isinstance(node, Mapping) else None
    if not isinstance(inputs, dict) or input_name not in inputs:
        return False
    inputs[input_name] = deepcopy(value)
    return True


def _replace_model_annotations(
    graph: JsonObject,
    annotations: Sequence[Mapping[str, object]],
) -> None:
    """Replace only Substitute model annotations while preserving future metadata."""

    extra = graph.setdefault("extra", {})
    if not isinstance(extra, dict):
        return
    existing = extra.get(_COMPOSITION_KEY)
    composition = deepcopy(dict(existing)) if isinstance(existing, Mapping) else {}
    raw_annotations = composition.get("field_annotations")
    retained = [
        deepcopy(dict(item))
        for item in _mapping_items(raw_annotations)
        if item.get("namespace") != _MODEL_NAMESPACE
    ]
    composition["schema_version"] = 1
    composition["field_annotations"] = [
        *retained,
        *(deepcopy(dict(item)) for item in annotations),
    ]
    extra[_COMPOSITION_KEY] = composition


def _mapping_items(value: object) -> tuple[Mapping[str, object], ...]:
    """Return mapping records from one JSON-like sequence."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


__all__ = ["project_resolved_recipe_model_fields"]
