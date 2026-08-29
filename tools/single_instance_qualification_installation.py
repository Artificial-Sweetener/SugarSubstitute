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

"""Prepare disposable installed layouts for single-instance qualification."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from launcher.sugarsubstitute_launcher.config import (
    LauncherConfig,
    UpdateCheckConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


def prepare_qualification_installation(
    *,
    repository_root: Path,
    launcher_bundle: Path,
    install_root: Path,
) -> InstallLayout:
    """Create a disposable installed layout using real launcher and app owners."""

    if not (launcher_bundle / "SugarSubstitute.exe").is_file():
        raise FileNotFoundError(f"Packaged launcher not found: {launcher_bundle}")
    shutil.copytree(launcher_bundle, install_root)
    layout = InstallLayout.from_root(install_root)
    layout.app_dir.mkdir()
    for package_name in ("sugarsubstitute_shared", "substitute"):
        shutil.copytree(
            repository_root / package_name,
            layout.app_dir / package_name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    shutil.copy2(
        repository_root / "tools" / "single_instance_qualification_app.py",
        layout.app_entrypoint,
    )
    layout.runtime_dir.mkdir()
    _create_directory_link(
        repository_root / ".venv",
        layout.runtime_dir / ".venv",
    )
    LauncherConfig.from_layout(
        layout=layout,
        update_check=UpdateCheckConfig(enabled=False),
        release_source=None,
    ).save(layout.config_path)
    return layout


def _create_directory_link(source: Path, destination: Path) -> None:
    """Create a disposable runtime link without administrator access."""

    try:
        os.symlink(source, destination, target_is_directory=True)
        return
    except OSError as error:
        if getattr(error, "winerror", None) != 1314:
            raise
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(destination), str(source)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10.0,
    )
    if result.returncode != 0:
        raise OSError(
            "Could not create the disposable runtime junction: "
            f"{result.stdout}{result.stderr}"
        )


__all__ = ["prepare_qualification_installation"]
