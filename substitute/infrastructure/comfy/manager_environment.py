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

"""Build deterministic environments for ComfyUI Manager operations."""

from __future__ import annotations

from collections.abc import Mapping
from importlib import metadata
import os
from pathlib import Path
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def manager_environment(
    workspace: Path,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the common environment required by every Manager runtime."""

    environment = dict(os.environ if base is None else base)
    environment["COMFYUI_PATH"] = subprocess_path(workspace)
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("PYTHONIOENCODING", "utf-8:replace")
    environment.pop("CM_USE_PYGIT2", None)
    return environment


def manager_runtime_environment(
    workspace: Path,
    base: Mapping[str, str] | None = None,
    *,
    use_pygit2: bool,
) -> dict[str, str]:
    """Build a Manager environment with only validated optional capabilities."""

    environment = manager_environment(workspace, base)
    if use_pygit2:
        environment["CM_USE_PYGIT2"] = "1"
    else:
        environment.pop("CM_USE_PYGIT2", None)
    return environment


def integrated_manager_pygit2_requirement() -> str:
    """Return the app-tested pygit2 version for the ComfyUI environment."""

    return f"pygit2=={metadata.version('pygit2')}"


__all__ = [
    "integrated_manager_pygit2_requirement",
    "manager_environment",
    "manager_runtime_environment",
]
