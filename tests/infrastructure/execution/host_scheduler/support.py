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

"""Provide deterministic lifecycle controls for host scheduler tests."""

from __future__ import annotations

import threading
import uuid
from _thread import LockType
from collections.abc import Callable
from threading import Event, Lock

from substitute.infrastructure.execution import (
    HostExecutionJob,
    HostExecutionLeaseRelease,
    HostExecutionPolicy,
    HostExecutionRequirements,
    HostExecutionResource,
    HostExecutionScheduler,
)


class ManualLifecycleJob:
    """Control settlement independently from physical worker completion."""

    def __init__(
        self,
        *,
        requirements: HostExecutionRequirements,
        started: Event | None = None,
        cancelled: list[uuid.UUID] | None = None,
        cancellation_lock: LockType | None = None,
    ) -> None:
        """Create one externally settled job."""

        self._started = started
        self._cancelled = cancelled
        self._cancellation_lock = cancellation_lock
        self._settled_callbacks: list[Callable[[], None]] = []
        self._settled = False
        self._lock = Lock()
        self.cancel_count = 0
        task_id = uuid.uuid4()
        self.job = HostExecutionJob(
            task_id=task_id,
            operation=f"manual_{task_id}",
            requirements=requirements,
            run=self._run,
            cancel_before_start=self._cancel,
            observe_settlement=self._observe_settlement,
        )

    def settle(self) -> None:
        """Notify every settlement observer exactly once."""

        with self._lock:
            if self._settled:
                return
            self._settled = True
            callbacks = tuple(self._settled_callbacks)
            self._settled_callbacks.clear()
        for callback in callbacks:
            callback()

    def _run(self) -> object:
        """Report physical activation."""

        if self._started is not None:
            self._started.set()
        return True

    def _cancel(self, _reason: str) -> bool:
        """Record one scheduler-owned pending cancellation."""

        with self._lock:
            self.cancel_count += 1
        if self._cancelled is not None and self._cancellation_lock is not None:
            with self._cancellation_lock:
                self._cancelled.append(self.job.task_id)
        self.settle()
        return True

    def _observe_settlement(self, callback: Callable[[], None]) -> None:
        """Retain or immediately invoke one settlement observer."""

        with self._lock:
            if self._settled:
                invoke_now = True
            else:
                invoke_now = False
                self._settled_callbacks.append(callback)
        if invoke_now:
            callback()


def build_scheduler(
    *,
    native_workers: int = 2,
    affinity_shards: int = 2,
) -> HostExecutionScheduler:
    """Create one deterministic scheduler with all public resources."""

    return HostExecutionScheduler(
        HostExecutionPolicy(
            resource_workers={
                HostExecutionResource.BLOCKING_IO: 1,
                HostExecutionResource.PYTHON_CPU: 1,
                HostExecutionResource.NATIVE_CPU: native_workers,
                HostExecutionResource.DEVICE: 1,
            },
            affinity_shards=affinity_shards,
            max_accepted=512,
            thread_name_prefix="test-host",
        )
    )


def native_requirements(
    *,
    exclusive_key: str | None = None,
    lease_release: HostExecutionLeaseRelease = HostExecutionLeaseRelease.WORK_FINISHED,
) -> HostExecutionRequirements:
    """Build native CPU requirements for scheduler abuse."""

    return HostExecutionRequirements(
        resource=HostExecutionResource.NATIVE_CPU,
        urgency_rank=10,
        exclusive_key=exclusive_key,
        lease_release=lease_release,
    )


def block_until_released(started: Event, release: Event) -> None:
    """Block one physical worker behind an observable gate."""

    started.set()
    if not release.wait(timeout=2.0):
        raise TimeoutError("test worker was not released")


def capture_affinity(affinity_key: str) -> tuple[str, str]:
    """Return one affinity key with its physical host thread."""

    return affinity_key, threading.current_thread().name


def record_storm_job(
    sequence: int,
    observed: dict[int, str],
    observed_lock: LockType,
) -> int:
    """Record one exact activation and reject duplicate physical execution."""

    with observed_lock:
        assert sequence not in observed
        observed[sequence] = threading.current_thread().name
    return sequence


def wait_for_release(release: Event) -> None:
    """Wait for one bounded hostile burst release."""

    if not release.wait(timeout=1.0):
        raise TimeoutError("test burst was not released")


def wait_for_snapshot(
    scheduler: HostExecutionScheduler,
    predicate: Callable[[int, int], bool],
) -> bool:
    """Wait on diagnostics publication until scheduler state converges."""

    reached = Event()
    subscription = scheduler.subscribe_diagnostics(
        lambda snapshot: (
            reached.set() if predicate(snapshot.accepted, snapshot.running) else None
        )
    )
    try:
        snapshot = scheduler.snapshot()
        if predicate(snapshot.accepted, snapshot.running):
            return True
        return reached.wait(timeout=1.0)
    finally:
        subscription.close()
