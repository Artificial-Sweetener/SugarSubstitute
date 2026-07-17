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

"""Verify launcher-owned resource discovery policy."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

from pytest import MonkeyPatch

from launcher.sugarsubstitute_launcher import runtime_resources
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


def test_launcher_uv_prefers_active_interpreter_environment(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Source setup should use the tested uv beside its active venv Python."""

    scripts_dir = tmp_path / "Scripts"
    scripts_dir.mkdir()
    python_executable = scripts_dir / "python.exe"
    python_executable.write_bytes(b"")
    environment_uv = scripts_dir / "uv.exe"
    environment_uv.write_bytes(b"current")
    path_uv = tmp_path / "old" / "uv.exe"
    path_uv.parent.mkdir()
    path_uv.write_bytes(b"old")
    monkeypatch.setattr(sys, "executable", str(python_executable))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing"), raising=False)
    monkeypatch.setattr(shutil, "which", lambda _name: str(path_uv))

    resolved = runtime_resources.launcher_uv_path(target=WINDOWS_X64)

    assert resolved == environment_uv.resolve()
