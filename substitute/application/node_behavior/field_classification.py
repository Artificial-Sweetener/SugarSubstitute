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

"""Classify node fields before applying editor-time value policies."""

from __future__ import annotations

from enum import StrEnum
from typing import Mapping

from .list_value_resolver import is_choice_field_type


class NodeFieldKind(StrEnum):
    """Describe the application-owned behavior class for one node input field."""

    ASSET_FIELD = "asset_field"
    COMFY_ENUM_FIELD = "comfy_enum_field"
    LINKED_FIELD = "linked_field"
    PLAIN_FIELD = "plain_field"


_ASSET_FIELDS = frozenset(
    {
        ("LoadImage", "image"),
        ("LoadImageMask", "image"),
    }
)


def classify_node_field(
    *,
    class_type: str,
    field_key: str,
    node_data: Mapping[str, object],
    field_type: str | None,
) -> NodeFieldKind:
    """Return the authoritative behavior class for one node input field."""

    if _has_active_list_link(field_key=field_key, node_data=node_data):
        return NodeFieldKind.LINKED_FIELD
    if (class_type, field_key) in _ASSET_FIELDS:
        return NodeFieldKind.ASSET_FIELD
    if is_choice_field_type(field_type):
        return NodeFieldKind.COMFY_ENUM_FIELD
    return NodeFieldKind.PLAIN_FIELD


def _has_active_list_link(
    *,
    field_key: str,
    node_data: Mapping[str, object],
) -> bool:
    """Return whether a list field is governed by explicit workflow link metadata."""

    if field_key == "sampler_name":
        sampler_link = node_data.get("sampler_link")
        return isinstance(sampler_link, Mapping) and bool(sampler_link)
    if field_key == "scheduler":
        scheduler_link = node_data.get("scheduler_link")
        return isinstance(scheduler_link, Mapping) and bool(scheduler_link)
    return False


__all__ = ["NodeFieldKind", "classify_node_field"]
