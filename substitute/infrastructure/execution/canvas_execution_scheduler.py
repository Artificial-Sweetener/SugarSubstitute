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

"""Schedule CuteCanvas work fairly across host-owned physical resource lanes."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from concurrent.futures import Future
from dataclasses import dataclass
from functools import partial
from threading import RLock

from cutecanvas import (
    ExecutionJob,
    ExecutionLeaseRelease,
    ExecutionRejected,
    ExecutionRejectionReason,
    ExecutionResource,
    ExecutionUrgency,
)

from substitute.infrastructure.execution.thread_pool_admission import (
    ThreadPoolAdmission,
    ThreadPoolAdmissionSaturatedError,
)

_MEBIBYTE = 1024 * 1024
_URGENCY_RANK = {
    ExecutionUrgency.INTERACTIVE: 0,
    ExecutionUrgency.FOREGROUND: 10,
    ExecutionUrgency.BACKGROUND: 20,
    ExecutionUrgency.OPPORTUNISTIC: 30,
    ExecutionUrgency.MAINTENANCE: 40,
}


@dataclass(frozen=True, slots=True)
class CanvasExecutionPolicy:
    """Bound host canvas admission, payload retention, and urgency aging."""

    max_accepted: int = 256
    max_retained_bytes: int = 512 * _MEBIBYTE
    aging_interval_seconds: float = 0.25

    def __post_init__(self) -> None:
        """Reject limits that cannot form a useful bounded scheduler."""

        if self.max_accepted <= 0:
            raise ValueError("max_accepted must be positive")
        if self.max_retained_bytes <= 0:
            raise ValueError("max_retained_bytes must be positive")
        if self.aging_interval_seconds <= 0.0:
            raise ValueError("aging_interval_seconds must be positive")


@dataclass(slots=True)
class _PendingCanvasJob:
    """Retain an accepted canvas job until its resource lane can start it."""

    job: ExecutionJob
    sequence: int
    queued_at: float


class CanvasExecutionScheduler:
    """Honor canvas requirements before dispatching to dedicated host lanes."""

    def __init__(
        self,
        admissions: Mapping[ExecutionResource, ThreadPoolAdmission],
        *,
        policy: CanvasExecutionPolicy | None = None,
    ) -> None:
        """Bind one physical admission lane per supported resource class."""

        if not admissions:
            raise ValueError("canvas admissions must not be empty")
        self._admissions = dict(admissions)
        self._policy = policy or CanvasExecutionPolicy()
        self._pending: list[_PendingCanvasJob] = []
        self._accepted_bytes: dict[uuid.UUID, int] = {}
        self._running: dict[uuid.UUID, Future[bool]] = {}
        self._running_jobs: dict[uuid.UUID, ExecutionJob] = {}
        self._active_resources: dict[tuple[ExecutionResource, str | None], int] = {}
        self._active_exclusive: set[str] = set()
        self._sequence = 0
        self._closed = False
        self._lock = RLock()

    @property
    def resources(self) -> frozenset[ExecutionResource]:
        """Return resource classes with dedicated physical admission."""

        return frozenset(self._admissions)

    def submit(self, job: ExecutionJob) -> None:
        """Accept one bounded job and dispatch all newly eligible work."""

        estimate = job.requirements.estimated_retained_bytes or 0
        with self._lock:
            if self._closed:
                raise ExecutionRejected(
                    ExecutionRejectionReason.BACKEND_UNAVAILABLE,
                    "canvas execution scheduler is closed",
                )
            if job.requirements.resource not in self._admissions:
                raise ExecutionRejected(
                    ExecutionRejectionReason.UNSUPPORTED_REQUIREMENTS,
                    "canvas resource has no host admission lane",
                )
            if len(self._accepted_bytes) >= self._policy.max_accepted:
                raise ExecutionRejected(
                    ExecutionRejectionReason.SATURATED,
                    "canvas accepted-task limit reached",
                    details=(("limit", "accepted"),),
                )
            if (
                sum(self._accepted_bytes.values()) + estimate
                > self._policy.max_retained_bytes
            ):
                raise ExecutionRejected(
                    ExecutionRejectionReason.SATURATED,
                    "canvas retained-byte limit reached",
                    details=(("limit", "retained_bytes"),),
                )
            self._sequence += 1
            self._pending.append(
                _PendingCanvasJob(job, self._sequence, time.monotonic())
            )
            self._accepted_bytes[job.task_id] = estimate
            job.add_settled_callback(partial(self._release_accepted, job.task_id))
            self._dispatch_locked()

    def cancel(self, task_id: uuid.UUID, *, reason: str) -> bool:
        """Cancel accepted work that has not begun physical execution."""

        with self._lock:
            pending = next(
                (entry for entry in self._pending if entry.job.task_id == task_id),
                None,
            )
            if pending is not None:
                self._pending.remove(pending)
                resolved_job = pending.job
            else:
                future = self._running.get(task_id)
                running_job = self._running_jobs.get(task_id)
                if future is None or running_job is None or not future.cancel():
                    return False
                resolved_job = running_job
        return resolved_job.cancel_before_start(reason=reason)

    def close(self) -> None:
        """Reject new work and cancel every scheduler-pending job."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            pending = tuple(self._pending)
            self._pending.clear()
        for entry in pending:
            entry.job.cancel_before_start(reason="backend_shutdown")

    def _dispatch_locked(self) -> None:
        """Submit the best eligible jobs while physical workers are available."""

        while True:
            entry = self._take_next_locked()
            if entry is None:
                return
            job = entry.job
            admission = self._admissions[job.requirements.resource]
            self._mark_running_locked(job)
            try:
                future = admission.submit(job.run)
            except ThreadPoolAdmissionSaturatedError:
                self._unmark_running_locked(job)
                self._pending.append(entry)
                return
            except RuntimeError as error:
                self._unmark_running_locked(job)
                self._pending.append(entry)
                raise ExecutionRejected(
                    ExecutionRejectionReason.BACKEND_UNAVAILABLE,
                    "canvas host execution lane is unavailable",
                    details=(("lane", admission.name),),
                ) from error
            self._running[job.task_id] = future
            future.add_done_callback(partial(self._future_finished, job))

    def _take_next_locked(self) -> _PendingCanvasJob | None:
        """Remove the most urgent eligible job with starvation-preventing aging."""

        now = time.monotonic()
        eligible = [
            entry for entry in self._pending if self._is_eligible_locked(entry.job)
        ]
        if not eligible:
            return None
        selected = min(
            eligible,
            key=lambda entry: (
                _URGENCY_RANK[entry.job.requirements.urgency]
                - int((now - entry.queued_at) / self._policy.aging_interval_seconds),
                entry.sequence,
            ),
        )
        self._pending.remove(selected)
        return selected

    def _is_eligible_locked(self, job: ExecutionJob) -> bool:
        """Return whether lane, resource, and exclusive capacity permit dispatch."""

        requirements = job.requirements
        admission = self._admissions[requirements.resource]
        running_for_lane = sum(
            1
            for running in self._running_jobs.values()
            if running.requirements.resource is requirements.resource
        )
        if running_for_lane >= admission.max_workers:
            return False
        if (
            requirements.exclusive_key is not None
            and requirements.exclusive_key in self._active_exclusive
        ):
            return False
        key = (requirements.resource, requirements.resource_id)
        active = self._active_resources.get(key, 0)
        limit = min(
            admission.max_workers,
            requirements.maximum_concurrency or admission.max_workers,
        )
        return active < limit

    def _mark_running_locked(self, job: ExecutionJob) -> None:
        """Reserve physical and logical resource capacity for one job."""

        requirements = job.requirements
        self._running_jobs[job.task_id] = job
        key = (requirements.resource, requirements.resource_id)
        self._active_resources[key] = self._active_resources.get(key, 0) + 1
        if requirements.exclusive_key is not None:
            self._active_exclusive.add(requirements.exclusive_key)
            if requirements.lease_release is ExecutionLeaseRelease.ADOPTION_FINISHED:
                job.add_settled_callback(
                    partial(self._release_exclusive, requirements.exclusive_key)
                )

    def _unmark_running_locked(self, job: ExecutionJob) -> None:
        """Release reservations after dispatch failure or physical completion."""

        requirements = job.requirements
        self._running.pop(job.task_id, None)
        self._running_jobs.pop(job.task_id, None)
        key = (requirements.resource, requirements.resource_id)
        remaining = self._active_resources.get(key, 0) - 1
        if remaining > 0:
            self._active_resources[key] = remaining
        else:
            self._active_resources.pop(key, None)
        if (
            requirements.exclusive_key is not None
            and requirements.lease_release is ExecutionLeaseRelease.WORK_FINISHED
        ):
            self._active_exclusive.discard(requirements.exclusive_key)

    def _work_finished(self, job: ExecutionJob) -> None:
        """Release physical capacity and dispatch the next eligible jobs."""

        with self._lock:
            self._unmark_running_locked(job)
            self._dispatch_locked()

    def _future_finished(
        self,
        job: ExecutionJob,
        _future: Future[bool],
    ) -> None:
        """Translate one host future callback into scheduler completion."""

        self._work_finished(job)

    def _release_accepted(self, task_id: uuid.UUID) -> None:
        """Release retained-payload accounting after runtime settlement."""

        with self._lock:
            self._accepted_bytes.pop(task_id, None)
            self._dispatch_locked()

    def _release_exclusive(self, exclusive_key: str) -> None:
        """Release an adoption-held exclusive lease after job settlement."""

        with self._lock:
            self._active_exclusive.discard(exclusive_key)
            self._dispatch_locked()


__all__ = ["CanvasExecutionPolicy", "CanvasExecutionScheduler"]
