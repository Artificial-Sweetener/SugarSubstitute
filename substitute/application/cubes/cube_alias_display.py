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

"""Define Qt-free display policies for cube aliases."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CubeAliasDisplayParts:
    """Store a cube alias split into optional prefix and display body."""

    prefix: str
    body: str


def split_cube_alias_prefix(alias: str) -> CubeAliasDisplayParts:
    """Split a leading non-empty slash prefix from a cube alias."""

    stripped = alias.strip()
    slash_index = stripped.find("/")
    if slash_index <= 0 or slash_index >= len(stripped) - 1:
        return CubeAliasDisplayParts(prefix="", body=stripped)

    prefix_body = stripped[:slash_index].strip()
    body = stripped[slash_index + 1 :].strip()
    if not prefix_body or not body:
        return CubeAliasDisplayParts(prefix="", body=stripped)

    return CubeAliasDisplayParts(
        prefix=stripped[: slash_index + 1],
        body=body,
    )


def cube_alias_body(alias: str) -> str:
    """Return the output-display alias body after an optional prefix."""

    return split_cube_alias_prefix(alias).body


__all__ = [
    "CubeAliasDisplayParts",
    "cube_alias_body",
    "split_cube_alias_prefix",
]
