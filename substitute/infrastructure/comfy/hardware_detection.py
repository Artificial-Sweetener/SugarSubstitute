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

"""Detect managed Comfy install hardware on supported operating systems."""

from __future__ import annotations

import sys

from substitute.infrastructure.comfy.hardware_linux import detect_linux_hardware
from substitute.infrastructure.comfy.hardware_macos import detect_macos_hardware
from substitute.infrastructure.comfy.hardware_models import (
    HardwareDetectionResult,
    HardwareToolingAvailability,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.hardware_windows import detect_windows_hardware


def detect_hardware() -> HardwareDetectionResult:
    """Return normalized hardware detection for the current platform."""

    if sys.platform.startswith("win"):
        return detect_windows_hardware()
    if sys.platform.startswith("linux"):
        return detect_linux_hardware()
    if sys.platform == "darwin":
        return detect_macos_hardware()
    return HardwareDetectionResult(
        platform=ManagedPlatform.WINDOWS
        if sys.platform.startswith("cygwin")
        else ManagedPlatform.LINUX,
        adapters=(),
        tooling=HardwareToolingAvailability(
            nvidia_smi=False,
            amd_tooling=False,
            intel_xpu_tooling=False,
        ),
    )


__all__ = ["detect_hardware"]
