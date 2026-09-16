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

"""Verify recovery after abrupt exit rather than caught transaction exceptions."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from sugarsubstitute_shared.repair_recovery.execution import recover_interrupted_repair


@pytest.mark.parametrize(
    ("boundary", "exit_code", "expected_version"),
    [
        ("relocation", 71, "original"),
        ("rollback", 72, "original"),
        ("commit", 73, "candidate"),
        ("before_relocation", 74, "original"),
        ("promotion", 75, "original"),
        ("rollback_candidate", 76, "original"),
        ("rollback_cleanup", 77, "original"),
    ],
)
def test_recovery_survives_abrupt_filesystem_transition(
    tmp_path: Path, boundary: str, exit_code: int, expected_version: str
) -> None:
    """Retain the correct installation and finish recovery exactly once."""
    root = tmp_path / "installation"
    for name in ("app", "runtime"):
        app = root / name
        app.mkdir(parents=True)
        (app / "version.txt").write_text("original", encoding="utf-8")
        staged = root / ".repair/staging" / name
        staged.mkdir(parents=True)
        (staged / "version.txt").write_text("candidate", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.support.repair_interruption",
            str(root),
            boundary,
        ],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    assert result.returncode == exit_code, result.stderr
    assert (root / ".repair/pending.json").exists()
    assert recover_interrupted_repair(root)
    for name in ("app", "runtime"):
        assert (root / name / "version.txt").read_text(
            encoding="utf-8"
        ) == expected_version
    assert not (root / ".repair/pending.json").exists()
    assert not recover_interrupted_repair(root)
