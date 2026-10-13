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

"""Keep source-host initialization output from blocking its readiness handshake."""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO
import json
from pathlib import Path
import subprocess
from typing import cast

import pytest

from substitute.app.bootstrap.early_launch_splash import start_shared_launch_splash
from substitute.app.bootstrap.launch_splash import (
    ProcessPumpTaskHandle,
    ProcessPumpWork,
)
from substitute.app.bootstrap.launch_splash_client import NullLaunchSplashClient
from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from sugarsubstitute_shared.launch_splash import (
    SocketSplashSessionClient,
    create_splash_session_spec,
)


class _BackpressuredStdout:
    """Require pending host stderr to drain before its first protocol output."""

    def __init__(self, output: str, stderr: StringIO) -> None:
        """Model initialization blocked behind an unread diagnostic pipe."""
        self._stream = StringIO(output)
        self._stderr = stderr

    def readline(self, size: int = -1) -> str:
        """Fail deterministically rather than hanging if stderr is still pending."""
        if self._stderr.tell() != len(self._stderr.getvalue()):
            raise BlockingIOError("Host initialization is blocked on stderr.")
        return self._stream.readline(size)

    def __iter__(self) -> Iterator[str]:
        """Expose remaining fixture lines to the established stdout reader."""
        return iter(self._stream)


class _HostProcess:
    """Expose controlled output pipes without spawning a child process."""

    def __init__(self, output: str) -> None:
        """Put initialization diagnostics ahead of ready, cancellation, or EOF."""
        self.stderr = StringIO("Initialization warning before readiness.\n")
        self.stdout = _BackpressuredStdout(output, self.stderr)


class _CompletedPump:
    """Represent synchronously consumed fixture pipes."""

    @property
    def is_finished(self) -> bool:
        """Report that all supplied pipe output has been consumed."""
        return True

    def stop(self, *, reason: str) -> None:
        """Accept no-op cleanup after the fixture pump completes."""


@pytest.mark.parametrize("outcome", ["ready", "cancel", "eof"])
def test_initializer_stderr_is_drained_before_waiting_for_host_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    outcome: str,
) -> None:
    """Keep ready, cancellation and terminal EOF reachable despite initializer output."""
    spec = create_splash_session_spec(port=49152, token="p" * 32, host_pid=1234)
    output = {
        "ready": json.dumps(
            {
                "type": "ready",
                "endpoint": spec.endpoint,
                "token": spec.token,
                "host_pid": spec.host_pid,
                "protocol_version": spec.protocol_version,
            }
        )
        + "\n",
        "cancel": '{"type":"cancel"}\n',
        "eof": "",
    }[outcome]
    process = _HostProcess(output)
    cancellations: list[bool] = []

    def start_process(*args: object, **kwargs: object) -> subprocess.Popen[str]:
        """Return the diagnostic-producing host at the subprocess boundary."""
        return cast("subprocess.Popen[str]", process)

    def start_pump(
        identity: TaskIdentity,
        context: ExecutionContext,
        work: ProcessPumpWork,
        thread_name: str,
    ) -> ProcessPumpTaskHandle:
        """Consume fixture output through the production reader without a thread."""
        work(CancellationSource(generation=0))
        return _CompletedPump()

    monkeypatch.setattr(subprocess, "Popen", start_process)
    client, actual_spec = start_shared_launch_splash(
        app_root=tmp_path,
        on_cancel_requested=lambda: cancellations.append(True),
        language_identifier="en",
        process_pump_task_factory=start_pump,
    )

    assert "Initialization warning before readiness." in caplog.text
    assert "Host initialization is blocked on stderr." not in caplog.text
    assert cancellations == ([True] if outcome == "cancel" else [])
    if outcome == "ready":
        assert isinstance(client, SocketSplashSessionClient)
        assert actual_spec == spec
    else:
        assert isinstance(client, NullLaunchSplashClient)
        assert actual_spec is None
