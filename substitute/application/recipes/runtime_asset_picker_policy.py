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

"""Identify picker fields whose execution values belong to asset staging."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

_LEGACY_RUNTIME_ASSET_PICKER_FIELDS = frozenset(
    {
        ("LoadImage", "image"),
        ("LoadImageMask", "image"),
    }
)


def is_runtime_asset_picker_field(
    *,
    class_type: str,
    input_name: str,
    field_spec: object,
) -> bool:
    """Return whether staging, rather than picker fallback, owns the value."""

    if (class_type, input_name) in _LEGACY_RUNTIME_ASSET_PICKER_FIELDS:
        return True
    if not isinstance(field_spec, Sequence) or len(field_spec) < 2:
        return False
    metadata = field_spec[1]
    return isinstance(metadata, Mapping) and metadata.get("image_upload") is True


__all__ = ["is_runtime_asset_picker_field"]
