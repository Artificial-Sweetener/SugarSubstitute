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

"""Transform workflow cube buffers at the recipe persistence boundary."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping
from typing import Any, Protocol, cast

from substitute.domain.common import JsonObject, JsonValue
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.recipes.sugar_ast import SugarBufferMap
from substitute.domain.workflow import CubeState


class RecipeCubeState(Protocol):
    """Describe cube state consumed by recipe buffer serialization."""

    @property
    def cube_id(self) -> str:
        """Return the persisted cube identity."""

        ...

    @property
    def version(self) -> str:
        """Return the persisted cube version."""

        ...

    @property
    def buffer(self) -> Mapping[str, JsonValue]:
        """Return the current workflow buffer."""

        ...


def strip_recipe_buffers(
    ordered_aliases: Iterable[str],
    cube_states: Mapping[str, RecipeCubeState],
) -> SugarBufferMap:
    """Return persistence-safe buffers in recipe stack order."""

    stripped_buffers: SugarBufferMap = OrderedDict()
    for alias in ordered_aliases:
        cube_state = cube_states[alias]
        buffer_data: OrderedDict[str, JsonValue] = OrderedDict()
        buffer_data["cube_id"] = cube_state.cube_id
        buffer_data["version"] = cube_state.version
        update_policy = getattr(cube_state, "update_policy", None)
        if not isinstance(update_policy, CubeUpdatePolicy):
            update_policy = (
                CubeUpdatePolicy.PINNED
                if cube_state.version.strip()
                else CubeUpdatePolicy.FOLLOW_LATEST
            )
        buffer_data["update_policy"] = update_policy.value
        buffer_data["bypassed"] = getattr(cube_state, "bypassed", False) is True
        buffer_data["save_outputs"] = (
            getattr(cube_state, "output_persistence_enabled", True) is not False
        )
        for key, value in cube_state.buffer.items():
            if key == "definitions":
                continue
            if key not in {
                "cube_id",
                "version",
                "update_policy",
                "bypassed",
                "save_outputs",
            }:
                buffer_data[key] = value
        stripped_buffers[alias] = buffer_data
    return stripped_buffers


def restore_recipe_cube_state(
    alias: str,
    buffer_data: JsonObject,
    get_cube_definition: Any,
) -> CubeState:
    """Build workflow cube state from one persisted recipe buffer."""

    cube_id = str(buffer_data["cube_id"])
    original_cube = get_cube_definition(cube_id)
    version = str(buffer_data.get("version") or original_cube.get("version") or "")
    return CubeState(
        cube_id=cube_id,
        version=version,
        alias=alias,
        original_cube=original_cube,
        buffer=buffer_data,
        update_policy=recipe_buffer_update_policy(buffer_data),
        bypassed=buffer_data.get("bypassed") is True,
        output_persistence_enabled=buffer_data.get("save_outputs") is not False,
    )


def merge_recipe_buffer(
    buffer: JsonObject,
    patch: Mapping[str, JsonValue],
    cube_definition: Mapping[str, JsonValue] | None = None,
) -> None:
    """Overlay a schema-filtered patch into a recipe buffer recursively."""

    if cube_definition is None:
        cube_definition = buffer

    for key, value in patch.items():
        if isinstance(value, dict) and key in buffer and isinstance(buffer[key], dict):
            definition_value = cube_definition.get(key) if cube_definition else None
            nested_definition = (
                definition_value if isinstance(definition_value, dict) else None
            )
            nested_buffer = cast(JsonObject, buffer[key])
            merge_recipe_buffer(
                buffer=nested_buffer,
                patch=value,
                cube_definition=nested_definition,
            )
            continue
        if (
            cube_definition is None
            or key in cube_definition
            or key in _PERSISTED_METADATA_KEYS
        ):
            buffer[key] = value


def recipe_buffer_update_policy(
    buffer_data: Mapping[str, JsonValue],
) -> CubeUpdatePolicy:
    """Return the update policy represented by one persisted buffer."""

    raw_policy = buffer_data.get("update_policy")
    if isinstance(raw_policy, str) and raw_policy:
        try:
            return CubeUpdatePolicy(raw_policy)
        except ValueError:
            pass
    version = buffer_data.get("version")
    if isinstance(version, str) and version.strip():
        return CubeUpdatePolicy.PINNED
    return CubeUpdatePolicy.FOLLOW_LATEST


_PERSISTED_METADATA_KEYS = frozenset(
    {
        "node_link",
        "prompt_link",
        "sampler_link",
        "scheduler_link",
        "enabled",
        "revealed",
        "save_outputs",
    }
)

__all__ = [
    "merge_recipe_buffer",
    "RecipeCubeState",
    "recipe_buffer_update_policy",
    "restore_recipe_cube_state",
    "strip_recipe_buffers",
]
