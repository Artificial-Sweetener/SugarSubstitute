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

"""Order visible node-card fields into behavior-defined groups."""

from __future__ import annotations


def group_visible_field_keys(
    *,
    input_keys: list[str],
    field_groups: tuple[tuple[str, ...], ...],
    skip_keys: set[str],
) -> list[list[str]]:
    """Group visible field keys in their original discovery order."""

    keys = [key for key in input_keys if key not in skip_keys]
    if not field_groups:
        return [[key] for key in keys]

    used: set[str] = set()
    ordered_groups: list[list[str]] = []
    for key in keys:
        if key in used:
            continue
        matching_group = next(
            (group for group in field_groups if key in group),
            None,
        )
        if matching_group is None:
            ordered_groups.append([key])
            used.add(key)
            continue
        visible_group = [
            group_key
            for group_key in matching_group
            if group_key in keys and group_key not in used
        ]
        if visible_group:
            ordered_groups.append(visible_group)
            used.update(visible_group)
    return ordered_groups


__all__ = ["group_visible_field_keys"]
