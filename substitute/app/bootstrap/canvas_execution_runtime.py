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

"""Compose CuteCanvas lifecycle over SugarSubstitute physical execution."""

from __future__ import annotations

from cutecanvas import ExecutionRuntime as CuteCanvasExecutionRuntime

from substitute.infrastructure.execution.cutecanvas_execution_backend import (
    CuteCanvasExecutionBackend,
)
from substitute.infrastructure.execution.host_execution_model import (
    HostExecutionResource,
)
from substitute.infrastructure.execution.host_execution_scheduler import (
    HostExecutionPolicy,
    HostExecutionScheduler,
)

_CANVAS_RESOURCE_WORKERS = {
    HostExecutionResource.BLOCKING_IO: 4,
    HostExecutionResource.PYTHON_CPU: 2,
    HostExecutionResource.NATIVE_CPU: 4,
    HostExecutionResource.DEVICE: 1,
}


class CanvasExecutionRuntime:
    """Own the complete host integration and its teardown order."""

    def __init__(self) -> None:
        """Create the host scheduler, public adapter, and logical runtime."""

        self._scheduler = HostExecutionScheduler(
            HostExecutionPolicy(
                resource_workers=_CANVAS_RESOURCE_WORKERS,
                affinity_shards=2,
            )
        )
        self._backend = CuteCanvasExecutionBackend(self._scheduler)
        self._runtime = CuteCanvasExecutionRuntime(self._backend)
        self._closed = False

    @property
    def runtime(self) -> CuteCanvasExecutionRuntime:
        """Return the public runtime injected into every canvas document."""

        return self._runtime

    @property
    def scheduler(self) -> HostExecutionScheduler:
        """Return the physical host owner for diagnostics and verification."""

        return self._scheduler

    def shutdown(self, *, wait: bool) -> None:
        """Close logical ownership before cancelling physical admission."""

        if self._closed:
            self._scheduler.shutdown(wait=wait)
            return
        self._closed = True
        self._runtime.shutdown(wait=False)
        self._backend.shutdown(wait=wait)


__all__ = ["CanvasExecutionRuntime"]
