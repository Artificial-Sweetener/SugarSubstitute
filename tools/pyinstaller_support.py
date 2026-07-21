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

"""Resolve external executables bundled by PyInstaller specifications."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import shutil
import sys


PyInstallerDataFile = tuple[str, str]


def build_launcher_data_files(
    *,
    repo_root: Path,
    app_icon_path: Path,
    uv_executable: str | None = None,
) -> tuple[PyInstallerDataFile, ...]:
    """Return the complete runtime data contract for every launcher bundle."""

    resolved_root = repo_root.resolve()
    resolved_uv = uv_executable or resolve_uv_executable()
    return (
        (str(app_icon_path.resolve()), "launcher_assets"),
        (resolved_uv, "launcher_assets"),
        (
            str(resolved_root / "launcher" / "sugarsubstitute_launcher" / "i18n"),
            "launcher/sugarsubstitute_launcher/i18n",
        ),
        (
            str(
                resolved_root / "sugarsubstitute_shared" / "localization" / "resources"
            ),
            "sugarsubstitute_shared/localization/resources",
        ),
    )


def resolve_uv_executable(
    *,
    python_executable: Path | None = None,
    path_lookup: Callable[[str], str | None] = shutil.which,
) -> str:
    """Locate uv beside the active Python interpreter or on the shell path."""

    executable_name = "uv.exe" if os.name == "nt" else "uv"
    interpreter = python_executable or Path(sys.executable)
    environment_uv = interpreter.parent / executable_name
    if environment_uv.is_file():
        return str(environment_uv.resolve())

    path_uv = path_lookup("uv")
    if path_uv is not None:
        return path_uv

    raise RuntimeError(
        "uv must be installed beside the active Python interpreter or on PATH "
        "before building the launcher."
    )


__all__ = [
    "PyInstallerDataFile",
    "build_launcher_data_files",
    "resolve_uv_executable",
]
