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

"""Normalize scalar fields from Comfy websocket payloads."""

from __future__ import annotations


def string_or_none(value: object) -> str | None:
    """Return string values while preserving missing optional fields."""

    if isinstance(value, (str, int)):
        return str(value)
    return None


def strict_string_or_none(value: object) -> str | None:
    """Return non-empty string values without coercing malformed payload fields."""

    if isinstance(value, str) and value:
        return value
    return None


def optional_float(value: object) -> float | None:
    """Return numeric payload fields as floats when present."""

    if isinstance(value, (int, float)):
        return float(value)
    return None


def positive_int_or_zero(value: object) -> int:
    """Return positive integer-like values or zero for incomplete image doubles."""

    if isinstance(value, int) and value > 0:
        return value
    return 0


def positive_int_or_none(value: object) -> int | None:
    """Return positive integer values from backend artifact metadata."""

    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def list_index_rejection_reason(value: object) -> str | None:
    """Return why a live final list index is unusable, if it is unusable."""

    if isinstance(value, bool):
        return "non_integer_list_index"
    if isinstance(value, int):
        if value < 0:
            return "negative_list_index"
        return None
    if value is None:
        return "missing_list_index"
    return "non_integer_list_index"
