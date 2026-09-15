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

"""Verify real-process qualification reproduces the released Windows layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.single_instance_qualification_installation import (
    prepare_launcher_surface_qualification_installation,
    prepare_qualification_installation,
)


pytestmark = pytest.mark.platforms("windows")


def test_raw_build_helpers_are_installed_beside_their_shared_runtime(
    tmp_path: Path,
) -> None:
    """Place Qt helpers exactly where the release archive installs them."""

    repository_root = tmp_path / "repository"
    launcher_bundle = tmp_path / "bundle"
    install_root = tmp_path / "installed"
    for directory in (
        repository_root / ".venv",
        repository_root / "substitute",
        repository_root / "sugarsubstitute_shared",
        repository_root / "tools",
        launcher_bundle / "launcher-bin",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    (repository_root / "tools" / "single_instance_qualification_app.py").write_text(
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    for filename in ("SugarSubstitute.exe", "LauncherUi.exe", "Repair.exe"):
        (launcher_bundle / filename).write_bytes(filename.encode("ascii"))
    (launcher_bundle / "launcher-bin" / "python312.dll").write_bytes(b"runtime")

    layout = prepare_qualification_installation(
        repository_root=repository_root,
        launcher_bundle=launcher_bundle,
        install_root=install_root,
    )

    assert layout.launcher_ui_executable_path == (
        layout.launcher_support_path / "LauncherUi.exe"
    )
    assert layout.launcher_ui_executable_path.read_bytes() == b"LauncherUi.exe"
    assert (layout.launcher_support_path / "Repair.exe").read_bytes() == b"Repair.exe"
    assert not (layout.root / "LauncherUi.exe").exists()
    assert not (layout.root / "Repair.exe").exists()


def test_blank_launcher_qualification_preserves_first_run_state(
    tmp_path: Path,
) -> None:
    """Prepare released helper placement without manufacturing an installation."""

    launcher_bundle = tmp_path / "bundle"
    install_root = tmp_path / "blank-install"
    (launcher_bundle / "launcher-bin").mkdir(parents=True)
    for filename in ("SugarSubstitute.exe", "LauncherUi.exe", "Repair.exe"):
        (launcher_bundle / filename).write_bytes(filename.encode("ascii"))

    layout = prepare_launcher_surface_qualification_installation(
        launcher_bundle=launcher_bundle,
        install_root=install_root,
    )

    assert layout.launcher_ui_executable_path is not None
    assert layout.launcher_ui_executable_path.is_file()
    assert not layout.config_path.exists()
