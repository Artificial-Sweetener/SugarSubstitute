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

"""Normalize loose snapshot values into strict JSON-compatible values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import cast
from uuid import UUID

from substitute.domain.common import JsonObject
from substitute.domain.cube_library import CubeIconDescriptor

from .errors import SnapshotCodecError


def json_object_to_json(value: Mapping[str, object], *, path: str) -> JsonObject:
    """Return a JSON-ready copy of one loose internal mapping."""

    return {
        str(item_key): json_value_to_json(
            item_value,
            path=f"{path}.{item_key}",
        )
        for item_key, item_value in value.items()
    }


def json_value_to_json(value: object, *, path: str) -> object:
    """Return a JSON-ready value or fail with its precise snapshot path."""

    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, UUID | Path):
        return str(value)
    if isinstance(value, Enum):
        enum_value = value.value
        if isinstance(enum_value, str | int | float | bool):
            return enum_value
        raise SnapshotCodecError(f"Unsupported enum value at {path}")
    if isinstance(value, CubeIconDescriptor):
        return _cube_icon_descriptor_to_json(value)
    if isinstance(value, Mapping):
        return json_object_to_json(cast(Mapping[str, object], value), path=path)
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [json_value_to_json(item, path=f"{path}[]") for item in value]
    raise SnapshotCodecError(
        f"Unsupported JSON snapshot value at {path}: {type(value).__name__}"
    )


def _cube_icon_descriptor_to_json(icon: CubeIconDescriptor) -> JsonObject:
    """Return JSON-ready Cube icon descriptor metadata."""

    return {
        "kind": icon.kind,
        "url": icon.url,
        "media_type": icon.media_type,
        "repo_relative_path": icon.repo_relative_path,
        "color_behavior": icon.color_behavior,
    }


__all__ = ["json_object_to_json", "json_value_to_json"]
