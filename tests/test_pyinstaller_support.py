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

"""Validate external executable discovery for PyInstaller builds."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.pyinstaller_support import resolve_uv_executable


def test_resolve_uv_executable_prefers_active_python_environment(
    tmp_path: Path,
) -> None:
    """Prefer the uv installed beside the interpreter running PyInstaller."""

    executable_name = "uv.exe" if os.name == "nt" else "uv"
    python_name = "python.exe" if os.name == "nt" else "python"
    python_executable = tmp_path / python_name
    environment_uv = tmp_path / executable_name
    environment_uv.touch()

    resolved = resolve_uv_executable(
        python_executable=python_executable,
        path_lookup=lambda _name: str(tmp_path / "path-uv"),
    )

    assert resolved == str(environment_uv.resolve())


def test_resolve_uv_executable_falls_back_to_shell_path(tmp_path: Path) -> None:
    """Support builds whose uv executable is intentionally available on PATH."""

    path_uv = str(tmp_path / "path-uv")

    resolved = resolve_uv_executable(
        python_executable=tmp_path / "missing-python",
        path_lookup=lambda _name: path_uv,
    )

    assert resolved == path_uv


@pytest.mark.skipif(os.name == "nt", reason="POSIX virtual environments use symlinks")
def test_resolve_uv_executable_keeps_virtual_environment_symlink_path(
    tmp_path: Path,
) -> None:
    """Search beside a venv interpreter symlink instead of its system target."""

    environment_dir = tmp_path / "environment" / "bin"
    environment_dir.mkdir(parents=True)
    hosted_python = tmp_path / "hosted" / "bin" / "python"
    hosted_python.parent.mkdir(parents=True)
    hosted_python.touch()
    environment_python = environment_dir / "python"
    environment_python.symlink_to(hosted_python)
    environment_uv = environment_dir / "uv"
    environment_uv.touch()

    resolved = resolve_uv_executable(
        python_executable=environment_python,
        path_lookup=lambda _name: None,
    )

    assert resolved == str(environment_uv.resolve())


def test_resolve_uv_executable_rejects_missing_uv(tmp_path: Path) -> None:
    """Fail with actionable guidance when neither supported location has uv."""

    with pytest.raises(RuntimeError, match="active Python interpreter or on PATH"):
        resolve_uv_executable(
            python_executable=tmp_path / "missing-python",
            path_lookup=lambda _name: None,
        )
