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

"""Define the normalized managed install targets used by backend policy selection."""

from __future__ import annotations

from enum import Enum


class ManagedInstallTarget(str, Enum):
    """Identify one concrete managed install target across platform and backend."""

    WINDOWS_NVIDIA = "windows_nvidia"
    WINDOWS_AMD = "windows_amd"
    WINDOWS_INTEL_XPU = "windows_intel_xpu"
    WINDOWS_CPU = "windows_cpu"
    LINUX_NVIDIA = "linux_nvidia"
    LINUX_AMD = "linux_amd"
    LINUX_INTEL_XPU = "linux_intel_xpu"
    LINUX_CPU = "linux_cpu"
    MACOS_APPLE_SILICON = "macos_apple_silicon"


__all__ = ["ManagedInstallTarget"]
