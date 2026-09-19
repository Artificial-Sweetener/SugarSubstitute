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

"""Prove that explicit cancellation retires startup without reporting readiness failure."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationStartupCancelled,
    CandidateProcess,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


class _Process:
    """Record cancellation at the external process lifetime boundary."""

    pid = 4401

    def __init__(self) -> None:
        """Start as a live process awaiting its first painted window."""
        self.ended = False
        self.waited = False

    def poll(self) -> int | None:
        """Expose completion only after termination was requested."""
        return 1 if self.ended else None

    def terminate(self) -> None:
        """Retire the synthetic startup process."""
        self.ended = True

    def kill(self) -> None:
        """Support forced termination at the OS boundary."""
        self.ended = True

    def wait(self, timeout: float | None = None) -> int:
        """Confirm that supervision waited for process cleanup."""
        assert self.ended
        self.waited = True
        return 1


@pytest.mark.parametrize("cancel_before_spawn", [True, False])
def test_cancellation_retires_startup_without_waiting_for_readiness(
    tmp_path: Path,
    cancel_before_spawn: bool,
) -> None:
    """Respect cancellation before launch and while no readiness receipt exists."""
    process = _Process()
    started = False

    def start(
        command: Sequence[str], environment: Mapping[str, str]
    ) -> tuple[CandidateProcess, Path]:
        """Represent starting the candidate without executing an external command."""
        nonlocal started
        started = True
        return process, tmp_path / "startup.log"

    supervisor = ApplicationReadinessSupervisor(
        process_starter=start,
        cancellation_requested=lambda: cancel_before_spawn or started,
    )
    with pytest.raises(ApplicationStartupCancelled) as raised:
        supervisor.launch_until_ready(
            layout=InstallLayout.from_root(tmp_path), command=("app",), environment={}
        )
    assert started is not cancel_before_spawn
    assert process.ended is not cancel_before_spawn
    assert process.waited is not cancel_before_spawn
    assert raised.value.terminated_process is (None if cancel_before_spawn else process)
