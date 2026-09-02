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

"""Verify source splash first-paint liveness in a real Qt process."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.platforms("windows")


def test_source_splash_confirms_first_paint_before_exit(tmp_path: Path) -> None:
    """The real animated splash must paint headlessly before clean exit."""

    environment = os.environ.copy()
    repository_root = Path(__file__).resolve().parents[3]
    environment["PYTHONPATH"] = str(repository_root)
    environment["QT_QPA_PLATFORM"] = "minimal"
    environment["SUGAR_SUBSTITUTE_SPLASH_SURFACE_EVIDENCE"] = "1"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "substitute.app.bootstrap.shared_splash_host",
            "--maximum-lifetime-seconds=0.05",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    records = tuple(
        (tmp_path / "user" / "qualification-splash-surfaces").glob("*.json")
    )
    assert len(records) == 1
    evidence = json.loads(records[0].read_text(encoding="utf-8"))
    assert evidence["first_paint_confirmed"] is True
    assert evidence["top_level_surface_count"] == 1
    assert evidence["visible_top_level_surface_count"] == 1
