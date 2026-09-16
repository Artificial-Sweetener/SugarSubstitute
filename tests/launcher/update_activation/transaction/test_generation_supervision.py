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

"""Verify selected launcher failure boundaries and owned process cleanup."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import generation_supervision
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting import CrashIncidentStore


@pytest.mark.parametrize(
    "outcome", ["spawn-error", "wait-error", "report-error", "crashed"]
)
def test_generation_failure_distinguishes_startup_from_owned_lifetime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """Allow startup fallback only before spawn and reap live children on failure."""
    layout = InstallLayout.from_root(tmp_path)

    class Process:
        """Control the OS boundary while preserving crash classification."""

        pid = 123

        def __init__(self) -> None:
            """Start with the selected execution still alive."""
            self.running = True
            self.killed = False

        def wait(self, timeout: float | None = None) -> int:
            """Inject an OS wait failure only while the test process is live."""
            if outcome == "wait-error" and self.running:
                raise OSError("wait failed")
            self.running = False
            return 73

        def poll(self) -> int | None:
            """Expose the live state for failure cleanup."""
            return None if self.running else 73

        def kill(self) -> None:
            """Record process-family termination through its owned handle."""
            self.killed = True
            self.running = False

    process = Process()

    def spawn(
        command: Sequence[str], *, environment: Mapping[str, str], allow_handoff: bool
    ) -> tuple[Process, Path]:
        """Inject only the OS creation boundary."""
        assert allow_handoff
        if outcome == "spawn-error":
            raise OSError("spawn failed")
        return process, tmp_path / "startup.log"

    def report(
        layout: InstallLayout, incident: str, environment: Mapping[str, str]
    ) -> None:
        """Prevent visible reporters while testing reporter-boundary failures."""
        if outcome == "report-error":
            raise RuntimeError("report failed")

    crash = ApplicationCrashSupervisor(reporter_starter=report)
    monkeypatch.setattr(generation_supervision, "spawn_supervised_process", spawn)
    monkeypatch.setattr(
        generation_supervision, "ApplicationCrashSupervisor", lambda: crash
    )
    supervisor = generation_supervision.LauncherGenerationSupervisor()
    if outcome == "spawn-error":
        with pytest.raises(generation_supervision.GenerationStartupError):
            supervisor.supervise(layout=layout, command=("fixture",), environment={})
        assert not process.killed
    elif outcome in {"wait-error", "report-error"}:
        error_type = OSError if outcome == "wait-error" else RuntimeError
        with pytest.raises(error_type):
            supervisor.supervise(layout=layout, command=("fixture",), environment={})
        assert not process.running
        assert process.killed == (outcome == "wait-error")
    else:
        assert (
            supervisor.supervise(layout=layout, command=("fixture",), environment={})
            == 73
        )
        assert not process.running
        assert not process.killed
        incidents = CrashIncidentStore(
            layout.appdata_dir / "diagnostics" / "crashes"
        ).pending()
        assert len(incidents) == 1
        assert incidents[0].exit_code == 73
