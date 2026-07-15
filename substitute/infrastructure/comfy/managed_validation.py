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

"""Validate canonical managed-local Comfy workspace layout artifacts."""

from __future__ import annotations

import os
from pathlib import Path


def workspace_venv_dir(workspace: Path) -> Path:
    """Return the managed workspace virtual-environment directory."""

    return workspace / ".venv"


def workspace_python_dir(workspace: Path) -> Path:
    """Return the managed workspace local Python bootstrap directory."""

    return workspace / ".python312"


def workspace_python_path(workspace: Path) -> Path:
    """Return the managed workspace venv Python executable path."""

    if os.name == "nt":
        return workspace_venv_dir(workspace) / "Scripts" / "python.exe"
    return workspace_venv_dir(workspace) / "bin" / "python"


def workspace_main_path(workspace: Path) -> Path:
    """Return the canonical managed workspace Comfy entrypoint path."""

    return workspace / "main.py"


def workspace_nested_main_path(workspace: Path) -> Path:
    """Return the legacy nested Comfy entrypoint path used by earlier installs."""

    return workspace / "ComfyUI" / "main.py"


def is_workspace_installed(workspace: Path) -> bool:
    """Return whether the managed workspace contains installed runtime artifacts."""

    return (
        workspace_python_path(workspace).exists()
        and workspace_main_path(workspace).exists()
    )


def is_workspace_launchable(workspace: Path) -> bool:
    """Return whether the managed workspace can be launched immediately."""

    return (
        workspace_python_path(workspace).exists()
        and workspace_main_path(workspace).exists()
    )
