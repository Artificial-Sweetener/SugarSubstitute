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

"""Resolve source ranges from production prompt-projection fragments."""

from __future__ import annotations

from collections.abc import Sequence


def fragment_source_range(source_positions: object) -> tuple[int, int]:
    """Return a half-open source range covered by one projection fragment."""

    if not isinstance(source_positions, Sequence):
        return (0, 0)
    positions = tuple(
        position
        for position in source_positions
        if isinstance(position, int) and position >= 0
    )
    if not positions:
        return (0, 0)
    return min(positions), max(positions) + 1
