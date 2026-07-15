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

"""Tests for the infrastructure thread-pool execution lane."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
import time
from typing import TypeVar

import pytest

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    ExecutionLaneSaturatedError,
    TaskIdentity,
    TaskRequest,
)
from tests.execution_testing import RecordingDispatcher
from substitute.infrastructure.execution import ThreadPoolExecutionLane

TResult = TypeVar("TResult")


def test_thread_pool_lane_publishes_callbacks_through_dispatcher() -> None:
    """Thread-pool completions should wait for dispatcher delivery."""

    dispatcher = RecordingDispatcher()
    lane = ThreadPoolExecutionLane(
        name="test-lane",
        dispatcher=dispatcher,
        max_workers=1,
        queue_capacity=4,
        thread_name_prefix="test-lane",
    )
    delivered: list[str] = []
    try:
        handle = lane.submit(
            _request(result="done"),
            cancellation=CancellationSource(generation=1),
        )
        handle.add_done_callback(
            lambda outcome: delivered.append(str(outcome.result)),
            reason="test_completion",
        )

        assert _wait_until(lambda: handle.is_finished)
        assert delivered == []
        assert len(dispatcher.callbacks) == 1

        dispatcher.run_all()

        assert delivered == ["done"]
        assert lane.pending_count == 0
        assert handle.outcome is not None
        assert handle.outcome.status == "succeeded"
        assert handle.outcome.timings.queued_age_ms is not None
        assert handle.outcome.timings.run_duration_ms is not None
    finally:
        lane.shutdown(wait=True)


def test_thread_pool_lane_enforces_queue_capacity() -> None:
    """Lane capacity should count running and queued tasks."""

    dispatcher = RecordingDispatcher()
    lane = ThreadPoolExecutionLane(
        name="limited-lane",
        dispatcher=dispatcher,
        max_workers=1,
        queue_capacity=1,
        thread_name_prefix="limited-lane",
    )
    started = Event()
    release = Event()
    try:
        lane.submit(
            _blocking_request(started=started, release=release),
            cancellation=CancellationSource(generation=1),
        )
        assert started.wait(1.0)

        with pytest.raises(
            ExecutionLaneSaturatedError, match="queue is full"
        ) as caught:
            lane.submit(
                _request(request_id=2, result="second"),
                cancellation=CancellationSource(generation=2),
            )
        assert caught.value.lane_name == "limited-lane"
        assert caught.value.queue_capacity == 1
    finally:
        release.set()
        assert _wait_until(lambda: lane.pending_count == 0)
        lane.shutdown(wait=True)


def test_thread_pool_lane_cancel_before_start_finishes_cancelled() -> None:
    """Cancelling queued work should publish a cancelled outcome."""

    dispatcher = RecordingDispatcher()
    lane = ThreadPoolExecutionLane(
        name="cancel-lane",
        dispatcher=dispatcher,
        max_workers=1,
        queue_capacity=2,
        thread_name_prefix="cancel-lane",
    )
    first_started = Event()
    first_release = Event()
    try:
        first_handle = lane.submit(
            _blocking_request(started=first_started, release=first_release),
            cancellation=CancellationSource(generation=1),
        )
        assert first_started.wait(1.0)
        second_handle = lane.submit(
            _request(request_id=2, result="second"),
            cancellation=CancellationSource(generation=2),
        )

        second_handle.cancel(reason="no_longer_current")

        assert _wait_until(lambda: second_handle.is_finished)
        assert second_handle.outcome is not None
        assert second_handle.outcome.status == "cancelled"
        assert second_handle.outcome.cancellation_reason == "no_longer_current"
    finally:
        first_release.set()
        assert _wait_until(lambda: first_handle.is_finished)
        lane.shutdown(wait=True)


def test_thread_pool_lane_returns_failed_outcome_without_raising() -> None:
    """Worker exceptions should become failed outcomes."""

    dispatcher = RecordingDispatcher()
    lane = ThreadPoolExecutionLane(
        name="failure-lane",
        dispatcher=dispatcher,
        max_workers=1,
        queue_capacity=None,
        thread_name_prefix="failure-lane",
    )
    try:
        handle = lane.submit(
            _failing_request(),
            cancellation=CancellationSource(generation=1),
        )

        assert _wait_until(lambda: handle.is_finished)

        assert handle.outcome is not None
        assert handle.outcome.status == "failed"
        assert isinstance(handle.outcome.error, RuntimeError)
    finally:
        lane.shutdown(wait=True)


def _request(
    *,
    request_id: int = 1,
    result: TResult,
) -> TaskRequest[TResult]:
    """Build a successful test request."""

    return TaskRequest(
        identity=TaskIdentity(request_id=request_id, domain="test", parts=()),
        context=ExecutionContext(
            operation="test_operation",
            reason="test_reason",
            lane="test-lane",
        ),
        work=lambda _token: result,
    )


def _blocking_request(*, started: Event, release: Event) -> TaskRequest[str]:
    """Build a request that blocks until released by the test."""

    def work(_token: object) -> str:
        """Signal start and wait for release."""

        started.set()
        release.wait(1.0)
        return "released"

    return TaskRequest(
        identity=TaskIdentity(request_id=1, domain="test", parts=()),
        context=ExecutionContext(
            operation="blocking_operation",
            reason="test_reason",
            lane="test-lane",
        ),
        work=work,
    )


def _failing_request() -> TaskRequest[str]:
    """Build a request that raises during worker execution."""

    def work(_token: object) -> str:
        """Raise a deterministic worker error."""

        raise RuntimeError("boom")

    return TaskRequest(
        identity=TaskIdentity(request_id=1, domain="test", parts=()),
        context=ExecutionContext(
            operation="failing_operation",
            reason="test_reason",
            lane="test-lane",
        ),
        work=work,
    )


def _wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 1.0,
) -> bool:
    """Poll a predicate until it returns true or the timeout expires."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()
