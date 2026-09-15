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

"""Verify output protocol isolation at the supervised helper's process boundary."""

from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sys

import pytest

from sugarsubstitute_shared.supervised_text_process import start_supervised_text_process


def test_helper_preserves_separate_utf8_protocol_and_diagnostic_streams(
    tmp_path: Path,
) -> None:
    """Diagnostics must not corrupt the first startup-protocol line."""
    process = start_supervised_text_process(
        [
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('diagnostic λ\\n'); sys.stderr.flush(); print('ready 日本語')",
        ],
        environment={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=tmp_path,
    )
    try:
        with closing(process.stdout), closing(process.stderr):
            assert process.wait(timeout=10) == 0
            assert process.stdout.read() == "ready 日本語\n"
            assert process.stderr.read() == "diagnostic λ\n"
            assert process.poll() == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_unavailable_helper_executable_reports_spawn_failure(tmp_path: Path) -> None:
    """A missing helper must fail at creation instead of leaving a pending session."""
    with pytest.raises(OSError):
        start_supervised_text_process(
            [str(tmp_path / "missing-helper")],
            environment=os.environ,
            cwd=tmp_path,
        )
