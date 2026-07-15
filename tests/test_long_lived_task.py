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

"""Tests for the long-lived execution task handle."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
import time

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from tests.execution_testing import RecordingDispatcher
from substitute.infrastructure.execution import LongLivedTaskHandle


def test_long_lived_task_stop_cancels_and_dispatches_terminal_outcome() -> None:
    """Stopping a long-lived task should cancel, close, join, and publish."""

    dispatcher = RecordingDispatcher()
    started = Event()
    close_calls: list[str] = []
    delivered: list[str] = []

    def work(source: CancellationSource) -> str:
        """Run until cancellation is requested."""

        started.set()
        while not source.is_cancelled:
            time.sleep(0.005)
        return "stopped"

    handle = _handle(
        work=work,
        dispatcher=dispatcher,
        close_hook=lambda: close_calls.append("closed"),
    )
    handle.add_done_callback(
        lambda outcome: delivered.append(outcome.status),
        reason="test_completion",
    )

    assert started.wait(1.0)
    handle.stop(reason="owner_closed")

    assert _wait_until(lambda: handle.is_finished)
    assert close_calls == ["closed"]
    assert delivered == []
    assert handle.outcome is not None
    assert handle.outcome.status == "cancelled"
    assert handle.outcome.cancellation_reason == "owner_closed"

    dispatcher.run_all()

    assert delivered == ["cancelled"]
    assert not handle.late_stop


def test_long_lived_task_records_late_stop_before_eventual_completion() -> None:
    """A task that misses its join timeout should expose late-stop state."""

    dispatcher = RecordingDispatcher()
    started = Event()
    release = Event()

    def work(_source: CancellationSource) -> str:
        """Ignore cancellation until the test releases this worker."""

        started.set()
        release.wait(1.0)
        return "late"

    handle = _handle(
        work=work,
        dispatcher=dispatcher,
        join_timeout_seconds=0.01,
    )

    assert started.wait(1.0)
    handle.stop(reason="shutdown")

    assert handle.late_stop
    assert not handle.is_finished

    release.set()

    assert _wait_until(lambda: handle.is_finished)
    assert handle.outcome is not None
    assert handle.outcome.status == "cancelled"


def _handle(
    *,
    work: Callable[[CancellationSource], str],
    dispatcher: RecordingDispatcher,
    close_hook: Callable[[], None] | None = None,
    join_timeout_seconds: float = 1.0,
) -> LongLivedTaskHandle[str]:
    """Create a long-lived task handle for tests."""

    return LongLivedTaskHandle(
        identity=TaskIdentity(
            request_id=1,
            domain="listener",
            parts=(),
            cancellation_generation=1,
        ),
        context=ExecutionContext(
            operation="listen",
            reason="test_reason",
            lane="listener-lane",
        ),
        work=work,
        dispatcher=dispatcher,
        close_hook=close_hook,
        join_timeout_seconds=join_timeout_seconds,
        thread_name="test-long-lived",
    )


def _wait_until(predicate: Callable[[], bool], *, timeout_seconds: float = 1.0) -> bool:
    """Poll a predicate until it returns true or the timeout expires."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()
