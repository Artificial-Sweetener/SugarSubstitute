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

"""Capture savable node input values for node input presets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TypeAlias

from substitute.application.node_behavior import ResolvedFieldSpec

JsonObject: TypeAlias = dict[str, object]
JsonValue: TypeAlias = object


def capture_savable_node_inputs(
    *,
    node_inputs: Mapping[str, object],
    field_specs: Mapping[str, ResolvedFieldSpec],
    is_connection: Callable[[object], bool],
) -> JsonObject:
    """Return editable JSON-safe node inputs that can be stored in a preset."""

    captured: JsonObject = {}
    for field_key in field_specs:
        if field_key not in node_inputs:
            continue
        value = node_inputs[field_key]
        if is_connection(value):
            continue
        copied = _copy_json_value(value)
        if copied is not _UNSAFE:
            captured[field_key] = copied
    return captured


class _UnsafeValue:
    """Mark values that should not be saved in node input presets."""


_UNSAFE = _UnsafeValue()


def _copy_json_value(value: object) -> JsonValue | _UnsafeValue:
    """Return a detached JSON value, or ``_UNSAFE`` when unsupported."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, tuple):
        return _UNSAFE
    if isinstance(value, list):
        if _is_graph_connection_value(value):
            return _UNSAFE
        copied_items: list[JsonValue] = []
        for item in value:
            copied_item = _copy_json_value(item)
            if copied_item is _UNSAFE:
                return _UNSAFE
            copied_items.append(copied_item)
        return copied_items
    if isinstance(value, dict):
        copied_dict: JsonObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                return _UNSAFE
            copied_item = _copy_json_value(item)
            if copied_item is _UNSAFE:
                return _UNSAFE
            copied_dict[key] = copied_item
        return copied_dict
    return _UNSAFE


def _is_graph_connection_value(value: list[object]) -> bool:
    """Return whether a list has Comfy's common graph-connection shape."""

    return len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


__all__ = ["capture_savable_node_inputs"]
