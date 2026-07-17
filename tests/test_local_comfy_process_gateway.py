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

"""Tests for conservative local Comfy process identification."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.onboarding import LocalComfyProcess
from substitute.infrastructure.comfy.local_process_gateway import (
    _collapse_nested_launchers,
    _workspace_from_command,
)


def test_workspace_identity_accepts_absolute_comfy_main(tmp_path: Path) -> None:
    """An absolute main.py command should identify its complete Comfy workspace."""

    workspace = _workspace(tmp_path / "ComfyUI")

    identified = _workspace_from_command(
        (str(tmp_path / "python.exe"), str(workspace / "main.py")),
        tmp_path,
    )

    assert identified == workspace.resolve()


def test_workspace_identity_resolves_relative_main_from_process_cwd(
    tmp_path: Path,
) -> None:
    """Portable launch commands should resolve main.py through process cwd."""

    workspace = _workspace(tmp_path / "portable" / "ComfyUI")

    identified = _workspace_from_command(
        (str(tmp_path / "python.exe"), "main.py", "--port", "8188"),
        workspace,
    )

    assert identified == workspace.resolve()


def test_workspace_identity_rejects_unrelated_python_main(tmp_path: Path) -> None:
    """A generic Python main.py process must not be treated as ComfyUI."""

    application = tmp_path / "other"
    application.mkdir(parents=True)
    (application / "main.py").write_text("", encoding="utf-8")

    identified = _workspace_from_command(
        (str(tmp_path / "python.exe"), "main.py"),
        application,
    )

    assert identified is None


def test_nested_virtual_environment_launcher_is_one_comfy_instance(
    tmp_path: Path,
) -> None:
    """A same-workspace Python child should not look like a second launch."""

    workspace = tmp_path / "ComfyUI"
    parent = LocalComfyProcess(
        pid=100,
        create_time=1.0,
        python_executable=tmp_path / "venv" / "Scripts" / "python.exe",
        workspace=workspace,
    )
    child = LocalComfyProcess(
        pid=101,
        create_time=1.1,
        python_executable=tmp_path / "base-python.exe",
        workspace=workspace,
    )

    assert _collapse_nested_launchers((parent, child), {100: 1, 101: 100}) == (parent,)


def _workspace(path: Path) -> Path:
    """Create the minimum source layout required for confident identification."""

    (path / "comfy").mkdir(parents=True)
    (path / "main.py").write_text("", encoding="utf-8")
    return path
