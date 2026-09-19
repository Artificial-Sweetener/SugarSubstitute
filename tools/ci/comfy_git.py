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

"""Own bounded Git access for Comfy source qualification."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


def run_git(
    workspace: Path,
    *arguments: str,
    timeout_seconds: float = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Opt each hidden Git operation into long descendant paths without global changes."""
    return subprocess.run(
        ["git", "-c", "core.longpaths=true", *arguments],
        cwd=workspace,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        timeout=timeout_seconds,
    )


def git_output(workspace: Path, *arguments: str) -> str:
    """Read exact source identity through the same Git path policy as writes."""
    return run_git(workspace, *arguments).stdout.strip()
