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

"""Resolve Python runtimes owned by Comfy workspaces."""

from __future__ import annotations

import os
from pathlib import Path

from substitute.infrastructure.comfy.managed_validation import workspace_python_path


def resolve_workspace_python(workspace: Path) -> Path:
    """Resolve the Python executable owned by a Comfy workspace."""

    candidates = [
        workspace_python_path(workspace),
        workspace / "venv" / "Scripts" / "python.exe",
        workspace / "python_embeded" / "python.exe",
        workspace / "python_embedded" / "python.exe",
    ]
    if os.name != "nt":
        candidates.extend(
            [
                workspace / "venv" / "bin" / "python",
                workspace / ".venv" / "bin" / "python",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Could not find a Python runtime inside the selected ComfyUI workspace."
    )


__all__ = ["resolve_workspace_python"]
