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

from substitute.application.workflows.input_asset_field_policy import (
    InputAssetFieldPolicy,
)

_INPUT_ASSET_FIELD_POLICY = InputAssetFieldPolicy()


def is_runtime_asset_picker_field(
    *,
    class_type: str,
    input_name: str,
    field_spec: object,
) -> bool:
    """Return whether staging, rather than picker fallback, owns the value."""

    return _INPUT_ASSET_FIELD_POLICY.is_asset_field(
        class_type=class_type,
        field_key=input_name,
        field_info=field_spec,
    )


__all__ = ["is_runtime_asset_picker_field"]
