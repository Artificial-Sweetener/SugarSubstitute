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

"""Define execution task outcome values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from .context import ExecutionContext
from .identity import TaskIdentity

TResult = TypeVar("TResult")
TaskStatus = Literal["succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class TaskTimings:
    """Record monotonic task scheduling and execution timestamps."""

    queued_at: float | None = None
    started_at: float | None = None
    completed_at: float | None = None

    def __post_init__(self) -> None:
        """Reject timestamp orderings that cannot describe one task."""

        if (
            self.queued_at is not None
            and self.started_at is not None
            and self.started_at < self.queued_at
        ):
            raise ValueError("started_at must not be earlier than queued_at.")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not be earlier than started_at.")

    @property
    def queued_age_ms(self) -> float | None:
        """Return milliseconds spent queued when timestamps are available."""

        if self.queued_at is None or self.started_at is None:
            return None
        return (self.started_at - self.queued_at) * 1000

    @property
    def run_duration_ms(self) -> float | None:
        """Return milliseconds spent running when timestamps are available."""

        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at) * 1000


@dataclass(frozen=True, slots=True)
class TaskOutcome(Generic[TResult]):
    """Carry one completed task result without raising during publication."""

    identity: TaskIdentity
    context: ExecutionContext
    status: TaskStatus
    result: TResult | None = None
    error: BaseException | None = None
    timings: TaskTimings = TaskTimings()
    cancellation_reason: str | None = None

    def __post_init__(self) -> None:
        """Reject outcome states that would make task publication ambiguous."""

        if self.status == "succeeded":
            if self.error is not None or self.cancellation_reason is not None:
                raise ValueError("succeeded outcomes must not carry failure state.")
        elif self.status == "failed":
            if self.error is None:
                raise ValueError("failed outcomes must carry an error.")
            if self.result is not None or self.cancellation_reason is not None:
                raise ValueError(
                    "failed outcomes must not carry result or cancellation."
                )
        elif self.status == "cancelled":
            if self.error is not None or self.result is not None:
                raise ValueError("cancelled outcomes must not carry result or error.")
            _require_non_blank(
                self.cancellation_reason,
                field_name="cancellation_reason",
            )

    @property
    def cancelled(self) -> bool:
        """Return whether this outcome represents cancellation."""

        return self.status == "cancelled"


def _require_non_blank(value: str | None, *, field_name: str) -> None:
    """Reject missing or blank outcome labels."""

    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "TaskOutcome",
    "TaskStatus",
    "TaskTimings",
]
