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

"""Expose infrastructure execution adapters."""

from .long_lived_task import LongLivedTaskHandle
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
from .thread_pool_admission import ThreadPoolAdmission
from .thread_pool_lane import ThreadPoolExecutionLane

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
