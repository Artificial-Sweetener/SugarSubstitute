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

"""Project editable Cube state into one complete canonical document."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import cast

from substitute.domain.common import JsonObject, JsonValue


def project_editable_cube_document(
    *,
    cube_id: str,
    version: str,
    buffer: Mapping[str, object],
    canonical_metadata: Mapping[str, object] | None,
) -> JsonObject:
    """Combine editable implementation state with immutable Cube metadata."""

    metadata = canonical_metadata or {}
    document: JsonObject = {
        "cube_id": cube_id,
        "version": version,
        "description": str(metadata.get("description", "")),
        "metadata": deepcopy(cast(JsonObject, metadata.get("metadata", {}))),
        "implementation": {
            "nodes": deepcopy(cast(JsonObject, buffer.get("nodes", {}))),
            "inputs": deepcopy(cast(JsonObject, buffer.get("inputs", {}))),
            "outputs": deepcopy(cast(JsonObject, buffer.get("outputs", {}))),
            "layout": deepcopy(cast(JsonObject, buffer.get("layout", {}))),
            "definitions": deepcopy(cast(JsonObject, buffer.get("definitions", {}))),
            "subgraphs": deepcopy(cast(list[JsonValue], buffer.get("subgraphs", []))),
        },
        "surface": deepcopy(
            cast(JsonObject, buffer.get("surface", metadata.get("surface", {})))
        ),
        "flavors": deepcopy(
            cast(JsonObject, buffer.get("flavors", metadata.get("flavors", {})))
        ),
    }
    return document


__all__ = [
    "project_editable_cube_document",
]
