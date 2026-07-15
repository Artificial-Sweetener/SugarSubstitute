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

"""Define normalized hardware-detection models for managed Comfy installs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ManagedPlatform(str, Enum):
    """Identify the supported managed-install operating-system families."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class AcceleratorClass(str, Enum):
    """Identify the accelerator class relevant to managed torch selection."""

    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL_XPU = "intel_xpu"
    APPLE_MPS = "apple_mps"
    CPU = "cpu"


@dataclass(frozen=True)
class HardwareAdapterInfo:
    """Describe one detected graphics adapter in normalized install-policy form."""

    name: str
    accelerator_class: AcceleratorClass
    vendor_id: str | None = None
    device_id: str | None = None
    generation_hint: str | None = None
    is_discrete: bool | None = None


@dataclass(frozen=True)
class HardwareToolingAvailability:
    """Describe optional vendor tooling that may improve detection confidence."""

    nvidia_smi: bool
    amd_tooling: bool
    intel_xpu_tooling: bool


@dataclass(frozen=True)
class HardwareDetectionResult:
    """Capture the normalized hardware selection inputs for managed install policy."""

    platform: ManagedPlatform
    adapters: tuple[HardwareAdapterInfo, ...]
    tooling: HardwareToolingAvailability

    @property
    def selected_adapter(self) -> HardwareAdapterInfo | None:
        """Return the highest-priority compatible adapter discovered on the host."""

        ranking = {
            AcceleratorClass.NVIDIA: 4,
            AcceleratorClass.AMD: 3,
            AcceleratorClass.INTEL_XPU: 2,
            AcceleratorClass.CPU: 1,
            AcceleratorClass.APPLE_MPS: 5,
        }
        return max(
            self.adapters,
            key=lambda adapter: (
                ranking[adapter.accelerator_class],
                bool(adapter.is_discrete),
            ),
            default=None,
        )

    @property
    def preferred_accelerator(self) -> AcceleratorClass:
        """Return the accelerator class owned by the selected adapter."""

        selected = self.selected_adapter
        return (
            selected.accelerator_class if selected is not None else AcceleratorClass.CPU
        )


__all__ = [
    "AcceleratorClass",
    "HardwareAdapterInfo",
    "HardwareDetectionResult",
    "HardwareToolingAvailability",
    "ManagedPlatform",
]
