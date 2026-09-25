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

"""Normalize loosely typed libmpv property observations."""

from __future__ import annotations


def optional_nonnegative_float(value: object) -> float | None:
    """Return one optional nonnegative numeric observation."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if converted >= 0.0 else None


def optional_positive_integer(value: object) -> int | None:
    """Return one optional positive integer observation."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = int(value)
    return converted if converted > 0 else None


def optional_string(value: object) -> str | None:
    """Return one non-empty native property string."""

    return value if isinstance(value, str) and value else None


__all__ = [
    "optional_nonnegative_float",
    "optional_positive_integer",
    "optional_string",
]
