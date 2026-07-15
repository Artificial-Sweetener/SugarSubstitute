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

"""Detect Linux graphics hardware for managed Comfy install policy."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess

from substitute.infrastructure.comfy.hardware_generations import (
    infer_generation_hint,
)
from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
    HardwareDetectionResult,
    HardwareToolingAvailability,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.intel_xpu_detection import (
    read_intel_xpu_adapters,
)
from substitute.infrastructure.comfy.nvidia_detection import (
    read_nvidia_smi_adapters,
)

logger = logging.getLogger(__name__)


def detect_linux_hardware() -> HardwareDetectionResult:
    """Detect Linux graphics adapters and choose the preferred accelerator class."""

    adapters = _read_linux_adapters()
    return HardwareDetectionResult(
        platform=ManagedPlatform.LINUX,
        adapters=tuple(adapters),
        tooling=HardwareToolingAvailability(
            nvidia_smi=shutil.which("nvidia-smi") is not None,
            amd_tooling=shutil.which("rocminfo") is not None
            or shutil.which("hipinfo") is not None,
            intel_xpu_tooling=shutil.which("xpu-smi") is not None,
        ),
    )


def _read_linux_adapters() -> list[HardwareAdapterInfo]:
    """Read Linux graphics adapters from PCI or DRM sources."""

    adapters = _parse_lspci_output() or _parse_sysfs_drm()
    if not any(
        adapter.accelerator_class is AcceleratorClass.NVIDIA for adapter in adapters
    ):
        adapters.extend(_parse_nvidia_smi_output())
    if not any(
        adapter.accelerator_class is AcceleratorClass.INTEL_XPU for adapter in adapters
    ):
        adapters.extend(read_intel_xpu_adapters())
    return adapters


def _parse_lspci_output() -> list[HardwareAdapterInfo]:
    """Parse `lspci -nn` output into normalized adapter records."""

    try:
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.debug("Linux PCI GPU detection failed: %s", error, exc_info=True)
        return []
    if result.returncode != 0:
        logger.debug(
            "Linux PCI GPU detection exited with code %s: %s",
            result.returncode,
            result.stderr.strip(),
        )
        return []
    adapters: list[HardwareAdapterInfo] = []
    for line in result.stdout.splitlines():
        lowered = line.lower()
        if (
            "vga compatible controller" not in lowered
            and "3d controller" not in lowered
        ):
            continue
        accelerator = _accelerator_for_linux_line(lowered)
        vendor_id, device_id = _extract_linux_ids(line)
        adapters.append(
            HardwareAdapterInfo(
                name=line.split(":", 2)[-1].strip(),
                accelerator_class=accelerator,
                vendor_id=vendor_id,
                device_id=device_id,
                generation_hint=infer_generation_hint(line),
                is_discrete=accelerator is not AcceleratorClass.CPU,
            )
        )
    return adapters


def _parse_sysfs_drm() -> list[HardwareAdapterInfo]:
    """Parse `/sys/class/drm` when PCI tooling is unavailable."""

    drm_root = Path("/sys/class/drm")
    if not drm_root.exists():
        return []
    adapters: list[HardwareAdapterInfo] = []
    for device_path in drm_root.glob("card*/device"):
        vendor_path = device_path / "vendor"
        device_id_path = device_path / "device"
        if not vendor_path.exists():
            continue
        try:
            vendor_id = (
                vendor_path.read_text(encoding="utf-8").strip().removeprefix("0x")
            )
            device_id = (
                device_id_path.read_text(encoding="utf-8").strip().removeprefix("0x")
                if device_id_path.exists()
                else None
            )
        except OSError as error:
            logger.debug(
                "Linux DRM adapter metadata could not be read from %s: %s",
                device_path,
                error,
            )
            continue
        accelerator = _accelerator_for_vendor_id(vendor_id)
        adapters.append(
            HardwareAdapterInfo(
                name=f"DRM adapter {device_path.parent.name}",
                accelerator_class=accelerator,
                vendor_id=vendor_id,
                device_id=device_id,
                generation_hint=None,
                is_discrete=accelerator is not AcceleratorClass.CPU,
            )
        )
    return adapters


def _parse_nvidia_smi_output() -> list[HardwareAdapterInfo]:
    """Detect NVIDIA adapters when virtualized Linux hides PCI and DRM devices."""

    return read_nvidia_smi_adapters()


def _accelerator_for_linux_line(lowered: str) -> AcceleratorClass:
    """Return the normalized accelerator class for one Linux adapter line."""

    if "nvidia" in lowered or "[10de:" in lowered:
        return AcceleratorClass.NVIDIA
    if (
        "advanced micro devices" in lowered
        or "amd/ati" in lowered
        or "[1002:" in lowered
    ):
        return AcceleratorClass.AMD
    if "intel corporation arc" in lowered or (
        "intel corporation" in lowered and "arc" in lowered
    ):
        return AcceleratorClass.INTEL_XPU
    return AcceleratorClass.CPU


def _accelerator_for_vendor_id(vendor_id: str | None) -> AcceleratorClass:
    """Return the normalized accelerator class for one PCI vendor id."""

    normalized = (vendor_id or "").lower()
    if normalized == "10de":
        return AcceleratorClass.NVIDIA
    if normalized == "1002":
        return AcceleratorClass.AMD
    if normalized == "8086":
        return AcceleratorClass.CPU
    return AcceleratorClass.CPU


def _extract_linux_ids(line: str) -> tuple[str | None, str | None]:
    """Extract one vendor and device identifier pair from one PCI line."""

    marker = line.rfind("[")
    if marker == -1 or ":" not in line[marker:]:
        return None, None
    bracket = line[marker + 1 :].split("]", 1)[0]
    vendor_id, _, device_id = bracket.partition(":")
    return vendor_id.lower() or None, device_id.lower() or None


__all__ = ["detect_linux_hardware"]
