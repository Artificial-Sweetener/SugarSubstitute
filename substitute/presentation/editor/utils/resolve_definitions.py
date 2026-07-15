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

"""Resolve node input definitions into UI-friendly field metadata."""

from __future__ import annotations

from typing import Any


def resolve_input_definition(
    definitions: dict[str, Any],
    node_type: str,
    key: str,
) -> tuple[str | None, dict[str, Any], list[Any] | None, dict[str, Any]]:
    """
    Safely resolve the type and metadata for a given input key based on cube definitions.
    Returns: (type_name: str or None, meta_info: dict, field_info: list or None, constraints: dict)
    constraints: dict with optional keys 'min', 'max', 'step' (may be None if not available)
    """
    type_name = None
    meta_info: dict[str, Any] = {}
    field_info: list[Any] | None = None
    constraints: dict[str, Any] = {"min": None, "max": None, "step": None}

    node_def = definitions.get(node_type, {}).get("input", {})
    combined: dict[str, Any] = {}

    for subkey in ("required", "optional"):
        inputs = node_def.get(subkey, {})
        if inputs:
            combined.update(inputs)

    field_info = combined.get(key)

    if isinstance(field_info, list):
        if len(field_info) == 2:
            if isinstance(field_info[0], str):
                type_name = field_info[0]
                meta_info = field_info[1] if isinstance(field_info[1], dict) else {}
            elif isinstance(field_info[0], list):
                type_name = "LIST"
                meta_info = field_info[1] if isinstance(field_info[1], dict) else {}
        elif len(field_info) == 1:
            if isinstance(field_info[0], str):
                type_name = field_info[0]
            elif isinstance(field_info[0], list):
                type_name = "LIST"

    if isinstance(meta_info, dict):
        constraints["min"] = meta_info.get("min")
        constraints["max"] = meta_info.get("max")
        constraints["step"] = meta_info.get("step")

    return type_name, meta_info, field_info, constraints
