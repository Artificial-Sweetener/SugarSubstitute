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

"""Tests for process-aware managed Comfy startup monitoring."""

from __future__ import annotations

from pathlib import Path
from typing import IO

from substitute.application.execution import CancellationSource
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncidentKind
from substitute.infrastructure.comfy.managed_startup_monitor import (
    wait_for_managed_startup_ready,
)


class _FakeProcess:
    """Provide deterministic process poll values for startup monitor tests."""

    def __init__(self, poll_values: tuple[int | None, ...]) -> None:
        """Store the sequence of process states returned by poll."""

        self.pid = 123
        self.stdout: IO[bytes] | None = None
        self._poll_values = list(poll_values)

    def poll(self) -> int | None:
        """Return the next configured process state."""

        if not self._poll_values:
            return None
        return self._poll_values.pop(0)


class _FakeClock:
    """Advance monotonic time through captured sleep requests."""

    def __init__(self) -> None:
        """Start at zero with no recorded sleeps."""

        self.current = 0.0
        self.sleep_delays: list[float] = []

    def monotonic(self) -> float:
        """Return the current fake monotonic time."""

        return self.current

    def sleep(self, delay: float) -> None:
        """Record one sleep and advance fake monotonic time."""

        self.sleep_delays.append(delay)
        self.current += delay


def test_http_ready_before_process_exit_returns_ready() -> None:
    """The startup monitor should prefer successful HTTP readiness."""

    result = wait_for_managed_startup_ready(
        host="127.0.0.1",
        port=8188,
        process=_FakeProcess((None,)),
        workspace=Path("E:/ComfyUI"),
        probe_ready=lambda *, host, port: True,
    )

    assert result.ready is True
    assert result.fatal_incident is None


def test_process_exit_before_http_ready_returns_fatal_incident() -> None:
    """Pre-ready managed process exit should become an immediate fatal result."""

    diagnostics = ComfyStartupDiagnosticsCollector()
    diagnostics.append_output("Traceback (most recent call last):\n")
    diagnostics.append_output("RuntimeError: bad import\n")

    result = wait_for_managed_startup_ready(
        host="127.0.0.1",
        port=8188,
        process=_FakeProcess((1,)),
        workspace=Path("E:/ComfyUI"),
        diagnostics=diagnostics,
        probe_ready=lambda *, host, port: False,
    )

    assert result.ready is False
    assert result.fatal_incident is not None
    assert (
        result.fatal_incident.kind
        is ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY
    )
    assert result.fatal_incident.values["exit_code"] == 1
    assert "RuntimeError: bad import" in result.fatal_incident.log_excerpt


def test_cancellation_token_cancels_without_fatal_incident() -> None:
    """User cancellation should not be reported as a startup failure."""

    cancellation = CancellationSource(generation=1)
    cancellation.cancel(reason="test")

    result = wait_for_managed_startup_ready(
        host="127.0.0.1",
        port=8188,
        process=_FakeProcess((None,)),
        workspace=Path("E:/ComfyUI"),
        cancellation=cancellation,
        probe_ready=lambda *, host, port: False,
    )

    assert result.ready is False
    assert result.canceled is True
    assert result.fatal_incident is None


def test_timeout_returns_fatal_readiness_incident() -> None:
    """Startup timeout should return a fatal readiness timeout incident."""

    clock = _FakeClock()
    status_messages: list[str] = []

    result = wait_for_managed_startup_ready(
        host="127.0.0.1",
        port=8188,
        process=_FakeProcess((None,)),
        workspace=Path("E:/ComfyUI"),
        timeout=1.0,
        on_status=status_messages.append,
        probe_ready=lambda *, host, port: False,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert result.ready is False
    assert result.timed_out is True
    assert result.fatal_incident is not None
    assert result.fatal_incident.kind is ComfyStartupIncidentKind.READINESS_TIMEOUT
    assert result.fatal_incident.values["host"] == "127.0.0.1"
    assert clock.sleep_delays == [0.25, 0.25, 0.25, 0.25]
    assert status_messages == ["Waiting for ComfyUI to become ready..."]


def test_startup_monitor_polls_faster_than_status_messages() -> None:
    """Readiness validation should poll quickly without spamming status output."""

    clock = _FakeClock()
    status_messages: list[str] = []
    probe_results = iter((False, False, False, False, True))

    result = wait_for_managed_startup_ready(
        host="127.0.0.1",
        port=8188,
        process=_FakeProcess((None, None, None, None, None)),
        workspace=Path("E:/ComfyUI"),
        on_status=status_messages.append,
        probe_ready=lambda *, host, port: next(probe_results),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert result.ready is True
    assert clock.sleep_delays == [0.25, 0.25, 0.25, 0.25]
    assert status_messages == ["Waiting for ComfyUI to become ready..."]
