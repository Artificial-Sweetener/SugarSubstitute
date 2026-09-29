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

"""Materialize production editor workflows from captured rig fixtures."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.domain.common import GlobalOverrideMap
from substitute.domain.cubes import (
    SubgraphWrapperDefinitionIndex,
    materialize_cube_runtime_graph,
    validate_canonical_cube_document,
)
from substitute.domain.workflow.models import CubeState, WorkflowState

from .fixtures import stable_json_hash, write_json


def workflow_from_fixture(
    fixture: Mapping[str, Any],
) -> tuple[WorkflowState, dict[str, Any]]:
    """Materialize captured canonical cube documents into runtime workflow state."""

    workflow = WorkflowState()
    raw_global_overrides = fixture.get("global_overrides", {})
    workflow.global_overrides = (
        copy.deepcopy(cast(GlobalOverrideMap, raw_global_overrides))
        if isinstance(raw_global_overrides, dict)
        else {}
    )
    definitions: dict[str, Any] = {}
    root_definitions = fixture.get("node_definitions")
    live_definitions: dict[str, Any] = (
        dict(root_definitions) if isinstance(root_definitions, Mapping) else {}
    )
    cubes = fixture.get("cubes", [])
    if not isinstance(cubes, list):
        return workflow, definitions
    for cube_payload in cubes:
        if not isinstance(cube_payload, Mapping):
            continue
        cube_buffer = cube_payload.get("cube_buffer")
        if not isinstance(cube_buffer, Mapping):
            continue
        document = validate_canonical_cube_document(cube_buffer)
        runtime_graph = materialize_cube_runtime_graph(document)
        graph_definitions = runtime_graph.get("definitions")
        if isinstance(graph_definitions, dict):
            graph_definitions.update(live_definitions)
            graph_definitions.update(_wrapper_definitions(runtime_graph))
        runtime_definitions = runtime_graph.get("definitions")
        if isinstance(runtime_definitions, Mapping):
            definitions.update(runtime_definitions)
        alias = str(cube_payload.get("alias", document.display_name))
        ui_payload: dict[str, object] = {
            "canonical_cube": document.to_metadata_payload(),
            "content_hash": str(cube_payload.get("content_hash", "")),
            "node_behavior_runtime": NodeBehaviorRuntimeState(),
        }
        cube_state = CubeState(
            cube_id=document.cube_id,
            version=document.version,
            alias=alias,
            original_cube=copy.deepcopy(runtime_graph),
            buffer=copy.deepcopy(runtime_graph),
            display_name=str(cube_payload.get("display_name", document.display_name)),
            ui=ui_payload,
        )
        workflow.cubes[alias] = cube_state
        workflow.stack_order.append(alias)
    if isinstance(root_definitions, Mapping):
        definitions.update(root_definitions)
    return workflow, definitions


def write_production_target(
    *,
    fixture_path: Path,
    fixture: Mapping[str, Any],
    signature: Mapping[str, Any],
) -> None:
    """Persist the observed production settled signature into one fixture."""

    updated = dict(fixture)
    signature_payload = copy.deepcopy(dict(signature))
    updated["production_settled_signature"] = signature_payload
    updated["production_settled_signature_hash"] = stable_json_hash(signature_payload)
    updated["fixture_hash"] = stable_json_hash(updated)
    write_json(fixture_path, updated)


def _wrapper_definitions(
    runtime_graph: Mapping[str, object],
) -> dict[str, Any]:
    """Return renderable wrapper definitions for standalone fixture projection."""

    wrapper_index = SubgraphWrapperDefinitionIndex.from_runtime_graph(runtime_graph)
    definitions: dict[str, Any] = {}
    nodes = runtime_graph.get("nodes")
    if not isinstance(nodes, Mapping):
        return definitions
    for node_payload in nodes.values():
        if not isinstance(node_payload, Mapping):
            continue
        class_type = node_payload.get("class_type")
        if not isinstance(class_type, str):
            continue
        definition = wrapper_index.definition_for_class_type(class_type)
        if definition is not None:
            definitions[class_type] = _definition_with_list_fallbacks(definition)
    return definitions


def _definition_with_list_fallbacks(
    definition: Mapping[str, object],
) -> dict[str, object]:
    """Add minimal LIST options when fixture metadata has only authored defaults."""

    patched = copy.deepcopy(dict(definition))
    input_section = patched.get("input")
    if not isinstance(input_section, dict):
        return patched
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, dict):
            continue
        for field_key, field_spec in list(section.items()):
            section[field_key] = _field_spec_with_list_fallback(field_spec)
    return patched


def _field_spec_with_list_fallback(field_spec: object) -> object:
    """Return a field spec with a renderable single fallback option when needed."""

    if not isinstance(field_spec, list) or not field_spec:
        return field_spec
    first = field_spec[0]
    if isinstance(first, list) and first:
        return field_spec
    if first != "LIST":
        return field_spec
    metadata = (
        field_spec[1] if len(field_spec) > 1 and isinstance(field_spec[1], dict) else {}
    )
    options = metadata.get("options") if isinstance(metadata, dict) else None
    if isinstance(options, list | tuple) and options:
        return field_spec
    fallback = metadata.get("default") if isinstance(metadata, dict) else None
    if fallback is None or isinstance(fallback, list | dict):
        fallback = "Fixture Placeholder"
    patched = list(field_spec)
    patched[0] = [str(fallback)]
    return patched
