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

"""Prove failed repair cleanup retires its host and releases native mutation locks."""

from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.crash_reporting.protocol import (
    without_crash_supervision_environment,
)
from sugarsubstitute_shared.installation_mutation import installation_mutation


@pytest.mark.platforms("windows")
def test_failed_native_cleanup_retires_host_and_reclaims_descendants(
    tmp_path: Path,
) -> None:
    """Exercise real Qt cancellation and outer Windows containment without user retry."""
    environment = without_crash_supervision_environment()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    process, log = spawn_supervised_process(
        (
            sys.executable,
            "-m",
            "tests.launcher.repair.failed_cleanup_host",
            str(tmp_path),
        ),
        environment=environment,
        startup_log_path=tmp_path / "host.log",
    )
    try:
        assert process.wait(timeout=30) == 1, log.read_text(encoding="utf-8")
        assert (tmp_path / "cancellation-observed.txt").read_text(
            encoding="utf-8"
        ) == "both-owned"
        assert "Injected native family termination failure" in log.read_text(
            encoding="utf-8"
        )
        for directory in (tmp_path, tmp_path / "descendant"):
            with installation_mutation(directory) as ownership:
                ownership.validate(directory)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
