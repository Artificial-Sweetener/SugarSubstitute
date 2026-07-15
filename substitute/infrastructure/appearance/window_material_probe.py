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

"""Probe native shell-material capabilities independently of system colors."""

from __future__ import annotations

import platform
import sys

from substitute.application.appearance import WindowMaterialCapabilities


def probe_window_material_capabilities(
    platform_name: str | None = None,
    platform_version: str | None = None,
) -> WindowMaterialCapabilities:
    """Return Windows material support for the requested or current host."""

    current_platform = platform_name or sys.platform
    if current_platform != "win32":
        return WindowMaterialCapabilities()
    build = _windows_build_number(platform_version or platform.version())
    return WindowMaterialCapabilities(
        acrylic_available=build >= 10240,
        mica_alt_available=build >= 22000,
    )


def _windows_build_number(version: str) -> int:
    """Return a Windows build number parsed from the platform version text."""

    try:
        return int(version.strip().rsplit(".", maxsplit=1)[-1])
    except ValueError:
        return 0


__all__ = ["probe_window_material_capabilities"]
