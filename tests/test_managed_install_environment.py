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

"""Verify managed-install subprocess environment ownership."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.managed_install_environment import (
    build_managed_install_environment,
)


def test_environment_routes_temporary_storage_through_scratch_root(
    tmp_path: Path,
) -> None:
    """Every child temporary variable should reference materialized scratch."""

    scratch_root = tmp_path / "scratch"
    env = build_managed_install_environment(
        scratch_root,
        {"PATH": "C:\\Tools"},
    )

    temp_dir = scratch_root / "temp"
    assert env["TEMP"] == str(temp_dir)
    assert env["TMP"] == str(temp_dir)
    assert env["TMPDIR"] == str(temp_dir)
    assert env["PIP_CACHE_DIR"] == str(scratch_root / "pip-cache")
    assert env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8:replace"
    assert env["PATH"] == "C:\\Tools"
    assert temp_dir.is_dir()
    assert (scratch_root / "pip-cache").is_dir()
