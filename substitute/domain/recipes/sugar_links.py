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

"""Encode and inspect Sugar recipe link references."""

from __future__ import annotations

from substitute.domain.common import JsonValue
from substitute.domain.recipes.sugar_path_codec import SugarPathCodec

_PATH_CODEC = SugarPathCodec()


def linkable_prompt_fields() -> tuple[tuple[str, str], ...]:
    """Return node/input pairs that support prompt links."""

    return (
        ("positive_prompt", "prompt_template"),
        ("negative_prompt", "prompt_template"),
    )


def prompt_field_reference(
    from_cube: str | None,
    node_name: str,
    input_key: str,
) -> str | None:
    """Return a Sugar prompt-field reference for a valid source cube."""

    if not from_cube or from_cube == "Independent (not linked)":
        return None
    return ".".join(
        _PATH_CODEC.encode_segment(segment)
        for segment in (from_cube, node_name, input_key)
    )


def prompt_link_source_alias(
    node_name: str,
    input_key: str,
    value: JsonValue,
) -> str | None:
    """Return the source alias represented by one prompt-link value."""

    if (
        node_name not in {"positive_prompt", "negative_prompt"}
        or input_key != "prompt_template"
        or not isinstance(value, str)
    ):
        return None
    parts = _PATH_CODEC.split(value)
    return parts[0] if len(parts) == 3 else None


def node_reference(from_cube: str | None, from_node: str | None) -> str | None:
    """Return a Sugar whole-node reference for a valid source node."""

    if not from_cube or not from_node:
        return None
    return ".".join(
        _PATH_CODEC.encode_segment(segment) for segment in (from_cube, from_node)
    )


__all__ = [
    "linkable_prompt_fields",
    "node_reference",
    "prompt_field_reference",
    "prompt_link_source_alias",
]
