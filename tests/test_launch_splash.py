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

"""Tests for process-backed launch splash IPC and lifecycle behavior."""

from __future__ import annotations

from io import StringIO
import inspect
import logging
import subprocess
from threading import Event
from typing import Any, cast

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.app.bootstrap.launch_splash import (
    LaunchSplashCancelRelay,
    LaunchSplashProcessClient,
    ProcessPumpWork,
    decode_splash_helper_event,
    encode_splash_message,
    _read_helper_stderr,
)
from substitute.app.bootstrap import splash_process
from substitute.app.bootstrap.splash_process import (
    decode_splash_message,
    encode_splash_helper_event,
    parent_process_is_alive,
)
from substitute.presentation.shell.window_frame import ShellBackdropMode


class _FakeProcess:
    """Minimal process double for launch-splash client tests."""

    def __init__(self) -> None:
        """Initialize process state used by assertions."""

        self.stdin = StringIO()
        self.stdout = StringIO()
        self.stderr = StringIO()
        self.pid = 12345
        self.terminated = False
        self.killed = False
        self.wait_calls: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int:
        """Record wait timeout and report immediate exit."""

        self.wait_calls.append(timeout)
        return 0

    def poll(self) -> int | None:
        """Report that the process is still running."""

        return None

    def terminate(self) -> None:
        """Record termination without touching real processes."""

        self.terminated = True

    def kill(self) -> None:
        """Record kill without touching real processes."""

        self.killed = True


class _NonClosingStringIO(StringIO):
    """StringIO variant that keeps contents available after close calls."""

    def close(self) -> None:
        """Ignore close so tests can inspect written IPC records."""


class _ImmediateProcessPumpTaskHandle:
    """Represent an already-run process-pump task in tests."""

    @property
    def is_finished(self) -> bool:
        """Return that immediate test work is already complete."""

        return True

    def stop(self, *, reason: str) -> None:
        """Accept cancellation for client cleanup tests."""

        _ = reason


def _process_pump_task_factory(
    identity: TaskIdentity,
    context: ExecutionContext,
    work: ProcessPumpWork,
    thread_name: str,
) -> _ImmediateProcessPumpTaskHandle:
    """Run one launch-splash reader task immediately for tests."""

    _ = identity, context, thread_name
    work(CancellationSource(generation=1))
    return _ImmediateProcessPumpTaskHandle()


def test_encode_splash_message_returns_compact_json() -> None:
    """Splash IPC messages should be newline-safe compact JSON records."""

    assert encode_splash_message({"type": "log", "line": "Hello"}) == (
        '{"type":"log","line":"Hello"}'
    )


def test_encode_splash_helper_event_returns_compact_json() -> None:
    """Helper-to-parent splash events should be compact newline-safe JSON."""

    assert encode_splash_helper_event({"type": "cancel"}) == '{"type":"cancel"}'


def test_decode_splash_message_accepts_valid_records() -> None:
    """Helper message decoding should accept supported JSON object records."""

    assert decode_splash_message('{"type":"status","line":"Starting"}') == {
        "type": "status",
        "line": "Starting",
    }


def test_decode_splash_message_ignores_invalid_records() -> None:
    """Malformed helper IPC records should be ignored instead of crashing."""

    assert decode_splash_message("{") is None
    assert decode_splash_message("[]") is None
    assert decode_splash_message('{"line":"missing type"}') is None


def test_decode_splash_helper_event_accepts_cancel_only() -> None:
    """Parent event decoding should only accept the helper cancel event."""

    assert decode_splash_helper_event('{"type":"cancel"}') == {"type": "cancel"}
    assert decode_splash_helper_event("{") is None
    assert decode_splash_helper_event('{"type":"log","line":"ignored"}') is None


def test_launch_splash_process_client_sends_log_and_close_messages() -> None:
    """Process client should write log and close messages to helper stdin."""

    fake_process = _FakeProcess()
    fake_process.stdin = _NonClosingStringIO()
    client = LaunchSplashProcessClient(
        process=fake_process,  # type: ignore[arg-type]
        stdin=fake_process.stdin,
        process_pump_task_factory=_process_pump_task_factory,
    )

    client.append_log("Preparing interface.")
    client.close()

    assert fake_process.stdin.getvalue().splitlines() == [
        '{"type":"log","line":"Preparing interface."}',
        '{"type":"close"}',
    ]
    assert fake_process.wait_calls == [2.0]


def test_launch_splash_process_client_dispatches_helper_cancel_event() -> None:
    """Process client should invoke the parent cancel callback from helper stdout."""

    fake_process = _FakeProcess()
    fake_process.stdin = _NonClosingStringIO()
    fake_process.stdout = StringIO('{"type":"cancel"}\n')
    cancel_received = Event()

    LaunchSplashProcessClient(
        process=fake_process,  # type: ignore[arg-type]
        stdin=fake_process.stdin,
        stdout=fake_process.stdout,
        on_cancel_requested=cancel_received.set,
        process_pump_task_factory=_process_pump_task_factory,
    )

    assert cancel_received.wait(timeout=1.0)


def test_launch_splash_process_client_builds_internal_helper_command() -> None:
    """Process launch should target the internal splash helper without Comfy data."""

    observed: dict[str, Any] = {}

    def fake_popen(command: list[str], **kwargs: object) -> _FakeProcess:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return _FakeProcess()

    client = LaunchSplashProcessClient.start(
        parent_pid=456,
        python_executable="python.exe",
        process_pump_task_factory=_process_pump_task_factory,
        popen=cast(Any, fake_popen),
    )

    assert isinstance(client, LaunchSplashProcessClient)
    assert observed["command"] == [
        "python.exe",
        "-m",
        "substitute.app.bootstrap.splash_process",
        "--parent-pid",
        "456",
    ]
    assert "stdin" in observed["kwargs"]
    assert "stdout" in observed["kwargs"]
    assert observed["kwargs"]["stderr"] != subprocess.DEVNULL
    assert "Comfy" not in " ".join(observed["command"])


def test_launch_splash_process_client_pipes_helper_stderr() -> None:
    """Process launch should preserve helper tracebacks for normal logging."""

    observed: dict[str, Any] = {}

    def fake_popen(command: list[str], **kwargs: object) -> _FakeProcess:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return _FakeProcess()

    LaunchSplashProcessClient.start(
        parent_pid=456,
        python_executable="python.exe",
        process_pump_task_factory=_process_pump_task_factory,
        popen=cast(Any, fake_popen),
    )

    assert observed["kwargs"]["stderr"] == subprocess.PIPE


def test_read_helper_stderr_routes_lines_to_normal_logging(caplog: Any) -> None:
    """Helper stderr must go to app logging, not splash/Comfy output IPC."""

    caplog.set_level(
        logging.ERROR, logger="sugarsubstitute.app.bootstrap.launch_splash"
    )

    _read_helper_stderr(
        stream=StringIO("Traceback line 1\nTraceback line 2\n"),
        helper_pid=456,
        cancellation=CancellationSource(generation=1),
    )

    assert "Launch splash helper stderr" in caplog.text
    assert "Traceback line 1" in caplog.text
    assert "Traceback line 2" in caplog.text


def test_parent_process_is_alive_returns_true_for_current_process() -> None:
    """Parent liveness checks should recognize the current process as alive."""

    import os

    assert parent_process_is_alive(os.getpid()) is True


def test_launch_splash_cancel_relay_replays_early_cancel() -> None:
    """Early splash cancellation should replay once bootstrap attaches handling."""

    relay = LaunchSplashCancelRelay()
    callbacks: list[str] = []

    relay.request_cancel()
    relay.connect(lambda: callbacks.append("cancel"))

    assert relay.cancel_requested() is True
    assert callbacks == ["cancel"]


def test_launch_splash_cancel_relay_forwards_attached_cancel() -> None:
    """Attached bootstrap cancellation should receive later splash close events."""

    relay = LaunchSplashCancelRelay()
    callbacks: list[str] = []

    relay.connect(lambda: callbacks.append("cancel"))
    relay.request_cancel()

    assert callbacks == ["cancel"]


def test_splash_process_configures_theme_before_constructing_splash() -> None:
    """Helper process must apply QFluent theme before creating SplashWindow."""

    source = inspect.getsource(splash_process.main)

    assert source.index("configure_theme(") < source.index("SplashWindow")


def test_splash_process_sets_app_icon_before_constructing_splash() -> None:
    """Helper process must set the QApplication icon before splash construction."""

    source = inspect.getsource(splash_process.main)

    assert source.index("app.setWindowIcon(application_icon())") < source.index(
        "SplashWindow"
    )


def test_splash_process_maps_mica_alt_backdrop_arg_to_plain_mica() -> None:
    """Splash helper should downgrade Mica Alt requests to plain Mica."""

    assert splash_process._backdrop_mode_from_arg("mica_alt") is ShellBackdropMode.MICA
    assert splash_process._backdrop_mode_from_arg("mica") is ShellBackdropMode.MICA
    assert splash_process._backdrop_mode_from_arg("acrylic") is (
        ShellBackdropMode.ACRYLIC
    )
