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

"""Describe host-owned physical execution without library task semantics."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class HostExecutionResource(str, Enum):
    """Identify one independently capacity-bounded physical resource."""

    BLOCKING_IO = "blocking_io"
    PYTHON_CPU = "python_cpu"
    NATIVE_CPU = "native_cpu"
    DEVICE = "device"
    THREAD_AFFINE_NATIVE = "thread_affine_native"


class HostExecutionLeaseRelease(str, Enum):
    """Identify when an exclusive physical lease becomes reusable."""

    WORK_FINISHED = "work_finished"
    SETTLEMENT_FINISHED = "settlement_finished"


@dataclass(frozen=True, slots=True)
class HostExecutionRequirements:
    """Describe physical scheduling constraints for one detached job."""

    resource: HostExecutionResource
    urgency_rank: int
    resource_id: str | None = None
    exclusive_key: str | None = None
    affinity_key: str | None = None
    maximum_concurrency: int | None = None
    lease_release: HostExecutionLeaseRelease = HostExecutionLeaseRelease.WORK_FINISHED
    estimated_retained_bytes: int = 0

    def __post_init__(self) -> None:
        """Reject requirements the host scheduler cannot interpret safely."""

        if self.maximum_concurrency is not None and self.maximum_concurrency <= 0:
            raise ValueError("maximum_concurrency must be positive")
        if self.estimated_retained_bytes < 0:
            raise ValueError("estimated_retained_bytes must not be negative")
        if (
            self.resource is HostExecutionResource.THREAD_AFFINE_NATIVE
            and self.affinity_key is None
        ):
            raise ValueError("thread-affine work requires affinity_key")
        if (
            self.lease_release is HostExecutionLeaseRelease.SETTLEMENT_FINISHED
            and self.exclusive_key is None
        ):
            raise ValueError("settlement-held leases require exclusive_key")


@dataclass(frozen=True, slots=True)
class HostExecutionJob:
    """Expose one lifecycle-owned callable to the physical scheduler."""

    task_id: uuid.UUID
    operation: str
    requirements: HostExecutionRequirements
    run: Callable[[], object]
    cancel_before_start: Callable[[str], bool]
    observe_settlement: Callable[[Callable[[], None]], None]

    def __post_init__(self) -> None:
        """Reject jobs without stable diagnostic identity."""

        if not self.operation.strip():
            raise ValueError("operation must not be blank")


@dataclass(frozen=True, slots=True)
class HostExecutionSnapshot:
    """Summarize physical execution state for diagnostics and tests."""

    accepted: int
    pending: int
    running: int
    retained_bytes: int
    rejected: int
    completed: int
    cancelled_before_start: int
    worker_threads: int


__all__ = [
    "HostExecutionJob",
    "HostExecutionLeaseRelease",
    "HostExecutionRequirements",
    "HostExecutionResource",
    "HostExecutionSnapshot",
]
