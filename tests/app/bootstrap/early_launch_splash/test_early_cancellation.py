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

"""Preserve source-startup cancellation before the shared host becomes ready."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
import subprocess
from typing import cast

import pytest

from substitute.app.bootstrap import early_launch_splash
from substitute.app.bootstrap.launch_splash import (
    ProcessPumpTaskHandle,
    ProcessPumpWork,
)
from substitute.app.bootstrap.launch_splash_client import NullLaunchSplashClient
from substitute.application.execution import ExecutionContext, TaskIdentity
from sugarsubstitute_shared.launch_splash import (
    create_splash_session_spec,
    splash_session_args,
)


class _UnreadyHostProcess:
    """Expose only the subprocess pipes consumed before host readiness."""

    def __init__(self, output: str) -> None:
        """Supply a deterministic first protocol line without starting a process."""
        self.stdout = StringIO(output)
        self.stderr = None


class _UnavailableAdoptedSplash:
    """Fail the adopted endpoint so source startup creates its fallback host."""

    def append_log(self, line: str) -> None:
        """Model the failed initial handoff write."""
        raise OSError("adopted splash unavailable")


class _CompletedTask:
    """Keep watcher composition observable without leaving a running thread."""

    @property
    def is_finished(self) -> bool:
        """Report that the inert task requires no background cleanup."""
        return True

    def stop(self, *, reason: str) -> None:
        """Accept cleanup for an inert task."""


@pytest.mark.parametrize("adopted_session", [False, True])
@pytest.mark.parametrize("cancelled", [False, True])
def test_pre_ready_cancel_is_replayed_instead_of_discarded_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    adopted_session: bool,
    cancelled: bool,
) -> None:
    """Retain cancellation through initial and fallback launch composition."""
    process = _UnreadyHostProcess('{"type":"cancel"}\n' if cancelled else "")
    launches: list[object] = []
    started_tasks: list[str] = []

    def start_process(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """Supply the owned host pipe at the real process-creation boundary."""
        launches.append(args)
        return cast("subprocess.Popen[str]", process)

    def start_task(
        identity: TaskIdentity,
        context: ExecutionContext,
        work: ProcessPumpWork,
        thread_name: str,
    ) -> ProcessPumpTaskHandle:
        """Record only already-adopted cancellation watching, without executing it."""
        started_tasks.append(identity.domain)
        return _CompletedTask()

    monkeypatch.delenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", raising=False)
    monkeypatch.setattr(subprocess, "Popen", start_process)
    monkeypatch.setattr(
        early_launch_splash, "_create_early_process_pump_task", start_task
    )
    argv = ["main.py"]
    if adopted_session:
        spec = create_splash_session_spec(port=49152, token="c" * 32, host_pid=1234)
        argv.extend(splash_session_args(spec))
        monkeypatch.setattr(
            early_launch_splash,
            "_connect_splash_session",
            lambda _spec: _UnavailableAdoptedSplash(),
        )

    splash, relay = early_launch_splash.start_early_launch_splash(argv, tmp_path, "en")

    assert len(launches) == 1
    assert started_tasks == (
        ["shared_launch_splash_cancel_watcher"] if adopted_session else []
    )
    if cancelled:
        assert isinstance(splash, NullLaunchSplashClient)
        assert relay is not None
        assert relay.cancel_requested()
        cancellations: list[bool] = []
        relay.connect(lambda: cancellations.append(True))
        assert cancellations == [True]
    else:
        assert splash is None
        assert relay is None
