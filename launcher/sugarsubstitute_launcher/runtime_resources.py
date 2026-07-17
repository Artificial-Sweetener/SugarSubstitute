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

"""Resolve launcher runtime resources without importing GUI dependencies."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from launcher.sugarsubstitute_launcher.platforms import (
    LauncherTarget,
    detect_launcher_target,
)


def launcher_uv_path(*, target: LauncherTarget | None = None) -> Path | None:
    """Return a bundled or developer uv executable for runtime provisioning."""

    resolved_target = target or detect_launcher_target()
    packaged_root = Path(getattr(sys, "_MEIPASS", ""))
    packaged_uv = packaged_root / "launcher_assets" / resolved_target.uv_executable_name
    if packaged_uv.is_file():
        return packaged_uv

    interpreter_uv = Path(sys.executable).parent / resolved_target.uv_executable_name
    if interpreter_uv.is_file():
        return interpreter_uv.resolve()

    source_uv = shutil.which("uv")
    if source_uv is not None:
        return Path(source_uv)
    return None
