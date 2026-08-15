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

"""Build managed ComfyUI process commands from active runtime policy."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.domain.onboarding import ComfyEndpoint
from sugarsubstitute_shared.windows_long_paths import (
    exceeds_windows_legacy_path_limit,
    subprocess_path,
)

_LONG_WORKSPACE_BOOTSTRAP = (
    "import os, runpy, sys; "
    "root = sys.argv.pop(1); script = sys.argv.pop(1); "
    "os.chdir(root); sys.argv[0] = script; "
    "runpy.run_path(script, run_name='__main__')"
)


def build_managed_launch_command(
    *,
    venv_python: Path,
    endpoint: ComfyEndpoint,
    workspace: Path,
    manager_runtime: ComfyManagerRuntime,
    force_cpu_mode: bool,
) -> tuple[str, ...]:
    """Build the authoritative managed ComfyUI launch command."""

    runtime_arguments = ("--cpu",) if force_cpu_mode else ()
    arguments = (
        "--listen",
        str(endpoint.host),
        "--port",
        str(endpoint.port),
        *runtime_arguments,
        *manager_runtime.launch_arguments,
    )
    if exceeds_windows_legacy_path_limit(workspace):
        return (
            subprocess_path(venv_python),
            "-c",
            _LONG_WORKSPACE_BOOTSTRAP,
            subprocess_path(workspace),
            subprocess_path(workspace / "main.py"),
            *arguments,
        )
    return (
        subprocess_path(venv_python),
        subprocess_path(workspace / "main.py"),
        *arguments,
    )


__all__ = ["build_managed_launch_command"]
