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

"""Resolve launcher process paths without importing GUI owners."""

from __future__ import annotations

from pathlib import Path
import sys


def frozen_support_path() -> Path | None:
    """Return PyInstaller's authoritative bundle support directory."""

    raw_path = getattr(sys, "_MEIPASS", None)
    if not bool(getattr(sys, "frozen", False)) or not isinstance(raw_path, str):
        return None
    return Path(raw_path)


def frozen_invocation_path() -> Path | None:
    """Return the packaged launcher path exactly as the OS invoked it."""

    if not bool(getattr(sys, "frozen", False)) or not sys.argv or not sys.argv[0]:
        return None
    return Path(sys.argv[0])


def native_frozen_executable_path() -> Path | None:
    """Return Linux's kernel-owned path to the current packaged executable."""

    if not bool(getattr(sys, "frozen", False)) or not sys.platform.startswith("linux"):
        return None
    try:
        return Path("/proc/self/exe").resolve(strict=True)
    except OSError:
        return None


__all__ = [
    "frozen_invocation_path",
    "frozen_support_path",
    "native_frozen_executable_path",
]
