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

"""Detect Apple Silicon hardware for managed Comfy installs on macOS."""

from __future__ import annotations

import platform

from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
    HardwareDetectionResult,
    HardwareToolingAvailability,
    ManagedPlatform,
)


class UnsupportedMacHardwareError(RuntimeError):
    """Report a Mac that cannot use the supported Apple Silicon MPS path."""


def detect_macos_hardware(
    *,
    machine: str | None = None,
    processor: str | None = None,
) -> HardwareDetectionResult:
    """Return MPS detection for Apple Silicon and reject Intel Macs."""

    machine_name = (machine or platform.machine()).strip().lower()
    processor_name = (processor or platform.processor()).strip().lower()
    if machine_name not in {"arm64", "aarch64"} and "arm" not in processor_name:
        raise UnsupportedMacHardwareError(
            "Managed Comfy on macOS requires Apple Silicon (M1 or newer)."
        )
    return HardwareDetectionResult(
        platform=ManagedPlatform.MACOS,
        adapters=(
            HardwareAdapterInfo(
                name="Apple Silicon",
                accelerator_class=AcceleratorClass.APPLE_MPS,
                generation_hint="apple_silicon",
                is_discrete=False,
            ),
        ),
        tooling=HardwareToolingAvailability(
            nvidia_smi=False,
            amd_tooling=False,
            intel_xpu_tooling=False,
        ),
    )


__all__ = ["UnsupportedMacHardwareError", "detect_macos_hardware"]
