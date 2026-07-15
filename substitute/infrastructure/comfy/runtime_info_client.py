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

"""Fetch Comfy runtime facts from the shared `/system_stats` route."""

from __future__ import annotations

import requests

from substitute.domain.comfy_runtime import ComfyRuntimeInfo
from substitute.domain.onboarding import ComfyEndpoint
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.runtime_info_client")


def fetch_comfy_runtime_info(
    endpoint: ComfyEndpoint,
    *,
    timeout_seconds: float = 3.0,
) -> ComfyRuntimeInfo | None:
    """Return Comfy runtime information or None when the target is unavailable."""

    try:
        response = requests.get(endpoint.system_stats_url(), timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except Exception as error:
        log_warning(
            _LOGGER,
            "Failed to fetch Comfy system stats",
            endpoint=endpoint.system_stats_url(),
            error=repr(error),
        )
        return None

    if not isinstance(payload, dict):
        return None
    system = payload.get("system")
    if not isinstance(system, dict):
        system = {}
    return ComfyRuntimeInfo(
        comfy_version=_optional_string(system.get("comfyui_version")),
        os_name=_optional_string(system.get("os")),
        python_version=_optional_string(system.get("python_version")),
        embedded_python=_optional_string(system.get("embedded_python")),
        pytorch_version=_optional_string(system.get("pytorch_version")),
        devices=_device_summaries(payload.get("devices")),
        launch_args=_string_tuple(system.get("argv")),
    )


def _device_summaries(value: object) -> tuple[str, ...]:
    """Return readable device summaries from a list-like devices payload."""

    if not isinstance(value, list):
        return ()
    devices: list[str] = []
    for device in value:
        if not isinstance(device, dict):
            continue
        name = _optional_string(device.get("name")) or "unknown"
        device_type = _optional_string(device.get("type")) or "unknown"
        index = device.get("index")
        memory = _memory_summary(device)
        prefix = f"{name} ({device_type}"
        if index is not None:
            prefix += f" #{index}"
        prefix += ")"
        devices.append(f"{prefix}{memory}")
    return tuple(devices)


def _memory_summary(device: dict[object, object]) -> str:
    """Return a compact VRAM summary for one Comfy device entry."""

    parts: list[str] = []
    for label, key in (
        ("VRAM", "vram_total"),
        ("free", "vram_free"),
        ("torch", "torch_vram_total"),
        ("torch free", "torch_vram_free"),
    ):
        value = device.get(key)
        if isinstance(value, int | float):
            parts.append(f"{label}: {value}")
    return f" [{', '.join(parts)}]" if parts else ""


def _string_tuple(value: object) -> tuple[str, ...]:
    """Return strings from a list-like value."""

    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return ()


def _optional_string(value: object) -> str:
    """Return a non-empty string representation or an empty string."""

    if isinstance(value, str) and value:
        return value
    if isinstance(value, bool):
        return str(value)
    return ""


__all__ = ["fetch_comfy_runtime_info"]
