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

"""Detect Windows graphics hardware for managed Comfy install policy."""

from __future__ import annotations

import logging
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

_WINDOWS_DETECTION_SCRIPT = """
$adapters = Get-CimInstance Win32_VideoController |
    Select-Object Name,PNPDeviceID,AdapterCompatibility |
    ConvertTo-Json -Compress
Write-Output $adapters
"""


def detect_windows_hardware() -> HardwareDetectionResult:
    """Detect Windows graphics adapters and choose the preferred accelerator class."""

    adapters = _read_windows_adapters()
    return HardwareDetectionResult(
        platform=ManagedPlatform.WINDOWS,
        adapters=tuple(adapters),
        tooling=HardwareToolingAvailability(
            nvidia_smi=shutil.which("nvidia-smi") is not None,
            amd_tooling=shutil.which("rocminfo") is not None
            or shutil.which("hipinfo") is not None,
            intel_xpu_tooling=shutil.which("xpu-smi") is not None,
        ),
    )


def _read_windows_adapters() -> list[HardwareAdapterInfo]:
    """Read Windows adapters from CIM and recover NVIDIA through vendor tooling."""

    adapters = _read_windows_cim_adapters()
    if not any(
        adapter.accelerator_class is AcceleratorClass.NVIDIA for adapter in adapters
    ):
        adapters.extend(read_nvidia_smi_adapters())
    if not any(
        adapter.accelerator_class is AcceleratorClass.INTEL_XPU for adapter in adapters
    ):
        adapters.extend(read_intel_xpu_adapters())
    return adapters


def _read_windows_cim_adapters() -> list[HardwareAdapterInfo]:
    """Read Windows graphics adapters from the native CIM provider."""

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _WINDOWS_DETECTION_SCRIPT],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.debug("Windows CIM GPU detection failed: %s", error, exc_info=True)
        return []
    if result.returncode != 0:
        logger.debug(
            "Windows CIM GPU detection exited with code %s: %s",
            result.returncode,
            result.stderr.strip(),
        )
        return []
    return _parse_windows_adapter_json(result.stdout.strip())


def _parse_windows_adapter_json(raw_json: str) -> list[HardwareAdapterInfo]:
    """Parse the Win32_VideoController JSON output into normalized adapter records."""

    import json

    if not raw_json:
        return []
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as error:
        logger.debug("Windows CIM GPU data was not valid JSON: %s", error)
        return []
    records = payload if isinstance(payload, list) else [payload]
    adapters: list[HardwareAdapterInfo] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("Name") or "").strip()
        pnp_device_id = str(record.get("PNPDeviceID") or "").strip()
        adapter_compatibility = str(record.get("AdapterCompatibility") or "").strip()
        accelerator = _accelerator_for_windows_adapter(
            name, pnp_device_id, adapter_compatibility
        )
        adapters.append(
            HardwareAdapterInfo(
                name=name or adapter_compatibility or "Unknown adapter",
                accelerator_class=accelerator,
                vendor_id=_extract_pci_id(pnp_device_id, prefix="VEN_"),
                device_id=_extract_pci_id(pnp_device_id, prefix="DEV_"),
                generation_hint=infer_generation_hint(name),
                is_discrete=_is_discrete(accelerator, name),
            )
        )
    return adapters


def _accelerator_for_windows_adapter(
    name: str,
    pnp_device_id: str,
    adapter_compatibility: str,
) -> AcceleratorClass:
    """Return the normalized accelerator class for one Windows adapter entry."""

    haystack = " ".join((name, pnp_device_id, adapter_compatibility)).lower()
    if "ven_10de" in haystack or "nvidia" in haystack:
        return AcceleratorClass.NVIDIA
    if "ven_1002" in haystack or "amd" in haystack or "radeon" in haystack:
        return AcceleratorClass.AMD
    intel_identity = " ".join((name, adapter_compatibility)).lower()
    if "ven_8086" in haystack and "arc" in intel_identity:
        return AcceleratorClass.INTEL_XPU
    return AcceleratorClass.CPU


def _extract_pci_id(pnp_device_id: str, *, prefix: str) -> str | None:
    """Extract one vendor or device identifier from a Windows PNP device id."""

    upper = pnp_device_id.upper()
    marker = upper.find(prefix)
    if marker == -1:
        return None
    start = marker + len(prefix)
    return upper[start : start + 4]


def _is_discrete(accelerator: AcceleratorClass, name: str) -> bool | None:
    """Infer whether one adapter should be treated as discrete for prioritization."""

    if accelerator in {AcceleratorClass.NVIDIA, AcceleratorClass.INTEL_XPU}:
        return True
    if accelerator is AcceleratorClass.AMD:
        lowered = name.lower()
        if "ryzen" in lowered or lowered.endswith("radeon(tm) graphics"):
            return False
        return " rx " in f" {lowered} "
    return False


__all__ = ["detect_windows_hardware"]
