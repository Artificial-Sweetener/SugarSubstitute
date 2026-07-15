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

"""Detect compute-capable Intel GPUs through Intel XPU Manager."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess

from substitute.infrastructure.comfy.hardware_generations import (
    infer_generation_hint,
)
from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
)

logger = logging.getLogger(__name__)


def read_intel_xpu_adapters() -> list[HardwareAdapterInfo]:
    """Return Intel GPUs proven available through `xpu-smi discovery`."""

    executable = shutil.which("xpu-smi")
    if executable is None:
        return []
    try:
        result = subprocess.run(
            [executable, "discovery", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.debug("Intel XPU CLI detection failed: %s", error, exc_info=True)
        return []
    if result.returncode != 0:
        logger.debug(
            "Intel XPU CLI detection exited with code %s: %s",
            result.returncode,
            result.stderr.strip(),
        )
        return []
    return _adapters_from_xpu_smi_output(result.stdout)


def _adapters_from_xpu_smi_output(output: str) -> list[HardwareAdapterInfo]:
    """Parse supported JSON or table output from Intel XPU Manager."""

    names: list[str] = []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        names.extend(
            match.group(1).strip()
            for match in re.finditer(r"Device Name\s*:\s*([^\r\n|]+)", output, re.I)
        )
    else:
        names.extend(_device_names_from_json(payload))
    return [
        HardwareAdapterInfo(
            name=name,
            accelerator_class=AcceleratorClass.INTEL_XPU,
            vendor_id="8086",
            generation_hint=infer_generation_hint(name) or "intel_xpu",
            is_discrete=True,
        )
        for name in dict.fromkeys(names)
        if name
    ]


def _device_names_from_json(value: object) -> list[str]:
    """Return device-name values from arbitrarily nested XPU Manager JSON."""

    if isinstance(value, list):
        return [name for item in value for name in _device_names_from_json(item)]
    if not isinstance(value, dict):
        return []
    names: list[str] = []
    for key, nested in value.items():
        normalized_key = str(key).lower().replace("_", " ").strip()
        if normalized_key == "device name" and isinstance(nested, str):
            names.append(nested.strip())
        else:
            names.extend(_device_names_from_json(nested))
    return names


__all__ = ["read_intel_xpu_adapters"]
