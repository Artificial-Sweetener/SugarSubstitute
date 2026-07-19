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

"""Resolve Comfy output-source identities from executable workflow graphs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, Mapping, cast

from substitute.application.cubes import cube_alias_body
from substitute.shared.util.path_safety import safe_component


@dataclass(frozen=True)
class OutputSourceIdentity:
    """Describe canvas grouping identity for one executable output source node."""

    node_id: str
    source_key: str
    source_label: str
    cube_alias: str


@dataclass(frozen=True)
class OutputSourceGraph:
    """Map executable nodes to downstream cube output source nodes."""

    node_to_cube_output_node_id: Mapping[str, str]
    ambiguous_cube_output_node_ids_by_node: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class OutputSourceDiagnostic:
    """Describe one prompt-safe output-source resolution diagnostic."""

    level: Literal["debug", "warning"]
    message: str
    fields: Mapping[str, object]


@dataclass(frozen=True)
class OutputSourceResolution:
    """Return a resolved output source with any diagnostic selected en route."""

    source_identity: OutputSourceIdentity
    diagnostic: OutputSourceDiagnostic | None = None


def prompt_nodes(workflow_payload: dict[str, object]) -> dict[str, object]:
    """Return executable Comfy prompt nodes from raw or wrapped payloads."""

    prompt_payload = workflow_payload.get("prompt")
    if isinstance(prompt_payload, dict):
        return cast(dict[str, object], prompt_payload)
    return workflow_payload


def collect_cube_output_node_ids(workflow_payload: dict[str, object]) -> set[str]:
    """Collect SugarCubes cube output node ids from workflow payload."""

    cube_output_node_ids: set[str] = set()
    for node_id, node_data in prompt_nodes(workflow_payload).items():
        if not isinstance(node_data, dict):
            continue
        class_type = node_data.get("class_type")
        if isinstance(class_type, str) and class_type == "SugarCubes.CubeOutput":
            cube_output_node_ids.add(str(node_id))
    return cube_output_node_ids


def typed_prompt_nodes(
    workflow_payload: dict[str, object],
) -> dict[str, dict[str, Any]]:
    """Return executable prompt nodes with malformed node entries removed."""

    nodes: dict[str, dict[str, Any]] = {}
    for node_id, node_data in prompt_nodes(workflow_payload).items():
        if isinstance(node_data, dict):
            nodes[str(node_id)] = dict(node_data)
    return nodes


def build_output_source_graph(
    workflow_payload: dict[str, object],
    cube_output_node_ids: set[str],
) -> OutputSourceGraph:
    """Map prompt nodes to their one unambiguous downstream CubeOutput."""

    nodes = typed_prompt_nodes(workflow_payload)
    downstream_output_ids_by_node: dict[str, set[str]] = {}
    for cube_output_node_id in cube_output_node_ids:
        for upstream_node_id in upstream_node_ids(
            cube_output_node_id,
            nodes,
        ):
            downstream_output_ids_by_node.setdefault(upstream_node_id, set()).add(
                cube_output_node_id
            )

    for cube_output_node_id in cube_output_node_ids:
        downstream_output_ids_by_node[cube_output_node_id] = {cube_output_node_id}

    node_to_cube_output_node_id: dict[str, str] = {}
    ambiguous_cube_output_node_ids_by_node: dict[str, tuple[str, ...]] = {}
    for node_id, downstream_output_ids in downstream_output_ids_by_node.items():
        ordered_output_ids = tuple(sorted(downstream_output_ids))
        if len(ordered_output_ids) == 1:
            node_to_cube_output_node_id[node_id] = ordered_output_ids[0]
        else:
            ambiguous_cube_output_node_ids_by_node[node_id] = ordered_output_ids

    return OutputSourceGraph(
        node_to_cube_output_node_id=node_to_cube_output_node_id,
        ambiguous_cube_output_node_ids_by_node=ambiguous_cube_output_node_ids_by_node,
    )


def upstream_node_ids(
    root_node_id: str,
    nodes: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    """Return one CubeOutput and every executable node connected upstream."""

    visited: set[str] = set()
    pending = [root_node_id]
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        node_data = nodes.get(node_id)
        if node_data is None:
            continue
        inputs = node_data.get("inputs", {})
        for linked_node_id in linked_input_node_ids(inputs):
            if linked_node_id in nodes:
                pending.append(linked_node_id)
    return visited


def linked_input_node_ids(value: object) -> tuple[str, ...]:
    """Return Comfy node ids referenced by nested input link values."""

    linked_ids: list[str] = []
    if is_comfy_input_link(value):
        linked_ids.append(str(cast(list[object], value)[0]))
        return tuple(linked_ids)
    if isinstance(value, Mapping):
        linked_ids.extend(flatten_linked_input_node_ids(value.values()))
        return tuple(linked_ids)
    if isinstance(value, list | tuple):
        linked_ids.extend(flatten_linked_input_node_ids(value))
    return tuple(linked_ids)


def flatten_linked_input_node_ids(values: Iterable[object]) -> tuple[str, ...]:
    """Return linked input node ids from a sequence of nested input values."""

    linked_ids: list[str] = []
    for item in values:
        linked_ids.extend(linked_input_node_ids(item))
    return tuple(linked_ids)


def is_comfy_input_link(value: object) -> bool:
    """Return whether a value has Comfy's ``[node_id, output_index]`` shape."""

    if not isinstance(value, list | tuple) or len(value) != 2:
        return False
    source_node_id, output_index = value
    return isinstance(source_node_id, str | int) and isinstance(output_index, int)


def resolve_output_source_identity_for_node(
    node_id: str,
    *,
    workflow_id: str,
    prompt_id: str,
    workflow_payload: dict[str, object],
    output_source_graph: OutputSourceGraph,
    cube_output_node_ids: set[str],
    ambiguous_warning_keys: set[tuple[str, tuple[str, ...]]],
) -> OutputSourceResolution:
    """Return downstream cube output identity or node-local fallback identity."""

    ambiguous_cube_output_node_ids = (
        output_source_graph.ambiguous_cube_output_node_ids_by_node.get(node_id)
    )
    if ambiguous_cube_output_node_ids is not None:
        warning_key = (node_id, ambiguous_cube_output_node_ids)
        diagnostic_level: Literal["debug", "warning"] = "debug"
        if warning_key not in ambiguous_warning_keys:
            ambiguous_warning_keys.add(warning_key)
            diagnostic_level = "warning"
        return OutputSourceResolution(
            source_identity=output_source_identity_for_node(
                node_id,
                workflow_id=workflow_id,
                workflow_payload=workflow_payload,
            ),
            diagnostic=OutputSourceDiagnostic(
                level=diagnostic_level,
                message=(
                    "Using node-local output source after ambiguous cube-output mapping"
                ),
                fields={
                    "workflow_id": workflow_id,
                    "prompt_id": prompt_id,
                    "node_id": node_id,
                    "cube_output_node_ids": ambiguous_cube_output_node_ids,
                },
            ),
        )

    cube_output_node_id = output_source_graph.node_to_cube_output_node_id.get(node_id)
    if cube_output_node_id is None:
        return OutputSourceResolution(
            source_identity=output_source_identity_for_node(
                node_id,
                workflow_id=workflow_id,
                workflow_payload=workflow_payload,
            ),
            diagnostic=OutputSourceDiagnostic(
                level="warning",
                message="Using node-local output source after missing cube-output mapping",
                fields={
                    "workflow_id": workflow_id,
                    "prompt_id": prompt_id,
                    "node_id": node_id,
                    "cube_output_node_ids": tuple(sorted(cube_output_node_ids)),
                },
            ),
        )

    return OutputSourceResolution(
        source_identity=output_source_identity_for_node(
            cube_output_node_id,
            workflow_id=workflow_id,
            workflow_payload=workflow_payload,
        )
    )


def output_source_identity_for_node(
    node_id: str,
    *,
    workflow_id: str,
    workflow_payload: dict[str, object],
) -> OutputSourceIdentity:
    """Return canvas source identity for one executable output node."""

    cube_alias = cube_alias_for_node(node_id, workflow_payload)
    source_label = cube_alias or node_id
    return OutputSourceIdentity(
        node_id=node_id,
        source_key=f"{workflow_id}:{node_id}",
        source_label=source_label,
        cube_alias=cube_alias,
    )


def cube_alias_for_node(node_id: str, workflow_payload: dict[str, object]) -> str:
    """Return output cube alias from node metadata with legacy semantics."""

    node_data = prompt_nodes(workflow_payload).get(node_id, {})
    meta_title = ""
    if isinstance(node_data, dict):
        meta_payload = node_data.get("_meta", {})
        if isinstance(meta_payload, dict):
            maybe_title = meta_payload.get("title")
            if isinstance(maybe_title, str):
                meta_title = maybe_title
    cube_alias = meta_title.split(".", 1)[0] if "." in meta_title else meta_title
    return safe_component(cube_alias_body(cube_alias))


def cube_number_for_source_identity(
    source_identity: OutputSourceIdentity,
    cube_numbers_by_alias: Mapping[str, int],
) -> int | None:
    """Return the workflow-order cube number for one output source identity."""

    for key in (
        source_identity.cube_alias,
        source_identity.source_label,
        source_identity.node_id,
    ):
        if not key:
            continue
        cube_number = cube_numbers_by_alias.get(key)
        if cube_number is not None:
            return cube_number
    return None


def output_cube_numbers_by_alias(workflow_payload: dict[str, object]) -> dict[str, int]:
    """Return fallback cube-order lookup from executable output node metadata."""

    numbers: dict[str, int] = {}
    output_index = 0
    for node_id, node_data in prompt_nodes(workflow_payload).items():
        if not isinstance(node_data, dict):
            continue
        if node_data.get("class_type") != "SugarCubes.CubeOutput":
            continue
        output_index += 1
        cube_alias = cube_alias_from_node_data(node_data) or node_id
        for key in {node_id, cube_alias, cube_alias_body(cube_alias)}:
            cleaned = str(key).strip()
            if cleaned and cleaned not in numbers:
                numbers[cleaned] = output_index
    return numbers


def cube_alias_from_node_data(node_data: Mapping[str, object]) -> str:
    """Return a cube alias from executable node metadata when present."""

    meta_payload = node_data.get("_meta", {})
    if not isinstance(meta_payload, Mapping):
        return ""
    maybe_title = meta_payload.get("title")
    if not isinstance(maybe_title, str):
        return ""
    cube_alias = maybe_title.split(".", 1)[0] if "." in maybe_title else maybe_title
    return cube_alias_body(cube_alias)
