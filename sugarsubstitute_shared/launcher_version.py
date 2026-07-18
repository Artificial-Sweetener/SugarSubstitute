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

"""Validate launcher release versions without importing runtime dependencies."""

from __future__ import annotations


def safe_launcher_version(version: str) -> str:
    """Return a filesystem-safe launcher release version identifier."""

    if not version or any(character not in "0123456789.-" for character in version):
        raise ValueError(f"Unsafe launcher version: {version!r}")
    return version


__all__ = ["safe_launcher_version"]
