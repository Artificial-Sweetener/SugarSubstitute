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

"""Resolve semantic field identities from widget metadata."""

from __future__ import annotations

from typing import Any


def scoped_field_key(input_metadata: dict[str, Any] | None) -> object | None:
    """Return a scoped field identity when available, otherwise its leaf key."""

    if not isinstance(input_metadata, dict):
        return None
    cube_alias = input_metadata.get("cube_alias")
    node_name = input_metadata.get("node_name")
    key = input_metadata.get("key")
    if cube_alias is not None and node_name is not None and key is not None:
        return cube_alias, node_name, key
    return key


def leaf_field_key(input_metadata: dict[str, Any] | None) -> str | None:
    """Return the locale-neutral field key from sanitized widget metadata."""

    if not isinstance(input_metadata, dict):
        return None
    key = input_metadata.get("key")
    return key if isinstance(key, str) and key else None
