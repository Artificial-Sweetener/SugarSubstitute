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

"""Persist Cube editor state that is not part of native graph semantics."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from substitute.domain.common import JsonObject
from substitute.domain.cube_library import CubeIconDescriptor, CubeUpdatePolicy
from substitute.domain.generation.seed_control import (
    SeedControlState,
    seed_control_state_from_json,
    seed_control_state_to_json,
)
from substitute.domain.workflow import CubeState

from .errors import SnapshotCodecError
from .json_value_codec import json_object_to_json

_GRAPH_OWNED_UI_KEYS = frozenset({"canonical_cube", "graph_node_id"})
_RUNTIME_UI_KEYS = frozenset({"node_behavior_runtime"})


def capture_cube_projection_state(cubes: Mapping[str, CubeState]) -> JsonObject:
    """Capture editor-only state keyed by stable native graph node identity."""

    result: JsonObject = {}
    for cube in cubes.values():
        ui = cube.ui
        if not isinstance(ui, Mapping):
            continue
        node_id = ui.get("graph_node_id")
        if isinstance(node_id, bool) or not isinstance(node_id, str | int):
            continue
        durable_ui = {
            key: value
            for key, value in ui.items()
            if key not in _GRAPH_OWNED_UI_KEYS and key not in _RUNTIME_UI_KEYS
        }
        result[str(node_id)] = {
            "display_name": cube.display_name,
            "undo_stack": deepcopy(cube.undo_stack),
            "redo_stack": deepcopy(cube.redo_stack),
            "dirty": cube.dirty,
            "ui": json_object_to_json(
                durable_ui,
                path=f"workflow.cube_projection_state.{node_id}.ui",
            ),
            "field_control_states": _seed_states_to_json(cube.field_control_states),
            "update_policy": cube.update_policy.value,
            "output_persistence_enabled": cube.output_persistence_enabled,
        }
    return result


def restore_cube_projection_state(
    cubes: Mapping[str, CubeState],
    value: Mapping[str, object],
) -> None:
    """Apply editor-only state without overriding graph identity, values, or mode."""

    cubes_by_node_id = {
        str(node_id): cube
        for cube in cubes.values()
        if isinstance((ui := cube.ui), Mapping)
        and (node_id := ui.get("graph_node_id")) is not None
    }
    for node_id, raw_state in value.items():
        cube = cubes_by_node_id.get(str(node_id))
        if cube is None or not isinstance(raw_state, Mapping):
            continue
        display_name = raw_state.get("display_name")
        if isinstance(display_name, str) and display_name:
            cube.display_name = display_name
        cube.undo_stack = _json_object_list(raw_state.get("undo_stack"))
        cube.redo_stack = _json_object_list(raw_state.get("redo_stack"))
        cube.dirty = raw_state.get("dirty") is True
        cube.ui = {
            **(cube.ui if isinstance(cube.ui, dict) else {}),
            **_editor_ui_from_json(raw_state.get("ui")),
        }
        cube.field_control_states = _seed_states_from_json(
            raw_state.get("field_control_states")
        )
        cube.update_policy = _update_policy(raw_state.get("update_policy"))
        cube.output_persistence_enabled = (
            raw_state.get("output_persistence_enabled") is not False
        )


def transfer_cube_projection_state(
    source: Mapping[str, CubeState],
    target: Mapping[str, CubeState],
) -> None:
    """Transfer editor-only state by alias during one-time legacy migration."""

    for alias, target_cube in target.items():
        source_cube = source.get(alias)
        if source_cube is None:
            continue
        target_cube.display_name = source_cube.display_name
        target_cube.undo_stack = deepcopy(source_cube.undo_stack)
        target_cube.redo_stack = deepcopy(source_cube.redo_stack)
        target_cube.dirty = source_cube.dirty
        source_ui = source_cube.ui if isinstance(source_cube.ui, Mapping) else {}
        durable_ui = {
            key: deepcopy(value)
            for key, value in source_ui.items()
            if key not in _GRAPH_OWNED_UI_KEYS and key not in _RUNTIME_UI_KEYS
        }
        target_cube.ui = {
            **(target_cube.ui if isinstance(target_cube.ui, dict) else {}),
            **durable_ui,
        }
        target_cube.field_control_states = deepcopy(source_cube.field_control_states)
        target_cube.update_policy = source_cube.update_policy
        target_cube.output_persistence_enabled = source_cube.output_persistence_enabled


def _seed_states_to_json(
    states: Mapping[str, Mapping[str, SeedControlState]],
) -> JsonObject:
    """Encode nested seed controls without Cube document data."""

    return {
        str(node_name): {
            str(field_name): seed_control_state_to_json(state)
            for field_name, state in field_states.items()
        }
        for node_name, field_states in states.items()
    }


def _seed_states_from_json(
    value: object,
) -> dict[str, dict[str, SeedControlState]]:
    """Decode nested seed controls conservatively."""

    if not isinstance(value, Mapping):
        return {}
    result: dict[str, dict[str, SeedControlState]] = {}
    for node_name, field_states in value.items():
        if not isinstance(field_states, Mapping):
            continue
        result[str(node_name)] = {
            str(field_name): seed_control_state_from_json(state)
            for field_name, state in field_states.items()
        }
    return result


def _json_object_list(value: object) -> list[JsonObject]:
    """Decode an optional list of object-only editor history records."""

    if not isinstance(value, list):
        return []
    if not all(isinstance(item, Mapping) for item in value):
        raise SnapshotCodecError("Cube editor history must contain JSON objects.")
    return [deepcopy(dict(item)) for item in value]


def _editor_ui_from_json(value: object) -> dict[str, object]:
    """Decode durable UI metadata and restore known value objects."""

    if not isinstance(value, Mapping):
        return {}
    result = deepcopy(dict(value))
    icon = result.get("cube_icon")
    if isinstance(icon, Mapping):
        result["cube_icon"] = CubeIconDescriptor(
            kind=str(icon.get("kind") or ""),
            url=str(icon.get("url") or ""),
            media_type=str(icon.get("media_type") or ""),
            repo_relative_path=str(icon.get("repo_relative_path") or ""),
            color_behavior=str(icon.get("color_behavior") or "auto"),
        )
    return result


def _update_policy(value: object) -> CubeUpdatePolicy:
    """Decode a supported update policy or reject corrupt editor state."""

    if value is None:
        return CubeUpdatePolicy.PINNED
    if not isinstance(value, str):
        raise SnapshotCodecError("Cube editor update policy must be text.")
    try:
        return CubeUpdatePolicy(value)
    except ValueError as error:
        raise SnapshotCodecError(
            f"Unsupported Cube editor update policy: {value}"
        ) from error


__all__ = [
    "capture_cube_projection_state",
    "restore_cube_projection_state",
    "transfer_cube_projection_state",
]
