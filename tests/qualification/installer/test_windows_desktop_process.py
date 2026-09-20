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

"""Prove installed-update qualification crosses the Windows host-job boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

from tools.ci.windows_desktop_process import start_windows_desktop_process

pytestmark = pytest.mark.platforms("windows")


def test_desktop_process_inherits_environment_without_host_job(tmp_path: Path) -> None:
    """Model an Explorer launch even when the qualification host is contained."""

    evidence_path = tmp_path / "desktop-process.json"
    script = (
        "import ctypes, json, os, pathlib, time; "
        "from ctypes import wintypes; "
        "kernel=ctypes.WinDLL('kernel32', use_last_error=True); "
        "kernel.IsProcessInJob.argtypes=[wintypes.HANDLE,wintypes.HANDLE,"
        "ctypes.POINTER(wintypes.BOOL)]; "
        "member=wintypes.BOOL(); "
        "ok=kernel.IsProcessInJob(kernel.GetCurrentProcess(),None,"
        "ctypes.byref(member)); "
        "assert ok; "
        f"pathlib.Path({str(evidence_path)!r}).write_text(json.dumps("
        "{'in_job': bool(member.value), 'token': os.environ['DESKTOP_TOKEN']}), "
        "encoding='utf-8'); time.sleep(0.2)"
    )
    environment = dict(os.environ)
    environment["DESKTOP_TOKEN"] = "qualified"
    process = start_windows_desktop_process(
        [str(Path(sys.base_prefix) / "python.exe"), "-c", script],
        environment=environment,
        cwd=tmp_path,
    )

    assert process.wait(10.0) == 0
    assert json.loads(evidence_path.read_text(encoding="utf-8")) == {
        "in_job": False,
        "token": "qualified",
    }
