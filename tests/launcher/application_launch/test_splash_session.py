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

"""Verify launcher-created shared splash-session handoff."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from typing import Any, cast

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.splash_session import (
    LauncherSplashSession,
    append_splash_session_args,
    start_launcher_splash_session,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
    subprocess_working_directory,
)


def test_launcher_splash_session_starts_host_and_returns_app_args(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The launcher should execute the app-payload host and parse its session spec."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    calls: list[dict[str, Any]] = []
    ready = {
        "type": "ready",
        "endpoint": "127.0.0.1:49152",
        "token": "x" * 32,
        "host_pid": 1234,
    }

    def _fake_popen(command: list[str], **kwargs: Any) -> _FakeProcess:
        """Record host process creation and return a ready fake process."""

        calls.append({"command": command, **kwargs})
        return _FakeProcess(stdout=json.dumps(ready) + "\n")

    session = start_launcher_splash_session(
        layout=layout,
        locale_identifier="ja",
        popen=cast(Any, _fake_popen),
    )

    assert session is not None
    assert session.host_pid == 1234
    assert session.app_arguments == (
        "--splash-session-endpoint=127.0.0.1:49152",
        f"--splash-session-token={'x' * 32}",
        "--splash-session-host-pid=1234",
    )
    assert calls[0]["command"] == [
        subprocess_path(layout.runtime_python),
        "-m",
        "substitute.app.bootstrap.shared_splash_host",
        "--locale=ja",
    ]
    assert calls[0]["cwd"] == subprocess_working_directory(layout.root)
    assert calls[0]["env"]["PYTHONPATH"] == subprocess_path(layout.app_dir)
    assert (
        int(
            calls[0]["env"][
                "SUGAR_SUBSTITUTE_SPLASH_HOST_PROCESS_REQUESTED_MONOTONIC_NS"
            ]
        )
        > 0
    )


def test_launcher_splash_session_returns_none_for_invalid_ready_payload(
    tmp_path: Path,
) -> None:
    """Malformed host output should stop its splash before direct fallback starts."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    process = _FakeProcess(stdout='{"type":"not-ready"}\n')

    def _fake_popen(command: list[str], **kwargs: Any) -> _FakeProcess:
        """Return invalid stdout while accepting the host command."""

        _ = command
        _ = kwargs
        return process

    assert (
        start_launcher_splash_session(
            layout=layout,
            locale_identifier="en",
            popen=cast(Any, _fake_popen),
        )
        is None
    )
    assert process.terminated is True
    assert process.wait_timeouts == [2.0]


def test_append_splash_session_args_preserves_command_without_session() -> None:
    """Launch command construction should stay unchanged when no session exists."""

    assert append_splash_session_args(["python", "main.py"], None) == [
        "python",
        "main.py",
    ]


def test_unacknowledged_splash_close_terminates_the_owned_process() -> None:
    """An unresponsive splash can never survive its launcher-owned handoff."""

    process = _FakeProcess(stdout="", wait_times_out_while_running=True)
    session = LauncherSplashSession(
        client=cast(Any, _UnresponsiveClient()),
        app_arguments=(),
        host_pid=1234,
        process=cast(Any, process),
    )

    session.close()

    assert process.terminated
    assert process.wait_timeouts == [2.0, 2.0]


class _UnresponsiveClient:
    """Reject the splash closure request without raising."""

    def close(self) -> bool:
        """Report that the GUI never applied closure."""

        return False


class _FakeProcess:
    """Provide the subset of `Popen[str]` used by splash session startup tests."""

    def __init__(
        self,
        *,
        stdout: str,
        wait_times_out_while_running: bool = False,
    ) -> None:
        """Create fake text pipes."""

        self.stdout = StringIO(stdout)
        self.stderr = StringIO("")
        self.terminated = False
        self.killed = False
        self.wait_timeouts: list[float] = []
        self.wait_times_out_while_running = wait_times_out_while_running

    def poll(self) -> int | None:
        """Report the fake process as running until it is terminated."""

        return 0 if self.terminated or self.killed else None

    def terminate(self) -> None:
        """Record graceful process termination."""

        self.terminated = True

    def kill(self) -> None:
        """Record forced process termination."""

        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        """Record the bounded wait and report successful process exit."""

        if timeout is not None:
            self.wait_timeouts.append(timeout)
        if (
            self.wait_times_out_while_running
            and not self.terminated
            and not self.killed
        ):
            import subprocess

            raise subprocess.TimeoutExpired("splash", timeout or 0.0)
        return 0
