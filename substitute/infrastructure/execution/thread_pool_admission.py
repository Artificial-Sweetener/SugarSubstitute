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

"""Provide bounded physical admission to one reusable thread pool."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import TypeVar

TResult = TypeVar("TResult")


class ThreadPoolAdmissionSaturatedError(RuntimeError):
    """Report expected rejection when a physical lane has no capacity."""

    def __init__(self, *, lane_name: str, queue_capacity: int) -> None:
        """Describe the saturated physical lane."""

        self.lane_name = lane_name
        self.queue_capacity = queue_capacity
        super().__init__(f"Execution lane {lane_name} queue is full.")


class ThreadPoolAdmission:
    """Own bounded physical submission independently of task lifecycle policy."""

    def __init__(
        self,
        *,
        name: str,
        max_workers: int,
        queue_capacity: int | None,
        thread_name_prefix: str,
    ) -> None:
        """Create one reusable bounded thread-pool admission boundary."""

        _require_non_blank(name, field_name="name")
        _require_non_blank(thread_name_prefix, field_name="thread_name_prefix")
        _require_positive(max_workers, field_name="max_workers")
        _require_optional_positive(queue_capacity, field_name="queue_capacity")
        self._name = name
        self._max_workers = max_workers
        self._queue_capacity = queue_capacity
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._pending_count = 0
        self._is_shutdown = False
        self._lock = Lock()

    @property
    def name(self) -> str:
        """Return the stable lane name."""

        return self._name

    @property
    def queue_capacity(self) -> int | None:
        """Return the configured accepted-work limit."""

        return self._queue_capacity

    @property
    def max_workers(self) -> int:
        """Return the lane's physical worker concurrency."""

        return self._max_workers

    @property
    def pending_count(self) -> int:
        """Return accepted work that has not yet settled physically."""

        with self._lock:
            return self._pending_count

    def submit(self, work: Callable[[], TResult]) -> Future[TResult]:
        """Accept detached work without imposing an application task lifecycle."""

        with self._lock:
            if self._is_shutdown:
                raise RuntimeError(f"Execution lane {self._name} is shut down.")
            if (
                self._queue_capacity is not None
                and self._pending_count >= self._queue_capacity
            ):
                raise ThreadPoolAdmissionSaturatedError(
                    lane_name=self._name,
                    queue_capacity=self._queue_capacity,
                )
            self._pending_count += 1
        try:
            future = self._executor.submit(work)
        except BaseException:
            self._release_capacity()
            raise
        future.add_done_callback(lambda _future: self._release_capacity())
        return future

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
        """Stop admission and release physical worker resources."""

        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def _release_capacity(self) -> None:
        """Release one accepted-work slot after physical settlement."""

        with self._lock:
            if self._pending_count > 0:
                self._pending_count -= 1


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank physical-lane labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


def _require_positive(value: int, *, field_name: str) -> None:
    """Reject non-positive physical limits."""

    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def _require_optional_positive(value: int | None, *, field_name: str) -> None:
    """Reject configured physical limits that cannot admit work."""

    if value is not None:
        _require_positive(value, field_name=field_name)


__all__ = ["ThreadPoolAdmission", "ThreadPoolAdmissionSaturatedError"]
