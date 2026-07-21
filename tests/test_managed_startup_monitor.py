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

import pytest

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.execution import CancellationSource
from substitute.application.managed_startup_progress import (
    managed_startup_progress_text,
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


def test_live_process_waits_beyond_five_minutes_until_user_cancels() -> None:
    """Elapsed time alone should never terminate a live managed Comfy process."""

    clock = _FakeClock()
    cancellation = CancellationSource(generation=1)
    progress_messages: list[str] = []

    def advance_startup(_delay: float) -> None:
        """Advance one simulated minute and cancel after six minutes."""

        clock.sleep_delays.append(_delay)
        clock.current += 60.0
        if clock.current >= 360.0:
            cancellation.cancel(reason="test")

    result = wait_for_managed_startup_ready(
        host="127.0.0.1",
        port=8188,
        process=_FakeProcess((None,)),
        workspace=Path("E:/ComfyUI"),
        on_progress=progress_messages.append,
        cancellation=cancellation,
        probe_ready=lambda *, host, port: False,
        sleep=advance_startup,
        monotonic=clock.monotonic,
    )

    assert result.ready is False
    assert result.canceled is True
    assert result.fatal_incident is None
    assert clock.current == 360.0
    assert progress_messages[-1] == (
        "Still waiting—custom nodes, slow storage, or a startup issue may be "
        "delaying ComfyUI."
    )


def test_startup_monitor_polls_faster_than_status_messages() -> None:
    """Readiness validation should poll quickly without spamming status output."""

    clock = _FakeClock()
    progress_messages: list[str] = []
    probe_results = iter((False, False, False, False, True))

    result = wait_for_managed_startup_ready(
        host="127.0.0.1",
        port=8188,
        process=_FakeProcess((None, None, None, None, None)),
        workspace=Path("E:/ComfyUI"),
        on_progress=progress_messages.append,
        probe_ready=lambda *, host, port: next(probe_results),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert result.ready is True
    assert clock.sleep_delays == [0.25, 0.25, 0.25, 0.25]
    assert progress_messages == [
        managed_startup_progress_text(elapsed_seconds=0.0, animation_frame=0)
    ]


@pytest.mark.parametrize(
    ("elapsed_seconds", "animation_frame", "expected"),
    (
        (0.0, 0, "Waiting for ComfyUI to become ready."),
        (1.0, 1, "Waiting for ComfyUI to become ready.."),
        (2.0, 2, "Waiting for ComfyUI to become ready..."),
        (120.0, 3, "ComfyUI is taking longer than usual…"),
        (
            300.0,
            4,
            "Still waiting—custom nodes, slow storage, or a startup issue may be "
            "delaying ComfyUI.",
        ),
    ),
)
def test_managed_startup_progress_copy_escalates_at_owned_milestones(
    elapsed_seconds: float,
    animation_frame: int,
    expected: str,
) -> None:
    """Progress copy should animate concisely before escalating at 120 and 300 seconds."""

    message = managed_startup_progress_text(
        elapsed_seconds=elapsed_seconds,
        animation_frame=animation_frame,
    )

    assert render_source_application_text(message) == expected
