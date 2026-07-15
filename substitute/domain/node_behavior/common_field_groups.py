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

"""Infer class-agnostic editor field groups for common scalar controls."""

from __future__ import annotations

from typing import Final

COMMON_FIELD_GROUPS: Final[tuple[tuple[str, ...], ...]] = (
    ("sampler_name", "scheduler"),
    ("steps", "cfg"),
)


def infer_common_field_groups(
    input_keys: tuple[str, ...],
    occupied_fields: frozenset[str] = frozenset(),
) -> tuple[tuple[str, ...], ...]:
    """Return common field groups present in input keys and not already occupied."""

    available_fields = frozenset(input_keys)
    groups: list[tuple[str, ...]] = []
    for group in COMMON_FIELD_GROUPS:
        if not all(field_key in available_fields for field_key in group):
            continue
        if any(field_key in occupied_fields for field_key in group):
            continue
        groups.append(group)
    return tuple(groups)


__all__ = ["COMMON_FIELD_GROUPS", "infer_common_field_groups"]
