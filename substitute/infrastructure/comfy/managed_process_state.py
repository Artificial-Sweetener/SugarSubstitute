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

"""Own synchronized managed process state and task lifecycle contracts."""

from __future__ import annotations

from threading import Lock
from typing import Callable, Protocol, TypeVar

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ContainmentMode,
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)

TResult = TypeVar("TResult")
LongLivedWork = Callable[[CancellationSource], TResult]


class ManagedLongLivedTaskHandle(Protocol):
    """Describe the task lifecycle handle used by managed process startup."""

    @property
    def is_finished(self) -> bool:
        """Return whether the task has reached a terminal state."""

    def stop(self, *, reason: str) -> None:
        """Request task cancellation."""


ManagedTaskFactory = Callable[
    [TaskIdentity, ExecutionContext, LongLivedWork[None], str],
    ManagedLongLivedTaskHandle,
]


class ManagedComfyState:
    """Track managed background ComfyUI process startup state."""

    def __init__(self, *, registry: ManagedProcessRegistry) -> None:
        """Initialize mutable managed process state."""

        self.proc: ManagedProcessHandle | None = None
        self.registry = registry
        self.metadata: ManagedProcessMetadata | None = None
        self.containment_handle: object | None = None
        self.containment_mode: ContainmentMode | None = None
        self.startup_result: ManagedStartupReadinessResult | None = None
        self.launch_task: ManagedLongLivedTaskHandle | None = None
        self._process_pumps: list[ManagedLongLivedTaskHandle] = []
        self._stop_requested = False
        self._spawn_lock = Lock()
        self._state_lock = Lock()

    @property
    def stop_requested(self) -> bool:
        """Return whether lifecycle shutdown has been requested."""

        with self._state_lock:
            return self._stop_requested

    @property
    def is_finished(self) -> bool:
        """Return whether the startup task has finished."""

        task = self.launch_task
        return task is not None and task.is_finished

    def request_stop(self, *, reason: str) -> None:
        """Request startup cancellation without closing process-owned output."""

        with self._state_lock:
            self._stop_requested = True
            launch_task = self.launch_task
        if launch_task is not None:
            launch_task.stop(reason=reason)

    def wait_until_finished(self, *, timeout: float) -> None:
        """Wait briefly for the startup task when the handle exposes waiting."""

        task = self.launch_task
        if task is None:
            return
        join = getattr(task, "join", None)
        if callable(join):
            join(timeout=timeout)
            return
        wait = getattr(task, "wait", None)
        if callable(wait):
            wait(timeout=timeout)
            return

    def set_launch_task(self, task: ManagedLongLivedTaskHandle) -> None:
        """Store the task that owns managed startup execution."""

        with self._state_lock:
            self.launch_task = task

    def add_process_pump(self, task: ManagedLongLivedTaskHandle) -> None:
        """Store one task that pumps managed process output."""

        with self._state_lock:
            self._process_pumps.append(task)

    def record_reused_metadata(self, metadata: ManagedProcessMetadata) -> None:
        """Record metadata for a reused owned listener."""

        with self._state_lock:
            self.metadata = metadata
            self.containment_mode = metadata.containment_mode

    def record_startup_result(self, result: ManagedStartupReadinessResult) -> None:
        """Record managed startup readiness output."""

        with self._state_lock:
            self.startup_result = result

    def record_validated_metadata(
        self,
        metadata: ManagedProcessMetadata | None,
    ) -> None:
        """Record refreshed metadata after readiness validation."""

        with self._state_lock:
            self.metadata = metadata

    def with_spawn_lock(self, action: Callable[[], TResult]) -> TResult:
        """Run an action after any in-flight process spawn has quiesced."""

        with self._spawn_lock:
            return action()

    def record_launch_result_if_running(
        self,
        launch_result: object,
        *,
        registry: ManagedProcessRegistry,
    ) -> bool:
        """Record one newly launched process unless shutdown was requested."""

        with self._spawn_lock:
            if self.stop_requested:
                return False
            process = getattr(launch_result, "process")
            metadata = getattr(launch_result, "metadata")
            self.proc = process
            self.containment_handle = getattr(launch_result, "containment_handle")
            self.metadata = registry.save(metadata)
            self.containment_mode = metadata.containment_mode
            return True
