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

"""Run bounded execution requests on a named thread-pool lane."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
import logging
from threading import Lock
import time
from typing import Generic, Protocol, TypeVar

from substitute.application.execution import (
    CancellationToken,
    ExecutionLane,
    ExecutionLaneSaturatedError,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskTimings,
)

TResult = TypeVar("TResult")
DispatcherFactory = Callable[[TaskRequest[object]], "CompletionDispatcher"]


class CompletionDispatcher(Protocol):
    """Publish completion callbacks through an owner-thread boundary."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Queue one completion callback for owner-thread delivery."""


class ThreadPoolExecutionLane(ExecutionLane):
    """Submit bounded short-running work to a named thread pool."""

    def __init__(
        self,
        *,
        name: str,
        max_workers: int,
        queue_capacity: int | None,
        thread_name_prefix: str,
        dispatcher: CompletionDispatcher | None = None,
        dispatcher_factory: DispatcherFactory | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Create a bounded thread-pool lane."""

        _require_non_blank(name, field_name="name")
        _require_non_blank(thread_name_prefix, field_name="thread_name_prefix")
        _require_positive(max_workers, field_name="max_workers")
        _require_optional_positive(queue_capacity, field_name="queue_capacity")
        if (dispatcher is None) == (dispatcher_factory is None):
            raise ValueError(
                "exactly one of dispatcher or dispatcher_factory must be supplied."
            )
        self._name = name
        self._dispatcher = dispatcher
        self._dispatcher_factory = dispatcher_factory
        self._max_workers = max_workers
        self._queue_capacity = queue_capacity
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._logger = logger or logging.getLogger(__name__)
        self._pending_count = 0
        self._is_shutdown = False
        self._lock = Lock()

    @property
    def name(self) -> str:
        """Return the configured lane name."""

        return self._name

    @property
    def queue_capacity(self) -> int | None:
        """Return the configured maximum pending count."""

        return self._queue_capacity

    @property
    def pending_count(self) -> int:
        """Return queued plus running work currently owned by this lane."""

        with self._lock:
            return self._pending_count

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit one request and return a dispatcher-backed handle."""

        queued_at = time.monotonic()
        execution_state = _ThreadPoolTaskState()
        dispatcher = self._dispatcher_for_request(request)
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError(f"Execution lane {self._name} is shut down.")
            if (
                self._queue_capacity is not None
                and self._pending_count >= self._queue_capacity
            ):
                raise ExecutionLaneSaturatedError(
                    lane_name=self._name,
                    queue_capacity=self._queue_capacity,
                )
            self._pending_count += 1

        try:
            future = self._executor.submit(
                self._run_request,
                request,
                cancellation,
                execution_state,
                queued_at,
            )
        except BaseException:
            self._decrement_pending()
            raise

        return _ThreadPoolTaskHandle(
            request=request,
            future=future,
            dispatcher=dispatcher,
            execution_state=execution_state,
            on_finished=self._decrement_pending,
            logger=self._logger,
        )

    def shutdown(
        self,
        *,
        wait: bool = False,
        cancel_futures: bool = True,
    ) -> None:
        """Stop accepting work and release the underlying executor."""

        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def _run_request(
        self,
        request: TaskRequest[TResult],
        cancellation: CancellationToken,
        execution_state: "_ThreadPoolTaskState",
        queued_at: float,
    ) -> TaskOutcome[TResult]:
        """Run one request and translate completion into a task outcome."""

        cancel_reason = execution_state.cancel_reason
        if cancel_reason is not None:
            completed_at = time.monotonic()
            return _cancelled_outcome(
                request=request,
                reason=cancel_reason,
                queued_at=queued_at,
                started_at=None,
                completed_at=completed_at,
            )
        if cancellation.is_cancelled:
            completed_at = time.monotonic()
            return _cancelled_outcome(
                request=request,
                reason=cancellation.reason or "cancelled",
                queued_at=queued_at,
                started_at=None,
                completed_at=completed_at,
            )

        started_at = time.monotonic()
        execution_state.mark_started()
        try:
            result = request.work(cancellation)
        except BaseException as error:  # noqa: BLE001
            completed_at = time.monotonic()
            return TaskOutcome(
                identity=request.identity,
                context=request.context,
                status="failed",
                error=error,
                timings=TaskTimings(
                    queued_at=queued_at,
                    started_at=started_at,
                    completed_at=completed_at,
                ),
            )

        completed_at = time.monotonic()
        cancel_reason = execution_state.cancel_reason
        if cancel_reason is not None or cancellation.is_cancelled:
            return _cancelled_outcome(
                request=request,
                reason=cancel_reason or cancellation.reason or "cancelled",
                queued_at=queued_at,
                started_at=started_at,
                completed_at=completed_at,
            )
        return TaskOutcome(
            identity=request.identity,
            context=request.context,
            status="succeeded",
            result=result,
            timings=TaskTimings(
                queued_at=queued_at,
                started_at=started_at,
                completed_at=completed_at,
            ),
        )

    def _decrement_pending(self) -> None:
        """Record that one submitted task no longer occupies the lane."""

        with self._lock:
            if self._pending_count > 0:
                self._pending_count -= 1

    def _dispatcher_for_request(
        self,
        request: TaskRequest[TResult],
    ) -> CompletionDispatcher:
        """Resolve the completion dispatcher for one submitted request."""

        if self._dispatcher is not None:
            return self._dispatcher
        if self._dispatcher_factory is None:
            raise RuntimeError(f"Execution lane {self._name} has no dispatcher.")
        return self._dispatcher_factory(_as_object_request(request))


class _ThreadPoolTaskHandle(Generic[TResult]):
    """Track one future-backed thread-pool task."""

    def __init__(
        self,
        *,
        request: TaskRequest[TResult],
        future: Future[TaskOutcome[TResult]],
        dispatcher: CompletionDispatcher,
        execution_state: "_ThreadPoolTaskState",
        on_finished: Callable[[], None],
        logger: logging.Logger,
    ) -> None:
        """Attach completion handling to the supplied future."""

        self._request = request
        self._future = future
        self._dispatcher = dispatcher
        self._execution_state = execution_state
        self._on_finished = on_finished
        self._logger = logger
        self._outcome: TaskOutcome[TResult] | None = None
        self._callbacks: list[tuple[Callable[[TaskOutcome[TResult]], None], str]] = []
        self._lock = Lock()
        self._future.add_done_callback(self._finish)

    @property
    def identity(self) -> TaskIdentity:
        """Return the identity associated with this submitted task."""

        return self._request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether the task has settled."""

        with self._lock:
            return self._outcome is not None

    @property
    def outcome(self) -> TaskOutcome[TResult] | None:
        """Return the completed task outcome when available."""

        with self._lock:
            return self._outcome

    @property
    def state(self) -> str:
        """Return task state for diagnostics and tests."""

        with self._lock:
            outcome = self._outcome
        if outcome is not None:
            return outcome.status
        if self._future.cancelled():
            return "cancelled"
        if self._execution_state.started:
            return "running"
        return "pending"

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Publish one callback through the configured dispatcher."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            outcome = self._outcome
            if outcome is None:
                self._callbacks.append((callback, reason))
                return
        self._publish_callback(callback, reason=reason, outcome=outcome)

    def cancel(self, *, reason: str) -> None:
        """Request cancellation of this task."""

        _require_non_blank(reason, field_name="reason")
        self._execution_state.request_cancel(reason=reason)
        self._future.cancel()

    def _finish(self, future: Future[TaskOutcome[TResult]]) -> None:
        """Build and publish one terminal outcome."""

        try:
            outcome = self._future_outcome(future)
            with self._lock:
                if self._outcome is not None:
                    return
                self._outcome = outcome
                callbacks = tuple(self._callbacks)
                self._callbacks.clear()
            self._log_outcome(outcome)
            for callback, reason in callbacks:
                self._publish_callback(callback, reason=reason, outcome=outcome)
        finally:
            self._on_finished()

    def _future_outcome(
        self,
        future: Future[TaskOutcome[TResult]],
    ) -> TaskOutcome[TResult]:
        """Return the outcome represented by the completed future."""

        if future.cancelled():
            return _cancelled_outcome(
                request=self._request,
                reason=self._execution_state.cancel_reason or "cancelled",
                queued_at=None,
                started_at=None,
                completed_at=time.monotonic(),
            )
        return future.result()

    def _publish_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
        outcome: TaskOutcome[TResult],
    ) -> None:
        """Queue one completion callback through the owner dispatcher."""

        self._dispatcher.publish(lambda: callback(outcome), reason=reason)

    def _log_outcome(self, outcome: TaskOutcome[TResult]) -> None:
        """Log one task completion with safe execution context."""

        extra = {
            "operation": outcome.context.operation,
            "reason": outcome.context.reason,
            "lane": outcome.context.lane,
            "request_id": outcome.identity.request_id,
            "queued_age_ms": outcome.timings.queued_age_ms,
            "run_duration_ms": outcome.timings.run_duration_ms,
            "status": outcome.status,
            "cancellation_reason": outcome.cancellation_reason,
        }
        if outcome.status == "failed":
            self._logger.error(
                "Execution task failed.",
                extra=extra,
                exc_info=outcome.error,
            )
        else:
            self._logger.debug("Execution task completed.", extra=extra)


class _ThreadPoolTaskState:
    """Share mutable task state between a handle and worker wrapper."""

    def __init__(self) -> None:
        """Create an uncancelled pending state."""

        self._started = False
        self._cancel_reason: str | None = None
        self._lock = Lock()

    @property
    def started(self) -> bool:
        """Return whether worker execution has begun."""

        with self._lock:
            return self._started

    @property
    def cancel_reason(self) -> str | None:
        """Return the requested cancellation reason when one exists."""

        with self._lock:
            return self._cancel_reason

    def mark_started(self) -> None:
        """Record worker start."""

        with self._lock:
            self._started = True

    def request_cancel(self, *, reason: str) -> None:
        """Record the first cancellation reason."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            if self._cancel_reason is None:
                self._cancel_reason = reason


def _cancelled_outcome(
    *,
    request: TaskRequest[TResult],
    reason: str,
    queued_at: float | None,
    started_at: float | None,
    completed_at: float | None,
) -> TaskOutcome[TResult]:
    """Build a cancelled outcome for one request."""

    return TaskOutcome(
        identity=request.identity,
        context=request.context,
        status="cancelled",
        cancellation_reason=reason,
        timings=TaskTimings(
            queued_at=queued_at,
            started_at=started_at,
            completed_at=completed_at,
        ),
    )


def _as_object_request(request: TaskRequest[TResult]) -> TaskRequest[object]:
    """Return a task request widened for dispatcher lookup."""

    return request  # type: ignore[return-value]


def _require_positive(value: int, *, field_name: str) -> None:
    """Reject non-positive lane settings."""

    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def _require_optional_positive(value: int | None, *, field_name: str) -> None:
    """Reject non-positive optional lane settings."""

    if value is not None:
        _require_positive(value, field_name=field_name)


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank lane labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "CompletionDispatcher",
    "DispatcherFactory",
    "ThreadPoolExecutionLane",
]
