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

from sugarsubstitute_shared.launcher_update.versions import validate_release_version


def safe_launcher_version(version: str) -> str:
    """Return a filesystem-safe launcher release version identifier."""

    try:
        validate_release_version(version)
    except ValueError as error:
        raise ValueError(f"Unsafe launcher version: {version!r}") from error
    return version


__all__ = ["safe_launcher_version"]
