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

"""Format Settings cache byte counts for compact display."""

from __future__ import annotations

_BYTE_UNITS = ("KB", "MB", "GB", "TB")
_UNIT_SCALE = 1024.0


def format_cache_size(byte_count: int) -> str:
    """Return a compact cache size using bytes through terabytes."""

    normalized_count = max(0, byte_count)
    if normalized_count < 1024:
        unit = "byte" if normalized_count == 1 else "bytes"
        return f"{normalized_count} {unit}"
    value = float(normalized_count)
    unit = _BYTE_UNITS[0]
    for unit in _BYTE_UNITS:
        value /= _UNIT_SCALE
        if value < _UNIT_SCALE or unit == _BYTE_UNITS[-1]:
            return f"{_format_scaled_value(value)} {unit}"
    return f"{_format_scaled_value(value)} {unit}"


def _format_scaled_value(value: float) -> str:
    """Return a scaled byte value with fixed point precision."""

    return f"{value:.2f}"


__all__ = ["format_cache_size"]
