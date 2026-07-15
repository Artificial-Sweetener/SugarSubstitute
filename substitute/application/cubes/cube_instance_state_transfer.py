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

"""Transfer user-authored cube instance state across definition updates."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState

_STRUCTURAL_PATCH_KEYS = {
    "definitions",
    "flavors",
    "implementation",
    "inputs",
    "layout",
    "outputs",
    "subgraphs",
    "surface",
}


@dataclass(slots=True)
class CubeInstanceStateTransferReport:
    """Summarize values preserved and dropped while updating a cube instance."""

    preserved_surface_value_count: int = 0
    dropped_surface_value_count: int = 0
    preserved_node_input_count: int = 0
    dropped_node_input_count: int = 0
    preserved_link_count: int = 0
    dropped_link_count: int = 0
    added_control_ids: tuple[str, ...] = ()
    removed_control_ids: tuple[str, ...] = ()
    incompatible_control_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CubeInstanceStateTransferResult:
    """Carry the loader patch and diagnostics produced by state transfer."""

    buffer_patch: JsonObject
    report: CubeInstanceStateTransferReport


class CubeInstanceStateTransferService:
    """Build a safe loader patch from old user values and the new definition."""

    def transfer(
        self,
        *,
        old_cube: CubeState,
        new_cube_definition: Mapping[str, Any],
    ) -> CubeInstanceStateTransferResult:
        """Transfer user-authored state without copying old definition structure."""

        patch: JsonObject = {
            "cube_id": str(new_cube_definition.get("cube_id") or old_cube.cube_id),
            "version": str(new_cube_definition.get("version") or old_cube.version),
        }

        report = _transfer_surface_values(
            patch=patch,
            old_buffer=old_cube.buffer,
            new_definition=new_cube_definition,
        )
        excluded_node_inputs = _surface_control_input_keys(old_cube.buffer)
        _transfer_compatible_node_inputs(
            patch=patch,
            old_buffer=old_cube.buffer,
            old_definition=old_cube.original_cube,
            new_definition=new_cube_definition,
            report=report,
            excluded_node_inputs=excluded_node_inputs,
        )
        return CubeInstanceStateTransferResult(buffer_patch=patch, report=report)


def structural_patch_keys() -> frozenset[str]:
    """Return definition-owned keys that must never be restored as raw patches."""

    return frozenset(_STRUCTURAL_PATCH_KEYS)


def _transfer_surface_values(
    *,
    patch: JsonObject,
    old_buffer: Mapping[str, Any],
    new_definition: Mapping[str, Any],
) -> CubeInstanceStateTransferReport:
    """Preserve surface values by stable control id."""

    old_controls = _controls_by_id(old_buffer)
    new_controls = _controls_by_id(new_definition)
    patch_nodes = _ensure_patch_nodes(patch)
    preserved = 0
    incompatible: list[str] = []
    for control_id, new_control in new_controls.items():
        old_control = old_controls.get(control_id)
        if old_control is None:
            continue
        if _control_value_type(old_control) != _control_value_type(new_control):
            incompatible.append(control_id)
            continue
        old_node = _node_for_control(old_buffer, old_control)
        if old_node is None:
            continue
        input_name = str(new_control.get("input_name") or "")
        old_input_name = str(old_control.get("input_name") or "")
        if not input_name or not old_input_name:
            continue
        old_inputs = old_node.get("inputs")
        if not isinstance(old_inputs, Mapping) or old_input_name not in old_inputs:
            continue
        symbol = str(new_control.get("symbol") or "")
        if not symbol:
            continue
        patch_nodes.setdefault(symbol, {"inputs": {}})
        patch_node = patch_nodes[symbol]
        if isinstance(patch_node, dict):
            inputs = patch_node.setdefault("inputs", {})
            if isinstance(inputs, dict):
                inputs[input_name] = copy.deepcopy(old_inputs[old_input_name])
                preserved += 1
    removed = tuple(sorted(set(old_controls) - set(new_controls)))
    added = tuple(sorted(set(new_controls) - set(old_controls)))
    return CubeInstanceStateTransferReport(
        preserved_surface_value_count=preserved,
        dropped_surface_value_count=len(removed) + len(incompatible),
        added_control_ids=added,
        removed_control_ids=removed,
        incompatible_control_ids=tuple(sorted(incompatible)),
    )


def _transfer_compatible_node_inputs(
    *,
    patch: JsonObject,
    old_buffer: Mapping[str, Any],
    old_definition: Mapping[str, Any],
    new_definition: Mapping[str, Any],
    report: CubeInstanceStateTransferReport,
    excluded_node_inputs: frozenset[tuple[str, str]],
) -> None:
    """Copy compatible node inputs by node name, input name, and class type."""

    old_nodes = _node_map(old_buffer)
    old_definition_nodes = _node_map(old_definition)
    new_nodes = _node_map(new_definition)
    patch_nodes = _ensure_patch_nodes(patch)
    preserved_inputs = 0
    dropped_inputs = 0
    preserved_links = 0
    dropped_links = 0
    for node_name, old_node in old_nodes.items():
        new_node = new_nodes.get(node_name)
        old_definition_node = old_definition_nodes.get(node_name)
        if new_node is None or old_definition_node is None:
            dropped_inputs += _transferable_input_count(
                old_node,
                node_name=node_name,
                excluded_node_inputs=excluded_node_inputs,
            )
            continue
        if old_definition_node.get("class_type") != new_node.get("class_type"):
            dropped_inputs += _transferable_input_count(
                old_node,
                node_name=node_name,
                excluded_node_inputs=excluded_node_inputs,
            )
            continue
        old_inputs = old_node.get("inputs")
        new_inputs = new_node.get("inputs")
        if not isinstance(old_inputs, Mapping) or not isinstance(new_inputs, Mapping):
            continue
        for input_name, value in old_inputs.items():
            input_key = (node_name, str(input_name))
            if input_key in excluded_node_inputs:
                continue
            if input_name not in new_inputs:
                dropped_inputs += 1
                continue
            if _is_link(value):
                if _link_endpoint_exists(value, new_nodes):
                    preserved_links += 1
                else:
                    dropped_links += 1
                    continue
            patch_nodes.setdefault(node_name, {"inputs": {}})
            patch_node = patch_nodes[node_name]
            if isinstance(patch_node, dict):
                inputs = patch_node.setdefault("inputs", {})
                if isinstance(inputs, dict):
                    inputs[str(input_name)] = copy.deepcopy(value)
                    preserved_inputs += 1
    report.preserved_node_input_count += preserved_inputs
    report.dropped_node_input_count += dropped_inputs
    report.preserved_link_count += preserved_links
    report.dropped_link_count += dropped_links


def _controls_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Return surface controls keyed by stable control id."""

    surface = payload.get("surface")
    if not isinstance(surface, Mapping):
        return {}
    controls = surface.get("controls")
    if not isinstance(controls, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for control in controls:
        if not isinstance(control, Mapping):
            continue
        control_id = str(control.get("control_id") or "")
        if control_id:
            result[control_id] = control
    return result


def _surface_control_input_keys(
    payload: Mapping[str, Any],
) -> frozenset[tuple[str, str]]:
    """Return node inputs whose transfer is owned by surface control identity."""

    keys: set[tuple[str, str]] = set()
    for control in _controls_by_id(payload).values():
        symbol = str(control.get("symbol") or "")
        input_name = str(control.get("input_name") or "")
        if symbol and input_name:
            keys.add((symbol, input_name))
    return frozenset(keys)


def _node_for_control(
    payload: Mapping[str, Any],
    control: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Return the node referenced by one surface control."""

    symbol = str(control.get("symbol") or "")
    if not symbol:
        return None
    node = _node_map(payload).get(symbol)
    return node if isinstance(node, Mapping) else None


def _control_value_type(control: Mapping[str, Any]) -> str:
    """Return the value type used for surface compatibility checks."""

    return str(control.get("value_type") or "")


def _node_map(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Return runtime node mappings from a cube-shaped payload."""

    nodes = payload.get("nodes")
    if not isinstance(nodes, Mapping):
        return {}
    return {
        str(name): node
        for name, node in nodes.items()
        if isinstance(name, str) and isinstance(node, Mapping)
    }


def _ensure_patch_nodes(patch: JsonObject) -> dict[str, Any]:
    """Return the mutable node patch mapping."""

    nodes = patch.setdefault("nodes", {})
    if not isinstance(nodes, dict):
        nodes = {}
        patch["nodes"] = nodes
    return nodes


def _transferable_input_count(
    node: Mapping[str, Any],
    *,
    node_name: str,
    excluded_node_inputs: frozenset[tuple[str, str]],
) -> int:
    """Return input count excluding surface-owned values."""

    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return 0
    return sum(
        1
        for input_name in inputs
        if (node_name, str(input_name)) not in excluded_node_inputs
    )


def _is_link(value: object) -> bool:
    """Return whether a value is a Comfy node link shape."""

    return (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _link_endpoint_exists(
    value: object, nodes: Mapping[str, Mapping[str, Any]]
) -> bool:
    """Return whether a persisted link endpoint still exists."""

    if not _is_link(value) or not isinstance(value, list):
        return False
    return str(value[0]) in nodes


__all__ = [
    "CubeInstanceStateTransferReport",
    "CubeInstanceStateTransferResult",
    "CubeInstanceStateTransferService",
    "structural_patch_keys",
]
