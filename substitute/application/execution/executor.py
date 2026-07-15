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

"""Define Qt-free execution request, handle, and lane protocols."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .cancellation import CancellationToken
from .context import ExecutionContext
from .identity import TaskIdentity
from .outcome import TaskOutcome

TResult = TypeVar("TResult")
TaskWork = Callable[[CancellationToken], TResult]


class ExecutionLaneSaturatedError(RuntimeError):
    """Report expected rejection when a bounded execution lane is full."""

    def __init__(self, *, lane_name: str, queue_capacity: int) -> None:
        """Describe the lane that could not admit additional work."""

        self.lane_name = lane_name
        self.queue_capacity = queue_capacity
        super().__init__(f"Execution lane {lane_name} queue is full.")


@dataclass(frozen=True, slots=True)
class TaskRequest(Generic[TResult]):
    """Describe one unit of execution work without running it."""

    identity: TaskIdentity
    context: ExecutionContext
    work: TaskWork[TResult]


class TaskHandle(Protocol, Generic[TResult]):
    """Describe one submitted execution task."""

    @property
    def identity(self) -> TaskIdentity:
        """Return the identity associated with this task."""

    @property
    def is_finished(self) -> bool:
        """Return whether this task has settled."""

    @property
    def outcome(self) -> TaskOutcome[TResult] | None:
        """Return the settled outcome when one is available."""

    @property
    def state(self) -> str:
        """Return the task state for diagnostics and tests."""

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Register one callback to receive the task outcome."""

    def cancel(self, *, reason: str) -> None:
        """Request cancellation of this task."""


class TaskSubmitter(Protocol):
    """Submit execution work through a replaceable boundary."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit one request and return its task handle."""


class ExecutionLane(TaskSubmitter, Protocol):
    """Submit bounded work to one named execution lane."""

    @property
    def name(self) -> str:
        """Return the configured lane name."""

    @property
    def queue_capacity(self) -> int | None:
        """Return the configured queue capacity when one is enforced."""

    @property
    def pending_count(self) -> int:
        """Return the number of queued or running lane tasks."""

    def shutdown(
        self,
        *,
        wait: bool = False,
        cancel_futures: bool = True,
    ) -> None:
        """Release lane resources."""


__all__ = [
    "ExecutionLaneSaturatedError",
    "ExecutionLane",
    "TaskHandle",
    "TaskRequest",
    "TaskSubmitter",
    "TaskWork",
]
