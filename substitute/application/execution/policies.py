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

"""Provide reusable execution submission policies."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Hashable
from dataclasses import dataclass
import logging
from threading import Condition, Lock, RLock
from typing import Generic, TypeVar, cast

from .cancellation import CancellationController, CancellationSource, CancellationToken
from .executor import TaskHandle, TaskRequest, TaskSubmitter
from .outcome import TaskOutcome

TResult = TypeVar("TResult")
TKey = TypeVar("TKey", bound=Hashable)
TItem = TypeVar("TItem")

_SUPERSEDED_REASON = "superseded_by_latest_request"
_COMPLETED_REASON = "execution_policy_completed"
_BLOCKING_SINGLE_FLIGHT_WAIT_SECONDS = 0.05


class SingleFlightCancelled(RuntimeError):
    """Report that a caller stopped waiting for shared single-flight work."""

    def __init__(self, reason: str) -> None:
        """Store the execution-layer cancellation reason."""

        super().__init__(f"Single-flight wait cancelled: {reason}")
        self.reason = reason


@dataclass(slots=True)
class _BlockingSingleFlightCall(Generic[TResult]):
    """Store one blocking single-flight result shared by duplicate callers."""

    condition: Condition
    completed: bool = False
    result: TResult | None = None
    error: BaseException | None = None


class LatestWinsRequestChannel(Generic[TResult]):
    """Submit only the most recent request as active work."""

    def __init__(
        self,
        *,
        submitter: TaskSubmitter,
        cancellation_controller: CancellationController | None = None,
    ) -> None:
        """Store submission and cancellation collaborators."""

        self._submitter = submitter
        self._cancellation_controller = (
            cancellation_controller or CancellationController()
        )
        self._active_source: CancellationSource | None = None
        self._active_handle: TaskHandle[TResult] | None = None
        self._lock = Lock()

    @property
    def active_handle(self) -> TaskHandle[TResult] | None:
        """Return the active handle for tests and lifecycle owners."""

        with self._lock:
            return self._active_handle

    def submit_latest(self, request: TaskRequest[TResult]) -> TaskHandle[TResult]:
        """Submit one request after cancelling the previous active request."""

        source = self._cancellation_controller.next_source()
        request_with_generation = TaskRequest(
            identity=request.identity.with_cancellation_generation(source.generation),
            context=request.context,
            work=request.work,
        )
        with self._lock:
            previous_source = self._active_source
            previous_handle = self._active_handle
            self._active_source = source
            self._active_handle = None
        _cancel_pair(
            source=previous_source,
            handle=previous_handle,
            reason=_SUPERSEDED_REASON,
        )
        handle = self._submitter.submit(
            request_with_generation,
            cancellation=source,
        )
        with self._lock:
            if self._active_source is not source:
                handle.cancel(reason=_SUPERSEDED_REASON)
                return handle
            self._active_handle = handle
        handle.add_done_callback(
            self._clear_if_current(handle),
            reason=_COMPLETED_REASON,
        )
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Cancel the active source and handle."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            source = self._active_source
            handle = self._active_handle
            self._active_source = None
            self._active_handle = None
        _cancel_pair(source=source, handle=handle, reason=reason)

    def _clear_if_current(
        self,
        handle: TaskHandle[TResult],
    ) -> Callable[[TaskOutcome[TResult]], None]:
        """Return a callback that clears active state only for this handle."""

        def clear(_outcome: TaskOutcome[TResult]) -> None:
            """Clear active state when this handle is still current."""

            with self._lock:
                if self._active_handle is not handle:
                    return
                self._active_handle = None
                self._active_source = None

        return clear


class KeyedSingleFlight(Generic[TKey, TResult]):
    """Coalesce duplicate keyed requests onto the active handle for that key."""

    def __init__(self, *, submitter: TaskSubmitter) -> None:
        """Store the submitter used for first requests per key."""

        self._submitter = submitter
        self._active: dict[TKey, TaskHandle[TResult]] = {}
        self._lock = Lock()

    def submit(
        self,
        key: TKey,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit the request only when no unfinished handle exists for the key."""

        with self._lock:
            existing = self._active.get(key)
            if existing is not None and not existing.is_finished:
                return existing
            handle = self._submitter.submit(request, cancellation=cancellation)
            self._active[key] = handle
        handle.add_done_callback(
            self._clear_if_current(key, handle),
            reason=_COMPLETED_REASON,
        )
        return handle

    @property
    def active_keys(self) -> tuple[TKey, ...]:
        """Return keys with active unfinished work."""

        with self._lock:
            return tuple(self._active)

    def _clear_if_current(
        self,
        key: TKey,
        handle: TaskHandle[TResult],
    ) -> Callable[[TaskOutcome[TResult]], None]:
        """Return a callback that clears the key when this handle finishes."""

        def clear(_outcome: TaskOutcome[TResult]) -> None:
            """Remove this key only if it still points at this handle."""

            with self._lock:
                if self._active.get(key) is handle:
                    del self._active[key]

        return clear


class ScopedKeyedSingleFlight(Generic[TKey, TResult]):
    """Coalesce keyed requests while owning cancellation for active work."""

    def __init__(
        self,
        *,
        submitter: TaskSubmitter,
        cancellation_controller: CancellationController | None = None,
    ) -> None:
        """Create a keyed single-flight policy for one owner lifetime."""

        self._submitter = submitter
        self._cancellation_controller = (
            cancellation_controller or CancellationController()
        )
        self._active: dict[
            TKey,
            tuple[TaskHandle[TResult], CancellationSource],
        ] = {}
        self._lock = Lock()

    @property
    def active_keys(self) -> tuple[TKey, ...]:
        """Return keys with active unfinished work."""

        with self._lock:
            return tuple(self._active)

    def submit(
        self,
        key: TKey,
        request: TaskRequest[TResult],
    ) -> TaskHandle[TResult]:
        """Submit one request when no unfinished handle exists for the key."""

        with self._lock:
            existing = self._active.get(key)
            if existing is not None and not existing[0].is_finished:
                return existing[0]
            source = self._cancellation_controller.next_source()
        scoped_request = TaskRequest(
            identity=request.identity.with_cancellation_generation(source.generation),
            context=request.context,
            work=request.work,
        )
        handle = self._submitter.submit(scoped_request, cancellation=source)
        with self._lock:
            existing = self._active.get(key)
            if existing is not None and not existing[0].is_finished:
                source.cancel(reason=_SUPERSEDED_REASON)
                handle.cancel(reason=_SUPERSEDED_REASON)
                return existing[0]
            self._active[key] = (handle, source)
        handle.add_done_callback(
            self._clear_if_current(key, handle),
            reason=_COMPLETED_REASON,
        )
        return handle

    def cancel_all(self, *, reason: str) -> None:
        """Cancel all active single-flight work."""

        _require_non_blank(reason, field_name="reason")
        with self._lock:
            active = tuple(self._active.values())
            self._active.clear()
        for handle, source in active:
            source.cancel(reason=reason)
            handle.cancel(reason=reason)

    def _clear_if_current(
        self,
        key: TKey,
        handle: TaskHandle[TResult],
    ) -> Callable[[TaskOutcome[TResult]], None]:
        """Return a callback that clears this key only for the current handle."""

        def clear(_outcome: TaskOutcome[TResult]) -> None:
            """Remove this key only if it still points at this handle."""

            with self._lock:
                existing = self._active.get(key)
                if existing is not None and existing[0] is handle:
                    del self._active[key]

        return clear


class BlockingSingleFlight(Generic[TKey, TResult]):
    """Share one synchronous keyed result across duplicate blocking callers."""

    def __init__(
        self,
        *,
        wait_interval_seconds: float = _BLOCKING_SINGLE_FLIGHT_WAIT_SECONDS,
    ) -> None:
        """Create a blocking single-flight policy for synchronous load paths."""

        if wait_interval_seconds <= 0.0:
            raise ValueError("wait_interval_seconds must be positive.")
        self._wait_interval_seconds = wait_interval_seconds
        self._active: dict[TKey, _BlockingSingleFlightCall[TResult]] = {}
        self._lock = RLock()

    @property
    def active_count(self) -> int:
        """Return the number of keys with active owner work."""

        with self._lock:
            return len(self._active)

    def run(
        self,
        key: TKey,
        work: Callable[[], TResult],
        *,
        cancellation: CancellationToken | None = None,
        on_wait: Callable[[], None] | None = None,
    ) -> TResult:
        """Run owner work once and let duplicate callers wait for its outcome."""

        with self._lock:
            existing = self._active.get(key)
            if existing is None:
                call = _BlockingSingleFlightCall[TResult](
                    condition=Condition(self._lock)
                )
                self._active[key] = call
                owns_work = True
            else:
                call = existing
                owns_work = False

        if not owns_work:
            if on_wait is not None:
                on_wait()
            return self._wait_for_result(call, cancellation=cancellation)

        try:
            result = work()
        except BaseException as error:
            self._publish_result(key, call, error=error)
            raise
        self._publish_result(key, call, result=result)
        return result

    def _wait_for_result(
        self,
        call: _BlockingSingleFlightCall[TResult],
        *,
        cancellation: CancellationToken | None,
    ) -> TResult:
        """Wait for owner work while polling optional cancellation state."""

        with self._lock:
            while not call.completed:
                if cancellation is not None and cancellation.is_cancelled:
                    raise SingleFlightCancelled(cancellation.reason or "cancelled")
                call.condition.wait(self._wait_interval_seconds)
            if call.error is not None:
                raise call.error
            return cast(TResult, call.result)

    def _publish_result(
        self,
        key: TKey,
        call: _BlockingSingleFlightCall[TResult],
        *,
        result: TResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Publish owner completion to every duplicate waiter."""

        with self._lock:
            if self._active.get(key) is call:
                del self._active[key]
            call.result = result
            call.error = error
            call.completed = True
            call.condition.notify_all()


class SerialTaskGate:
    """Allow one ordered task to run while later requests wait."""

    def __init__(self) -> None:
        """Create an idle serial gate."""

        self._active = False
        self._queued: deque[Hashable] = deque()
        self._lock = Lock()

    @property
    def is_active(self) -> bool:
        """Return whether a task currently owns the gate."""

        with self._lock:
            return self._active

    @property
    def queued_count(self) -> int:
        """Return the number of waiting task keys."""

        with self._lock:
            return len(self._queued)

    def request_start(self, key: Hashable) -> bool:
        """Return true when the caller can start immediately."""

        with self._lock:
            if self._active:
                self._queued.append(key)
                return False
            self._active = True
            return True

    def finish_and_take_next(self) -> Hashable | None:
        """Release the active task and return the next waiting key."""

        with self._lock:
            if self._queued:
                return self._queued.popleft()
            self._active = False
            return None


class BoundedTaskQueue(Generic[TItem]):
    """Track queued items while enforcing a maximum pending count."""

    def __init__(self, *, capacity: int) -> None:
        """Create a bounded FIFO queue."""

        if capacity <= 0:
            raise ValueError("capacity must be positive.")
        self._capacity = capacity
        self._queued: deque[TItem] = deque()
        self._lock = Lock()

    @property
    def capacity(self) -> int:
        """Return the configured queue capacity."""

        return self._capacity

    @property
    def pending_count(self) -> int:
        """Return the number of queued items."""

        with self._lock:
            return len(self._queued)

    def try_push(self, item: TItem) -> bool:
        """Queue one item when capacity is available."""

        with self._lock:
            if len(self._queued) >= self._capacity:
                return False
            self._queued.append(item)
            return True

    def pop_next(self) -> TItem | None:
        """Return the next queued item when one exists."""

        with self._lock:
            if not self._queued:
                return None
            return self._queued.popleft()


class FireAndLogSubmitter:
    """Submit best-effort work and log failed outcomes."""

    def __init__(
        self,
        *,
        submitter: TaskSubmitter,
        logger: logging.Logger,
    ) -> None:
        """Store the wrapped submitter and diagnostic logger."""

        self._submitter = submitter
        self._logger = logger

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit work and attach a failure logging callback."""

        handle = self._submitter.submit(request, cancellation=cancellation)
        handle.add_done_callback(
            self._log_failed_outcome,
            reason="fire_and_log_completion",
        )
        return handle

    def _log_failed_outcome(self, outcome: TaskOutcome[TResult]) -> None:
        """Log failed best-effort work without raising to the owner."""

        if outcome.status != "failed":
            return
        self._logger.error(
            "Best-effort execution task failed.",
            extra={
                "operation": outcome.context.operation,
                "reason": outcome.context.reason,
                "lane": outcome.context.lane,
                "request_id": outcome.identity.request_id,
            },
            exc_info=outcome.error,
        )


def _cancel_pair(
    *,
    source: CancellationSource | None,
    handle: TaskHandle[TResult] | None,
    reason: str,
) -> None:
    """Cancel a source and handle when either is active."""

    if source is not None:
        source.cancel(reason=reason)
    if handle is not None:
        handle.cancel(reason=reason)


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank policy labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "BlockingSingleFlight",
    "BoundedTaskQueue",
    "FireAndLogSubmitter",
    "KeyedSingleFlight",
    "LatestWinsRequestChannel",
    "ScopedKeyedSingleFlight",
    "SerialTaskGate",
    "SingleFlightCancelled",
]
