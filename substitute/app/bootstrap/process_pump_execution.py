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

"""Create process-pump long-lived execution tasks for bootstrap adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)

ProcessPumpWork = Callable[[CancellationSource], None]


class ProcessPumpTaskHandle(Protocol):
    """Describe a process-pump long-lived task handle."""

    @property
    def is_finished(self) -> bool:
        """Return whether the process-pump task has finished."""

    def stop(self, *, reason: str) -> None:
        """Request process-pump cancellation."""


def create_process_pump_task(
    *,
    execution_runtime: object,
    dispatcher_factory: Callable[[], object],
    identity: TaskIdentity,
    context: ExecutionContext,
    work: ProcessPumpWork,
    thread_name: str,
) -> ProcessPumpTaskHandle:
    """Create and register one process-pump long-lived task."""

    return cast(
        ProcessPumpTaskHandle,
        cast(Any, execution_runtime).start_long_lived(
            "process_pump",
            f"{identity.domain}:{identity.request_id}",
            identity=identity,
            context=context,
            work=work,
            dispatcher=cast(Any, dispatcher_factory()),
            thread_name=thread_name,
        ),
    )


__all__ = [
    "ProcessPumpTaskHandle",
    "ProcessPumpWork",
    "create_process_pump_task",
]
