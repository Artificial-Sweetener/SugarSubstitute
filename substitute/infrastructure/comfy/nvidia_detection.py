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

"""Detect NVIDIA adapters through the cross-platform vendor CLI."""

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
)

logger = logging.getLogger(__name__)


def read_nvidia_smi_adapters() -> list[HardwareAdapterInfo]:
    """Return NVIDIA adapters reported by a responsive `nvidia-smi` executable."""

    executable = shutil.which("nvidia-smi")
    if executable is None:
        return []
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.debug("NVIDIA CLI detection failed: %s", error, exc_info=True)
        return []
    if result.returncode != 0:
        logger.debug(
            "NVIDIA CLI detection exited with code %s: %s",
            result.returncode,
            result.stderr.strip(),
        )
        return []
    return [
        adapter
        for line in result.stdout.splitlines()
        if (adapter := _parse_nvidia_smi_line(line)) is not None
    ]


def _parse_nvidia_smi_line(line: str) -> HardwareAdapterInfo | None:
    """Parse one NVIDIA adapter-name row."""

    normalized_name = line.strip()
    if not normalized_name:
        return None
    return HardwareAdapterInfo(
        name=normalized_name,
        accelerator_class=AcceleratorClass.NVIDIA,
        vendor_id="10de",
        generation_hint=infer_generation_hint(normalized_name),
        is_discrete=True,
    )


__all__ = ["read_nvidia_smi_adapters"]
