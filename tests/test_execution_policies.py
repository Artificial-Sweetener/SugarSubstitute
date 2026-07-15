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

"""Test reusable execution policies and deterministic adapters."""

from __future__ import annotations

import logging
from threading import Event, Thread
from typing import cast

import pytest

from substitute.application.execution import (
    BlockingSingleFlight,
    BoundedTaskQueue,
    CancellationController,
    CancellationSource,
    ExecutionContext,
    FireAndLogSubmitter,
    KeyedSingleFlight,
    LatestWinsRequestChannel,
    ScopedKeyedSingleFlight,
    SerialTaskGate,
    SingleFlightCancelled,
    TaskIdentity,
    TaskRequest,
)
from tests.execution_testing import (
    ImmediateTaskSubmitter,
    ManualTaskHandle,
    QueuedTaskSubmitter,
    never_cancelled,
)


def _request(request_id: int = 1, result: str = "done") -> TaskRequest[str]:
    """Build one policy test request."""

    return TaskRequest(
        identity=TaskIdentity(request_id=request_id, domain="settings"),
        context=ExecutionContext(operation="load", reason="refresh", lane="settings"),
        work=lambda _token: result,
    )


def test_latest_wins_cancels_previous_handle() -> None:
    """Supersede older active work when a newer request arrives."""

    submitter = QueuedTaskSubmitter()
    channel: LatestWinsRequestChannel[str] = LatestWinsRequestChannel(
        submitter=submitter,
        cancellation_controller=CancellationController(),
    )

    first = cast(ManualTaskHandle[str], channel.submit_latest(_request(request_id=1)))
    second = channel.submit_latest(_request(request_id=2))

    assert first.outcome is not None
    assert first.outcome.status == "cancelled"
    assert second.identity.request_id == 2
    assert second.identity.cancellation_generation == 2
    assert submitter.cancellations[0].is_cancelled is True


def test_latest_wins_clears_active_handle_on_completion() -> None:
    """Drop active state once the current request finishes."""

    submitter = QueuedTaskSubmitter()
    channel: LatestWinsRequestChannel[str] = LatestWinsRequestChannel(
        submitter=submitter
    )

    handle = cast(ManualTaskHandle[str], channel.submit_latest(_request()))
    handle.complete_success("done")

    assert channel.active_handle is None


def test_keyed_single_flight_reuses_active_handle() -> None:
    """Coalesce duplicate keyed work onto one active handle."""

    submitter = QueuedTaskSubmitter()
    single_flight: KeyedSingleFlight[str, str] = KeyedSingleFlight(submitter=submitter)

    first = cast(
        ManualTaskHandle[str],
        single_flight.submit("pack", _request(1), cancellation=never_cancelled()),
    )
    second = single_flight.submit("pack", _request(2), cancellation=never_cancelled())

    assert second is first
    assert single_flight.active_keys == ("pack",)
    first.complete_success("done")
    assert len(single_flight.active_keys) == 0


def test_scoped_keyed_single_flight_cancels_active_work() -> None:
    """Coalesce duplicate keyed work and cancel it from the owner scope."""

    submitter = QueuedTaskSubmitter()
    single_flight: ScopedKeyedSingleFlight[str, str] = ScopedKeyedSingleFlight(
        submitter=submitter
    )

    first = cast(ManualTaskHandle[str], single_flight.submit("pack", _request(1)))
    second = single_flight.submit("pack", _request(2))
    assert second is first
    assert first.identity.cancellation_generation == 1
    assert submitter.cancellations[0].is_cancelled is False

    single_flight.cancel_all(reason="owner_shutdown")

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "owner_shutdown"
    assert first.cancel_reason == "owner_shutdown"
    assert single_flight.active_keys == ()


def test_blocking_single_flight_reuses_owner_result() -> None:
    """Share one synchronous owner result with a duplicate caller."""

    single_flight: BlockingSingleFlight[str, str] = BlockingSingleFlight()
    started = Event()
    waiter_joined = Event()
    release = Event()
    calls: list[str] = []
    results: list[str] = []
    errors: list[BaseException] = []

    def owner_work() -> str:
        """Block owner work until the duplicate caller joins."""

        calls.append("owner")
        started.set()
        assert release.wait(timeout=5)
        return "loaded"

    def duplicate_work() -> str:
        """Fail the test if duplicate callers run work."""

        raise AssertionError("duplicate work should not run")

    def run_owner() -> None:
        """Run owner work in a background thread."""

        try:
            results.append(single_flight.run("asset", owner_work))
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)

    def run_duplicate() -> None:
        """Wait for the owner result from a duplicate thread."""

        try:
            results.append(
                single_flight.run(
                    "asset",
                    duplicate_work,
                    on_wait=waiter_joined.set,
                )
            )
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)

    owner = Thread(target=run_owner, name="single-flight-owner")
    duplicate = Thread(target=run_duplicate, name="single-flight-duplicate")
    owner.start()
    assert started.wait(timeout=5)
    duplicate.start()
    assert waiter_joined.wait(timeout=5)
    release.set()
    owner.join(timeout=5)
    duplicate.join(timeout=5)

    assert not owner.is_alive()
    assert not duplicate.is_alive()
    if errors:
        raise AssertionError(errors) from errors[0]
    assert calls == ["owner"]
    assert sorted(results) == ["loaded", "loaded"]
    assert single_flight.active_count == 0


def test_blocking_single_flight_propagates_owner_failure() -> None:
    """Publish owner failures to duplicate callers and clear active state."""

    single_flight: BlockingSingleFlight[str, str] = BlockingSingleFlight()
    started = Event()
    waiter_joined = Event()
    release = Event()
    errors: list[BaseException] = []

    def owner_work() -> str:
        """Raise after a duplicate caller is waiting."""

        started.set()
        assert release.wait(timeout=5)
        raise RuntimeError("load failed")

    def run_owner() -> None:
        """Capture the owner failure."""

        try:
            single_flight.run("asset", owner_work)
        except BaseException as error:
            errors.append(error)

    def run_duplicate() -> None:
        """Capture the duplicate failure."""

        try:
            single_flight.run(
                "asset",
                lambda: "unexpected",
                on_wait=waiter_joined.set,
            )
        except BaseException as error:
            errors.append(error)

    owner = Thread(target=run_owner, name="single-flight-failing-owner")
    duplicate = Thread(target=run_duplicate, name="single-flight-failing-duplicate")
    owner.start()
    assert started.wait(timeout=5)
    duplicate.start()
    assert waiter_joined.wait(timeout=5)
    release.set()
    owner.join(timeout=5)
    duplicate.join(timeout=5)

    assert not owner.is_alive()
    assert not duplicate.is_alive()
    assert len(errors) == 2
    assert all(isinstance(error, RuntimeError) for error in errors)
    assert {str(error) for error in errors} == {"load failed"}
    assert single_flight.active_count == 0


def test_blocking_single_flight_waiter_observes_cancellation() -> None:
    """Let duplicate waiters abandon shared work when cancellation is requested."""

    single_flight: BlockingSingleFlight[str, str] = BlockingSingleFlight()
    started = Event()
    release = Event()
    source = CancellationSource(generation=1)
    errors: list[BaseException] = []

    def owner_work() -> str:
        """Keep owner work active while the waiter observes cancellation."""

        started.set()
        assert release.wait(timeout=5)
        return "loaded"

    def run_owner() -> None:
        """Run cancellable owner work in a background thread."""

        try:
            single_flight.run("asset", owner_work)
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)

    owner = Thread(target=run_owner, name="single-flight-cancel-owner")
    owner.start()
    assert started.wait(timeout=5)
    source.cancel(reason="test_cancel")

    with pytest.raises(SingleFlightCancelled) as raised:
        single_flight.run(
            "asset",
            lambda: "unexpected",
            cancellation=source,
        )

    release.set()
    owner.join(timeout=5)

    assert raised.value.reason == "test_cancel"
    assert not owner.is_alive()
    if errors:
        raise AssertionError(errors) from errors[0]
    assert single_flight.active_count == 0


def test_serial_task_gate_preserves_order() -> None:
    """Queue later keys while one serial task is active."""

    gate = SerialTaskGate()

    assert gate.request_start("first") is True
    assert gate.request_start("second") is False
    assert gate.request_start("third") is False
    assert gate.finish_and_take_next() == "second"
    assert gate.finish_and_take_next() == "third"
    assert gate.finish_and_take_next() is None
    assert gate.is_active is False


def test_bounded_task_queue_rejects_over_capacity() -> None:
    """Reject queued work after capacity is reached."""

    queue: BoundedTaskQueue[str] = BoundedTaskQueue(capacity=1)

    assert queue.try_push("first") is True
    assert queue.try_push("second") is False
    assert queue.pop_next() == "first"
    assert queue.pop_next() is None


def test_immediate_submitter_returns_settled_success() -> None:
    """Run work synchronously in tests."""

    handle = ImmediateTaskSubmitter().submit(_request(), cancellation=never_cancelled())

    assert handle.outcome is not None
    assert handle.outcome.status == "succeeded"
    assert handle.outcome.result == "done"


def test_immediate_submitter_returns_settled_failure() -> None:
    """Convert raised errors into failed task outcomes."""

    def fail(_token: object) -> str:
        raise RuntimeError("boom")

    handle = ImmediateTaskSubmitter().submit(
        TaskRequest(
            identity=TaskIdentity(request_id=1, domain="settings"),
            context=ExecutionContext(
                operation="load",
                reason="refresh",
                lane="settings",
            ),
            work=fail,
        ),
        cancellation=never_cancelled(),
    )

    assert handle.outcome is not None
    assert handle.outcome.status == "failed"
    assert isinstance(handle.outcome.error, RuntimeError)


def test_bounded_task_queue_rejects_invalid_capacity() -> None:
    """Require a positive queue capacity."""

    with pytest.raises(ValueError, match="capacity"):
        BoundedTaskQueue[str](capacity=0)


def test_fire_and_log_submitter_logs_failures(caplog: pytest.LogCaptureFixture) -> None:
    """Log failed best-effort work without changing handle outcome."""

    def fail(_token: object) -> str:
        raise RuntimeError("boom")

    logger = logging.getLogger("tests.execution.fire_and_log")
    submitter = FireAndLogSubmitter(
        submitter=ImmediateTaskSubmitter(),
        logger=logger,
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        handle = submitter.submit(
            TaskRequest(
                identity=TaskIdentity(request_id=1, domain="settings"),
                context=ExecutionContext(
                    operation="load",
                    reason="refresh",
                    lane="settings",
                ),
                work=fail,
            ),
            cancellation=never_cancelled(),
        )

    assert handle.outcome is not None
    assert handle.outcome.status == "failed"
    assert "Best-effort execution task failed" in caplog.text
