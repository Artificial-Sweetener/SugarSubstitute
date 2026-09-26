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

"""Describe stable editor field identities and their persistence locations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

NODE_STATE_KEYS = frozenset({"enabled"})
DISPLAY_FALLBACK_VALUE_SOURCES = frozenset({"first_option", "live_default"})

FieldStorageKind = Literal["input", "node"]


@dataclass(frozen=True, slots=True)
class EditorFieldBinding:
    """Identify one editor field and how its value is stored."""

    cube_alias: str | None
    node_name: str | None
    field_key: str
    storage_kind: FieldStorageKind
    value_source: str | None
    resolved_display_value: object | None
    prompt_field_identity: str | None
    node_type: str | None = None
    field_type: str | None = None
    native_widget_type: str | None = None

    @classmethod
    def from_metadata(cls, metadata: object) -> EditorFieldBinding | None:
        """Create a typed field binding from sanitized Qt input metadata."""

        if not isinstance(metadata, Mapping):
            return None
        raw_key = metadata.get("key")
        if not isinstance(raw_key, str) or not raw_key.strip():
            return None
        raw_node_name = metadata.get("node_name")
        node_name = raw_node_name if isinstance(raw_node_name, str) else None
        raw_cube_alias = metadata.get("cube_alias")
        cube_alias = raw_cube_alias if isinstance(raw_cube_alias, str) else None
        value_source = metadata.get("value_source")
        node_type = metadata.get("node_type")
        field_type = metadata.get("type")
        meta_info = metadata.get("meta_info")
        native_widget_type = (
            meta_info.get("native_widget_type")
            if isinstance(meta_info, Mapping)
            else None
        )
        field_key = raw_key.strip()
        prompt_identity = (
            f"{node_name.strip()}.{field_key}"
            if isinstance(node_name, str) and node_name.strip()
            else None
        )
        return cls(
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=field_key,
            storage_kind="node" if field_key in NODE_STATE_KEYS else "input",
            value_source=value_source if isinstance(value_source, str) else None,
            resolved_display_value=metadata.get("resolved_value"),
            prompt_field_identity=prompt_identity,
            node_type=node_type if isinstance(node_type, str) else None,
            field_type=field_type if isinstance(field_type, str) else None,
            native_widget_type=(
                native_widget_type if isinstance(native_widget_type, str) else None
            ),
        )

    @classmethod
    def from_widget(cls, widget: object) -> EditorFieldBinding | None:
        """Create a typed binding from one widget's Qt metadata."""

        property_getter = getattr(widget, "property", None)
        if not callable(property_getter):
            return None
        return cls.from_metadata(property_getter("input_metadata"))


__all__ = [
    "DISPLAY_FALLBACK_VALUE_SOURCES",
    "EditorFieldBinding",
    "FieldStorageKind",
    "NODE_STATE_KEYS",
]
