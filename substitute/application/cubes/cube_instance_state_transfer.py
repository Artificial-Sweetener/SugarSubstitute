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
_MISSING = object()


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
    dropped_authored_input_ids: tuple[str, ...] = ()

    @property
    def has_destructive_loss(self) -> bool:
        """Return whether applying the update would discard authored state."""

        return bool(self.dropped_authored_input_ids)


@dataclass(frozen=True, slots=True)
class CubeInstanceStateTransferResult:
    """Carry the loader patch and diagnostics produced by state transfer."""

    buffer_patch: JsonObject
    report: CubeInstanceStateTransferReport


class CubeAuthoredStateLossError(RuntimeError):
    """Reject a Cube update that cannot preserve authored instance values."""

    def __init__(self, input_ids: tuple[str, ...]) -> None:
        """Describe the exact authored fields that the update would discard."""

        self.input_ids = input_ids
        joined = ", ".join(input_ids)
        super().__init__(f"Cube update would discard authored values: {joined}")


@dataclass(frozen=True, slots=True)
class _CubeTransferSources:
    """Separate canonical documents from their implementation value buffers."""

    old_document: Mapping[str, Any]
    old_definition_implementation: Mapping[str, Any]
    old_instance_implementation: Mapping[str, Any]
    new_document: Mapping[str, Any]
    new_implementation: Mapping[str, Any]


class CubeInstanceStateTransferService:
    """Build a safe loader patch from old user values and the new definition."""

    def transfer(
        self,
        *,
        old_cube: CubeState,
        new_cube_definition: Mapping[str, Any],
    ) -> CubeInstanceStateTransferResult:
        """Transfer user-authored state without copying old definition structure."""

        sources = _CubeTransferSources(
            old_document=old_cube.original_cube,
            old_definition_implementation=_implementation_of(old_cube.original_cube),
            old_instance_implementation=old_cube.buffer,
            new_document=new_cube_definition,
            new_implementation=_implementation_of(new_cube_definition),
        )

        patch: JsonObject = {
            "cube_id": str(new_cube_definition.get("cube_id") or old_cube.cube_id),
            "version": str(new_cube_definition.get("version") or old_cube.version),
        }

        report = _transfer_surface_values(
            patch=patch,
            sources=sources,
        )
        excluded_node_inputs = _surface_control_input_keys(sources.old_document)
        _transfer_compatible_node_inputs(
            patch=patch,
            sources=sources,
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
    sources: _CubeTransferSources,
) -> CubeInstanceStateTransferReport:
    """Preserve surface values by stable control id."""

    old_controls = _controls_by_id(sources.old_document)
    new_controls = _controls_by_id(sources.new_document)
    patch_nodes = _ensure_patch_nodes(patch)
    preserved = 0
    incompatible: list[str] = []
    dropped_authored: list[str] = []
    for control_id, new_control in new_controls.items():
        old_control = old_controls.get(control_id)
        if old_control is None:
            continue
        old_value = _control_value(
            sources.old_instance_implementation,
            old_control,
        )
        old_default = _control_value(
            sources.old_definition_implementation,
            old_control,
        )
        authored = old_value is not _MISSING and old_value != old_default
        if _control_value_type(old_control) != _control_value_type(new_control):
            incompatible.append(control_id)
            if authored:
                dropped_authored.append(f"surface.{control_id}")
            continue
        if old_value is _MISSING:
            continue
        input_name = str(new_control.get("input_name") or "")
        symbol = str(new_control.get("symbol") or "")
        new_node = _node_map(sources.new_implementation).get(symbol)
        new_inputs = new_node.get("inputs") if new_node is not None else None
        if (
            not input_name
            or not symbol
            or not isinstance(new_inputs, Mapping)
            or input_name not in new_inputs
            or _is_link(new_inputs[input_name])
        ):
            incompatible.append(control_id)
            if authored:
                dropped_authored.append(f"surface.{control_id}")
            continue
        patch_nodes.setdefault(symbol, {"inputs": {}})
        patch_node = patch_nodes[symbol]
        if isinstance(patch_node, dict):
            inputs = patch_node.setdefault("inputs", {})
            if isinstance(inputs, dict):
                inputs[input_name] = copy.deepcopy(old_value)
                preserved += 1
    removed = tuple(sorted(set(old_controls) - set(new_controls)))
    for control_id in removed:
        old_control = old_controls[control_id]
        old_value = _control_value(
            sources.old_instance_implementation,
            old_control,
        )
        old_default = _control_value(
            sources.old_definition_implementation,
            old_control,
        )
        if old_value is not _MISSING and old_value != old_default:
            dropped_authored.append(f"surface.{control_id}")
    added = tuple(sorted(set(new_controls) - set(old_controls)))
    return CubeInstanceStateTransferReport(
        preserved_surface_value_count=preserved,
        dropped_surface_value_count=len(removed) + len(incompatible),
        added_control_ids=added,
        removed_control_ids=removed,
        incompatible_control_ids=tuple(sorted(incompatible)),
        dropped_authored_input_ids=tuple(sorted(set(dropped_authored))),
    )


def _transfer_compatible_node_inputs(
    *,
    patch: JsonObject,
    sources: _CubeTransferSources,
    report: CubeInstanceStateTransferReport,
    excluded_node_inputs: frozenset[tuple[str, str]],
) -> None:
    """Copy compatible node inputs by node name, input name, and class type."""

    old_nodes = _node_map(sources.old_instance_implementation)
    old_definition_nodes = _node_map(sources.old_definition_implementation)
    new_nodes = _node_map(sources.new_implementation)
    patch_nodes = _ensure_patch_nodes(patch)
    preserved_inputs = 0
    dropped_inputs = 0
    preserved_links = 0
    dropped_links = 0
    dropped_authored = list(report.dropped_authored_input_ids)
    for node_name, old_node in old_nodes.items():
        new_node = new_nodes.get(node_name)
        old_definition_node = old_definition_nodes.get(node_name)
        old_inputs = old_node.get("inputs")
        if not isinstance(old_inputs, Mapping):
            continue
        old_default_inputs = (
            old_definition_node.get("inputs")
            if old_definition_node is not None
            else None
        )
        if not isinstance(old_default_inputs, Mapping):
            old_default_inputs = {}
        new_inputs = new_node.get("inputs") if new_node is not None else None
        for input_name, value in old_inputs.items():
            input_key = (node_name, str(input_name))
            if input_key in excluded_node_inputs:
                continue
            if _is_link(value):
                dropped_links += 1
                continue
            old_default = old_default_inputs.get(input_name, _MISSING)
            if old_default is not _MISSING and value == old_default:
                continue
            input_id = f"{node_name}.{input_name}"
            compatible_node = (
                new_node is not None
                and old_definition_node is not None
                and old_definition_node.get("class_type") == new_node.get("class_type")
            )
            if (
                not compatible_node
                or not isinstance(new_inputs, Mapping)
                or input_name not in new_inputs
                or _is_link(new_inputs[input_name])
            ):
                dropped_inputs += 1
                dropped_authored.append(input_id)
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
    report.dropped_authored_input_ids = tuple(sorted(set(dropped_authored)))


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


def _implementation_of(document: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a canonical document's implementation or its legacy flat shape."""

    implementation = document.get("implementation")
    return implementation if isinstance(implementation, Mapping) else document


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


def _control_value(
    implementation: Mapping[str, Any],
    control: Mapping[str, Any],
) -> object:
    """Return one control's live or default implementation value."""

    symbol = str(control.get("symbol") or "")
    input_name = str(control.get("input_name") or "")
    node = _node_map(implementation).get(symbol)
    inputs = node.get("inputs") if node is not None else None
    if not isinstance(inputs, Mapping) or input_name not in inputs:
        return _MISSING
    return inputs[input_name]


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


def _is_link(value: object) -> bool:
    """Return whether a value is a Comfy node link shape."""

    return (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


__all__ = [
    "CubeAuthoredStateLossError",
    "CubeInstanceStateTransferReport",
    "CubeInstanceStateTransferResult",
    "CubeInstanceStateTransferService",
    "structural_patch_keys",
]
