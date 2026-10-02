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

"""Verify slow splash bootstrap, terminal deadlines, and early cancellation."""

from io import StringIO
from pathlib import Path
import subprocess
from threading import Event
from typing import IO, cast

import pytest

from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationStartupCancelled,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.splash_host_readiness import (
    read_splash_host_ready_line,
)
from launcher.sugarsubstitute_launcher.splash_session import (
    start_launcher_splash_session,
)
from sugarsubstitute_shared.supervised_text_process import SupervisedTextProcess
from tests.launcher.application_launch.splash_process_fixture import SplashProcessDouble


@pytest.mark.parametrize("expire", [False, True])
def test_slow_host_survives_old_cutoff_but_not_terminal_deadline(expire: bool) -> None:
    """Advance a controlled clock beyond eight seconds without replacing a live host."""
    entered = Event()
    release = Event()
    reader_finished = Event()
    clock = [0.0]

    class ControlledPipe:
        """Hold first output behind an explicit bootstrap barrier."""

        def __init__(self, text: str) -> None:
            """Own a text stream whose first read is admitted by the test barrier."""
            self._stream = StringIO(text)

        def readline(self, size: int = -1) -> str:
            """Wait for authorized initialization rather than an arbitrary sleep."""
            entered.set()
            try:
                assert release.wait(10), "Bootstrap barrier was not released"
                return self._stream.readline(size)
            finally:
                reader_finished.set()

        def close(self) -> None:
            """Release the fixture's text stream after its reader has finished."""
            self._stream.close()

    process = SplashProcessDouble(stdout="")
    process.stdout = cast(IO[str], ControlledPipe("ready\n"))
    waits = [0]

    def wait(completed: Event, seconds: float) -> bool:
        """Expose the old cutoff and then the independently controlled terminal state."""
        assert entered.wait(10), "Readiness reader did not start"
        assert not process.terminated
        waits[0] += 1
        clock[0] = 9.0
        if waits[0] == 1:
            return False
        if expire:
            clock[0] = 30.0
            return False
        release.set()
        return completed.wait(10)

    try:
        if expire:
            with pytest.raises(subprocess.TimeoutExpired):
                read_splash_host_ready_line(
                    cast(SupervisedTextProcess, process),
                    timeout_seconds=30,
                    monotonic=lambda: clock[0],
                    wait=wait,
                )
        else:
            assert (
                read_splash_host_ready_line(
                    cast(SupervisedTextProcess, process),
                    timeout_seconds=30,
                    monotonic=lambda: clock[0],
                    wait=wait,
                )
                == "ready\n"
            )
        assert not process.terminated
    finally:
        release.set()
        assert reader_finished.wait(10), "Fixture left its pipe reader blocked"
        process.stdout.close()


def test_cancel_before_ready_retires_the_owned_host_and_cancels_startup(
    tmp_path: Path,
) -> None:
    """An early Close must never fall back to launching an application."""
    process = SplashProcessDouble(stdout='{"type":"cancel"}\n')

    def start(*args: object, **kwargs: object) -> SupervisedTextProcess:
        """Provide an owned host that reports cancellation before its session spec."""
        return cast(SupervisedTextProcess, process)

    with pytest.raises(ApplicationStartupCancelled):
        start_launcher_splash_session(
            layout=InstallLayout.from_root(tmp_path),
            locale_override=None,
            process_starter=start,
        )
    assert process.terminated
    assert process.stdout.closed
