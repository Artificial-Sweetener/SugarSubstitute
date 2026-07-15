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

"""Resolve the Python interpreter policy for managed Comfy workspace creation."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import sys
from collections.abc import Sequence


@dataclass(frozen=True)
class PythonRuntimeSelection:
    """Describe the interpreter Substitute selected for the managed workspace."""

    executable: str
    selected_version: str
    used_fallback: bool


def resolve_python_runtime(
    *,
    preferred_version: str = "3.13",
    fallback_version: str = "3.12",
) -> PythonRuntimeSelection:
    """Resolve the preferred or fallback Python interpreter for the managed install."""

    for version, used_fallback in (
        (preferred_version, False),
        (fallback_version, True),
    ):
        executable = _resolve_python_executable(version)
        if executable is not None:
            return PythonRuntimeSelection(
                executable=executable,
                selected_version=version,
                used_fallback=used_fallback,
            )
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    return PythonRuntimeSelection(
        executable=sys.executable,
        selected_version=current_version,
        used_fallback=current_version != preferred_version,
    )


def _resolve_python_executable(version: str) -> str | None:
    """Resolve one installed Python executable for the requested major.minor version."""

    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if current_version == version:
        return sys.executable
    if os.name == "nt":
        launcher = _resolve_windows_py_launcher(version)
        if launcher is not None:
            return launcher
    return _resolve_posix_python(version)


def _resolve_windows_py_launcher(version: str) -> str | None:
    """Resolve one Windows Python launcher target for the requested version."""

    return _probe_python_executable(
        ["py", f"-{version}", "-c", "import sys; print(sys.executable)"]
    )


def _resolve_posix_python(version: str) -> str | None:
    """Resolve one POSIX Python executable path for the requested version."""

    command = f"python{version}"
    return _probe_python_executable(
        [command, "-c", "import sys; print(sys.executable)"]
    )


def _probe_python_executable(command: Sequence[str]) -> str | None:
    """Return a probed interpreter path or treat failed probes as unavailable."""

    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    executable = result.stdout.strip()
    return executable or None


__all__ = ["PythonRuntimeSelection", "resolve_python_runtime"]
