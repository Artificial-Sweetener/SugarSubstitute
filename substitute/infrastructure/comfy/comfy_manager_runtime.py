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

"""Bind Comfy-Manager subprocesses to the selected Comfy runtime."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path

from substitute.infrastructure.process.hidden_process_runner import run_command
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def selected_comfy_environment(
    *,
    workspace: Path,
    python_executable: Path,
    env: Mapping[str, str] | None,
) -> dict[str, str]:
    """Bind Manager work to one explicit Comfy workspace and Python runtime."""

    selected_env = dict(os.environ if env is None else env)
    selected_env.pop("CONDA_PREFIX", None)
    selected_env["COMFYUI_PATH"] = str(workspace.resolve())
    selected_env["COMFYUI_FOLDERS_BASE_PATH"] = str(workspace.resolve())
    executable_directory = python_executable.resolve().parent
    if executable_directory.name.casefold() in {"scripts", "bin"}:
        selected_env["VIRTUAL_ENV"] = str(executable_directory.parent)
    else:
        selected_env.pop("VIRTUAL_ENV", None)
    return selected_env


def python_module_available(
    *,
    module_name: str,
    workspace: Path,
    python_executable: Path,
    env: Mapping[str, str] | None,
) -> bool:
    """Return whether the selected Comfy Python exposes one module."""

    probe = run_command(
        [
            subprocess_path(python_executable),
            "-c",
            (
                "import importlib.util; "
                f"raise SystemExit(importlib.util.find_spec({module_name!r}) is None)"
            ),
        ],
        cwd=workspace,
        check=False,
        env=selected_comfy_environment(
            workspace=workspace,
            python_executable=python_executable,
            env=env,
        ),
    )
    return probe.returncode == 0


__all__ = ["python_module_available", "selected_comfy_environment"]
