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

"""Verify native backdrop recovery after Qt promotes the shell to OpenGL."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.platforms("windows")
def test_image_and_video_presentations_retain_mica_after_surface_recreation() -> None:
    """Reapply Mica to the replacement HWND created for embedded OpenGL."""

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    environment["QT_OPENGL"] = "software"
    result = subprocess.run(
        [sys.executable, "-m", "tests.support.window_backdrop_recreation_probe"],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
