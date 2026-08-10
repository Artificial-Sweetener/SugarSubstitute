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

"""Expose infrastructure execution adapters without eager backend imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cutecanvas_execution_backend import CuteCanvasExecutionBackend
    from .host_execution_model import (
        HostExecutionJob,
        HostExecutionLeaseRelease,
        HostExecutionRequirements,
        HostExecutionResource,
        HostExecutionSnapshot,
    )
    from .host_execution_scheduler import (
        HostExecutionPolicy,
        HostExecutionRejected,
        HostExecutionScheduler,
    )
    from .long_lived_task import LongLivedTaskHandle
    from .thread_pool_admission import ThreadPoolAdmission
    from .thread_pool_lane import ThreadPoolExecutionLane

_EXPORT_MODULES = {
    "CuteCanvasExecutionBackend": (
        "substitute.infrastructure.execution.cutecanvas_execution_backend"
    ),
    "HostExecutionJob": "substitute.infrastructure.execution.host_execution_model",
    "HostExecutionLeaseRelease": (
        "substitute.infrastructure.execution.host_execution_model"
    ),
    "HostExecutionPolicy": (
        "substitute.infrastructure.execution.host_execution_scheduler"
    ),
    "HostExecutionRejected": (
        "substitute.infrastructure.execution.host_execution_scheduler"
    ),
    "HostExecutionRequirements": (
        "substitute.infrastructure.execution.host_execution_model"
    ),
    "HostExecutionResource": (
        "substitute.infrastructure.execution.host_execution_model"
    ),
    "HostExecutionScheduler": (
        "substitute.infrastructure.execution.host_execution_scheduler"
    ),
    "HostExecutionSnapshot": (
        "substitute.infrastructure.execution.host_execution_model"
    ),
    "LongLivedTaskHandle": "substitute.infrastructure.execution.long_lived_task",
    "ThreadPoolAdmission": (
        "substitute.infrastructure.execution.thread_pool_admission"
    ),
    "ThreadPoolExecutionLane": ("substitute.infrastructure.execution.thread_pool_lane"),
}

__all__ = [
    "LongLivedTaskHandle",
    "CuteCanvasExecutionBackend",
    "HostExecutionJob",
    "HostExecutionLeaseRelease",
    "HostExecutionPolicy",
    "HostExecutionRejected",
    "HostExecutionRequirements",
    "HostExecutionResource",
    "HostExecutionScheduler",
    "HostExecutionSnapshot",
    "ThreadPoolAdmission",
    "ThreadPoolExecutionLane",
]


def __getattr__(name: str) -> object:
    """Load one execution adapter only when a caller requests it."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return stable lazy-export names for interactive inspection."""

    return sorted({*globals(), *__all__})
