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

"""Tests for one managed ComfyUI process behavior owner."""

from __future__ import annotations

from __future__ import annotations
import os
import signal
import subprocess
import threading
from typing import cast
import pytest
from substitute.infrastructure.comfy import (
    posix_guardian_containment,
    posix_guardian_entry,
)
from substitute.infrastructure.comfy.posix_guardian_containment import (
    PosixGuardianContainmentHandle,
)


def test_posix_guardian_handle_close_preserves_log_stream() -> None:
    """POSIX cleanup should preserve the stderr stream owned by the log pump."""

    closed_streams: list[str] = []
    guardian_process = _FakeGuardianProcess(closed_streams)
    handle = PosixGuardianContainmentHandle(
        guardian_process=cast(subprocess.Popen[bytes], guardian_process),
        keepalive_write_fd=_create_pipe_write_fd(),
        guardian_pipe_token="guardian-1",
        process_group_id=321,
    )

    handle.close()

    assert "stdin" in closed_streams
    assert "stdout" in closed_streams
    assert "stderr" not in closed_streams


def test_terminate_process_group_yields_between_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POSIX process-group termination should sleep between liveness probes."""

    running_states = iter([True, True, False])
    sent_signals: list[int] = []
    sleep_calls: list[float] = []
    monotonic_values = iter([0.0, 0.01, 0.02])

    monkeypatch.setattr(
        posix_guardian_containment,
        "is_process_group_running",
        lambda _pgid: next(running_states),
    )
    monkeypatch.setattr(
        posix_guardian_containment,
        "_kill_process_group",
        lambda _pgid, signum: sent_signals.append(signum),
    )
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("time.sleep", lambda seconds: sleep_calls.append(seconds))

    posix_guardian_containment.terminate_process_group(123, timeout_seconds=1.0)

    assert sent_signals == [signal.SIGTERM]
    assert sleep_calls == [0.1]


def test_inaccessible_process_group_is_not_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permission denial must not authorize signaling an unrelated group."""

    def deny_signal(_process_group_id: int, _signum: int) -> None:
        """Simulate a process group that the current install does not own."""

        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(
        posix_guardian_containment,
        "_kill_process_group",
        deny_signal,
    )

    assert posix_guardian_containment.is_process_group_running(123) is False


def test_process_group_termination_tolerates_ownership_loss_after_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reused group id must not turn successful cleanup into an exception."""

    monkeypatch.setattr(
        posix_guardian_containment,
        "is_process_group_running",
        lambda _process_group_id: True,
    )

    def deny_signal(_process_group_id: int, _signum: int) -> None:
        """Simulate ownership changing between the probe and the signal."""

        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(
        posix_guardian_containment,
        "_kill_process_group",
        deny_signal,
    )

    posix_guardian_containment.terminate_process_group(123, timeout_seconds=1.0)


def test_guardian_falls_back_to_its_child_when_group_signal_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guardian shutdown must still stop its directly owned managed child."""

    class _ChildProcess:
        """Expose a directly owned child that exits after SIGTERM."""

        returncode: int | None = None

        def poll(self) -> int | None:
            """Return the current simulated child state."""

            return self.returncode

        def terminate(self) -> None:
            """Record orderly direct-child termination."""

            self.returncode = 0

        def kill(self) -> None:
            """Record forced direct-child termination."""

            self.returncode = -int(getattr(signal, "SIGKILL", signal.SIGTERM))

    def deny_group_signal(_process_group_id: int) -> None:
        """Simulate macOS denying process-group signaling."""

        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(
        posix_guardian_entry,
        "_terminate_process_group",
        deny_group_signal,
    )
    stop_event = threading.Event()
    stop_event.set()
    child = _ChildProcess()

    result = posix_guardian_entry._monitor_child(
        child_process=cast(subprocess.Popen[bytes], child),
        process_group_id=123,
        keepalive_fd=-1,
        stop_event=stop_event,
    )

    assert result == 0
    assert child.returncode == 0


class _FakeGuardianProcess:
    """Provide close-traceable guardian stdio for containment-handle tests."""

    def __init__(self, closed_streams: list[str]) -> None:
        self.stdin = _NamedCloser("stdin", closed_streams)
        self.stdout = _NamedCloser("stdout", closed_streams)
        self.stderr = _NamedCloser("stderr", closed_streams)


class _NamedCloser:
    """Record when one guardian stream is explicitly closed."""

    def __init__(self, name: str, closed_streams: list[str]) -> None:
        self._name = name
        self._closed_streams = closed_streams

    def close(self) -> None:
        """Record one close call."""

        self._closed_streams.append(self._name)


def _create_pipe_write_fd() -> int:
    """Return one write file descriptor for containment-handle close tests."""

    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    return write_fd
