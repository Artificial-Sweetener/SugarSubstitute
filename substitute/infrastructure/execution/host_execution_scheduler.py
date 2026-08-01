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

"""Own bounded physical scheduling for host and embedded-library work."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from dataclasses import dataclass
from functools import partial
from threading import Condition, Lock, Thread
from typing import TypeVar

from substitute.infrastructure.execution.host_execution_diagnostics import (
    HostDiagnosticsSubscription,
    HostExecutionDiagnostics,
)
from substitute.infrastructure.execution.host_execution_model import (
    HostExecutionJob,
    HostExecutionLeaseRelease,
    HostExecutionRequirements,
    HostExecutionResource,
    HostExecutionSnapshot,
)

TResult = TypeVar("TResult")
_MEBIBYTE = 1024 * 1024


class HostExecutionRejected(RuntimeError):
    """Report host admission rejection before physical activation."""

    def __init__(self, *, limit: str) -> None:
        """Describe the bounded limit that rejected work."""

        self.limit = limit
        super().__init__(f"host execution rejected work at {limit}")


@dataclass(frozen=True, slots=True)
class HostExecutionPolicy:
    """Configure resource capacity, admission, affinity, and urgency aging."""

    resource_workers: Mapping[HostExecutionResource, int]
    affinity_shards: int = 2
    max_accepted: int = 256
    max_retained_bytes: int = 512 * _MEBIBYTE
    aging_interval_seconds: float = 0.25
    thread_name_prefix: str = "substitute-canvas"

    def __post_init__(self) -> None:
        """Reject policies that cannot form a bounded physical scheduler."""

        ordinary_resources = set(HostExecutionResource) - {
            HostExecutionResource.THREAD_AFFINE_NATIVE
        }
        if set(self.resource_workers) != ordinary_resources:
            raise ValueError("resource_workers must configure every ordinary resource")
        if any(workers <= 0 for workers in self.resource_workers.values()):
            raise ValueError("resource worker counts must be positive")
        if self.affinity_shards <= 0:
            raise ValueError("affinity_shards must be positive")
        if self.max_accepted <= 0:
            raise ValueError("max_accepted must be positive")
        if self.max_retained_bytes <= 0:
            raise ValueError("max_retained_bytes must be positive")
        if self.aging_interval_seconds <= 0.0:
            raise ValueError("aging_interval_seconds must be positive")
        if not self.thread_name_prefix.strip():
            raise ValueError("thread_name_prefix must not be blank")


@dataclass(slots=True)
class _PendingHostJob:
    """Retain one accepted job until an eligible worker activates it."""

    job: HostExecutionJob
    sequence: int
    queued_at: float


class HostExecutionSubmission:
    """Cancel one host-scheduler job while it remains pending."""

    def __init__(self, scheduler: HostExecutionScheduler, task_id: uuid.UUID) -> None:
        """Bind cancellation to the authoritative scheduler."""

        self._scheduler = scheduler
        self._task_id = task_id

    def cancel(self, *, reason: str) -> bool:
        """Remove pending work and invoke its lifecycle cancellation."""

        return self._scheduler.cancel(self._task_id, reason=reason)


class HostExecutionScheduler:
    """Schedule every canvas resource through host-owned bounded workers."""

    def __init__(
        self,
        policy: HostExecutionPolicy,
        *,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        """Create an initially idle scheduler whose workers start lazily."""

        self._policy = policy
        self._clock = clock
        self._logger = logger or logging.getLogger(__name__)
        self._pending: list[_PendingHostJob] = []
        self._accepted_bytes: dict[uuid.UUID, int] = {}
        self._running: dict[uuid.UUID, HostExecutionJob] = {}
        self._active_resources: dict[tuple[HostExecutionResource, str | None], int] = {}
        self._active_exclusive: set[str] = set()
        self._ordinary_threads: dict[HostExecutionResource, list[Thread]] = {}
        self._affinity_threads: dict[int, Thread] = {}
        self._sequence = 0
        self._rejected = 0
        self._completed = 0
        self._cancelled_before_start = 0
        self._closed = False
        self._condition = Condition(Lock())
        self._diagnostics = HostExecutionDiagnostics(
            thread_name=f"{policy.thread_name_prefix}-diagnostics",
            logger=self._logger,
        )

    @property
    def supported_resources(self) -> frozenset[HostExecutionResource]:
        """Return every resource the physical scheduler can execute."""

        return frozenset(HostExecutionResource)

    def submit(self, job: HostExecutionJob) -> HostExecutionSubmission:
        """Admit a lifecycle-owned job and wake its physical resource."""

        with self._condition:
            self._admit_locked(job)
            self._ensure_workers_locked(job.requirements)
            self._condition.notify_all()
        return HostExecutionSubmission(self, job.task_id)

    def submit_detached(
        self,
        work: Callable[[], TResult],
        *,
        operation: str,
        requirements: HostExecutionRequirements,
    ) -> Future[TResult]:
        """Admit host work with a future as its complete lifecycle owner."""

        future: Future[TResult] = Future()

        def _run() -> object:
            """Execute detached work and settle its future once."""

            if not future.set_running_or_notify_cancel():
                return False
            try:
                future.set_result(work())
            except BaseException as error:  # noqa: BLE001
                future.set_exception(error)
            return True

        job = HostExecutionJob(
            task_id=uuid.uuid4(),
            operation=operation,
            requirements=requirements,
            run=_run,
            cancel_before_start=lambda _reason: future.cancel(),
            observe_settlement=lambda callback: future.add_done_callback(
                lambda _future: callback()
            ),
        )
        self.submit(job)
        return future

    def cancel(self, task_id: uuid.UUID, *, reason: str) -> bool:
        """Cancel one accepted job if no worker has activated it."""

        if not reason.strip():
            raise ValueError("cancellation reason must not be blank")
        with self._condition:
            entry = next(
                (item for item in self._pending if item.job.task_id == task_id),
                None,
            )
            if entry is None:
                return False
            self._pending.remove(entry)
            self._condition.notify_all()
            self._publish_locked()
        cancelled = entry.job.cancel_before_start(reason)
        if cancelled:
            with self._condition:
                self._cancelled_before_start += 1
                self._condition.notify_all()
                self._publish_locked()
        return cancelled

    def snapshot(self) -> HostExecutionSnapshot:
        """Return current physical state without exposing queue internals."""

        with self._condition:
            return self._snapshot_locked()

    def subscribe_diagnostics(
        self,
        callback: Callable[[HostExecutionSnapshot], None],
    ) -> HostDiagnosticsSubscription:
        """Observe coalesced scheduler snapshots until the subscription closes."""

        return self._diagnostics.subscribe(callback)

    def shutdown(self, *, wait: bool) -> None:
        """Cancel pending work and stop all host-owned workers."""

        pending: tuple[_PendingHostJob, ...] = ()
        with self._condition:
            if self._closed:
                threads = self._threads_locked()
            else:
                self._closed = True
                pending = tuple(self._pending)
                self._pending.clear()
                threads = self._threads_locked()
                self._condition.notify_all()
                self._publish_locked()
        for entry in pending:
            if entry.job.cancel_before_start("host_scheduler_shutdown"):
                with self._condition:
                    self._cancelled_before_start += 1
                    self._condition.notify_all()
                    self._publish_locked()
        if wait:
            for thread in threads:
                thread.join()
        self._diagnostics.close(wait=wait)

    def _admit_locked(self, job: HostExecutionJob) -> None:
        """Validate and retain one job while holding the scheduler lock."""

        if self._closed:
            raise HostExecutionRejected(limit="scheduler_closed")
        if job.task_id in self._accepted_bytes:
            raise ValueError("task_id must be unique")
        if len(self._accepted_bytes) >= self._policy.max_accepted:
            self._rejected += 1
            self._publish_locked()
            raise HostExecutionRejected(limit="accepted")
        estimate = job.requirements.estimated_retained_bytes
        if (
            sum(self._accepted_bytes.values()) + estimate
            > self._policy.max_retained_bytes
        ):
            self._rejected += 1
            self._publish_locked()
            raise HostExecutionRejected(limit="retained_bytes")
        self._sequence += 1
        self._pending.append(
            _PendingHostJob(
                job=job,
                sequence=self._sequence,
                queued_at=self._clock(),
            )
        )
        self._accepted_bytes[job.task_id] = estimate
        job.observe_settlement(partial(self._release_accepted, job.task_id))
        self._publish_locked()

    def _ensure_workers_locked(
        self,
        requirements: HostExecutionRequirements,
    ) -> None:
        """Start only the workers needed by an admitted resource."""

        resource = requirements.resource
        if resource is HostExecutionResource.THREAD_AFFINE_NATIVE:
            affinity_key = requirements.affinity_key
            if affinity_key is None:
                raise ValueError("thread-affine work requires affinity_key")
            shard = self._affinity_shard(affinity_key)
            if shard not in self._affinity_threads:
                thread = Thread(
                    target=self._worker_loop,
                    args=(resource, shard),
                    name=f"{self._policy.thread_name_prefix}-affinity-{shard + 1}",
                    daemon=True,
                )
                self._affinity_threads[shard] = thread
                thread.start()
                self._publish_locked()
            return
        threads = self._ordinary_threads.setdefault(resource, [])
        accepted_for_resource = sum(
            entry.job.requirements.resource is resource for entry in self._pending
        ) + sum(job.requirements.resource is resource for job in self._running.values())
        desired_workers = min(
            self._policy.resource_workers[resource],
            accepted_for_resource,
        )
        while len(threads) < desired_workers:
            index = len(threads)
            thread = Thread(
                target=self._worker_loop,
                args=(resource, None),
                name=(
                    f"{self._policy.thread_name_prefix}-"
                    f"{resource.value.replace('_', '-')}-{index + 1}"
                ),
                daemon=True,
            )
            threads.append(thread)
            thread.start()
        self._publish_locked()

    def _worker_loop(
        self,
        resource: HostExecutionResource,
        affinity_shard: int | None,
    ) -> None:
        """Activate eligible work for one ordinary pool or affinity shard."""

        while True:
            with self._condition:
                entry = self._take_next_locked(resource, affinity_shard)
                while entry is None:
                    if self._closed:
                        return
                    self._condition.wait()
                    entry = self._take_next_locked(resource, affinity_shard)
                self._mark_running_locked(entry.job)
            try:
                entry.job.run()
            except BaseException:  # noqa: BLE001
                self._logger.exception(
                    "Host execution job escaped its lifecycle boundary.",
                    extra={
                        "operation": entry.job.operation,
                        "resource": entry.job.requirements.resource.value,
                    },
                )
            finally:
                self._finish_running(entry.job)

    def _take_next_locked(
        self,
        resource: HostExecutionResource,
        affinity_shard: int | None,
    ) -> _PendingHostJob | None:
        """Remove the most urgent eligible job for one physical worker."""

        now = self._clock()
        eligible = [
            entry
            for entry in self._pending
            if entry.job.requirements.resource is resource
            and self._matches_affinity(entry.job.requirements, affinity_shard)
            and self._is_eligible_locked(entry.job)
        ]
        if not eligible:
            return None
        selected = min(
            eligible,
            key=lambda entry: (
                entry.job.requirements.urgency_rank
                - int((now - entry.queued_at) / self._policy.aging_interval_seconds),
                entry.sequence,
            ),
        )
        self._pending.remove(selected)
        return selected

    def _matches_affinity(
        self,
        requirements: HostExecutionRequirements,
        affinity_shard: int | None,
    ) -> bool:
        """Return whether one worker owns the request's affinity identity."""

        if requirements.resource is not HostExecutionResource.THREAD_AFFINE_NATIVE:
            return affinity_shard is None
        affinity_key = requirements.affinity_key
        return affinity_key is not None and affinity_shard == self._affinity_shard(
            affinity_key
        )

    def _is_eligible_locked(self, job: HostExecutionJob) -> bool:
        """Return whether logical resource and exclusive capacity is available."""

        requirements = job.requirements
        if (
            requirements.exclusive_key is not None
            and requirements.exclusive_key in self._active_exclusive
        ):
            return False
        key = self._resource_key(requirements)
        active = self._active_resources.get(key, 0)
        physical_limit = (
            1
            if requirements.resource is HostExecutionResource.THREAD_AFFINE_NATIVE
            else self._policy.resource_workers[requirements.resource]
        )
        limit = min(
            physical_limit,
            requirements.maximum_concurrency or physical_limit,
        )
        return active < limit

    def _mark_running_locked(self, job: HostExecutionJob) -> None:
        """Reserve resource and exclusive capacity before activation."""

        requirements = job.requirements
        self._running[job.task_id] = job
        key = self._resource_key(requirements)
        self._active_resources[key] = self._active_resources.get(key, 0) + 1
        if requirements.exclusive_key is not None:
            self._active_exclusive.add(requirements.exclusive_key)
            if (
                requirements.lease_release
                is HostExecutionLeaseRelease.SETTLEMENT_FINISHED
            ):
                job.observe_settlement(
                    partial(
                        self._release_exclusive,
                        requirements.exclusive_key,
                    )
                )
        self._publish_locked()

    def _finish_running(self, job: HostExecutionJob) -> None:
        """Release computation capacity after worker execution returns."""

        requirements = job.requirements
        with self._condition:
            self._running.pop(job.task_id, None)
            key = self._resource_key(requirements)
            remaining = self._active_resources.get(key, 0) - 1
            if remaining > 0:
                self._active_resources[key] = remaining
            else:
                self._active_resources.pop(key, None)
            if (
                requirements.exclusive_key is not None
                and requirements.lease_release
                is HostExecutionLeaseRelease.WORK_FINISHED
            ):
                self._active_exclusive.discard(requirements.exclusive_key)
            self._condition.notify_all()
            self._publish_locked()

    def _release_accepted(self, task_id: uuid.UUID) -> None:
        """Release retained-payload accounting after lifecycle settlement."""

        with self._condition:
            if task_id not in self._accepted_bytes:
                return
            self._accepted_bytes.pop(task_id)
            self._completed += 1
            self._condition.notify_all()
            self._publish_locked()

    def _release_exclusive(self, exclusive_key: str) -> None:
        """Release one settlement-held exclusive lease."""

        with self._condition:
            self._active_exclusive.discard(exclusive_key)
            self._condition.notify_all()
            self._publish_locked()

    def _affinity_shard(self, affinity_key: str) -> int:
        """Map one arbitrary key to a bounded stable worker shard."""

        digest = hashlib.blake2b(affinity_key.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self._policy.affinity_shards

    @staticmethod
    def _resource_key(
        requirements: HostExecutionRequirements,
    ) -> tuple[HostExecutionResource, str | None]:
        """Resolve the identity governed by request concurrency."""

        identity = requirements.resource_id
        if (
            identity is None
            and requirements.resource is HostExecutionResource.THREAD_AFFINE_NATIVE
        ):
            identity = requirements.affinity_key
        return requirements.resource, identity

    def _threads_locked(self) -> tuple[Thread, ...]:
        """Return every lazily created worker while holding the lock."""

        return tuple(
            thread for threads in self._ordinary_threads.values() for thread in threads
        ) + tuple(self._affinity_threads.values())

    def _snapshot_locked(self) -> HostExecutionSnapshot:
        """Build one immutable snapshot while holding scheduler state."""

        return HostExecutionSnapshot(
            accepted=len(self._accepted_bytes),
            pending=len(self._pending),
            running=len(self._running),
            retained_bytes=sum(self._accepted_bytes.values()),
            rejected=self._rejected,
            completed=self._completed,
            cancelled_before_start=self._cancelled_before_start,
            worker_threads=sum(
                sum(thread.is_alive() for thread in threads)
                for threads in self._ordinary_threads.values()
            )
            + sum(thread.is_alive() for thread in self._affinity_threads.values()),
        )

    def _publish_locked(self) -> None:
        """Publish current state without invoking observers on this lock."""

        self._diagnostics.publish(self._snapshot_locked())


__all__ = [
    "HostExecutionPolicy",
    "HostExecutionRejected",
    "HostExecutionScheduler",
    "HostExecutionSubmission",
]
