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

"""Compare release versions shared by launcher update participants."""

from __future__ import annotations


def compare_release_versions(left: str, right: str) -> int:
    """Compare dotted numeric release versions."""

    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    width = max(len(left_parts), len(right_parts))
    padded_left = (*left_parts, *([0] * (width - len(left_parts))))
    padded_right = (*right_parts, *([0] * (width - len(right_parts))))
    return (padded_left > padded_right) - (padded_left < padded_right)


def _version_parts(version: str) -> tuple[int, ...]:
    """Parse one release version and reject nonnumeric components."""

    normalized = version.removeprefix("v").strip()
    if not normalized:
        raise ValueError("Release version must not be empty.")
    parts = normalized.split(".")
    if any(not part.isdigit() for part in parts):
        raise ValueError(f"Release version must be numeric: {version}")
    return tuple(int(part) for part in parts)


__all__ = ["compare_release_versions"]
