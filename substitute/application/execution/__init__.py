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

"""Expose application-wide execution contracts and policies."""

from .cancellation import (
    CancellationController,
    CancellationSource,
    CancellationToken,
    NeverCancelled,
)
from .context import ExecutionContext, SAFE_EXECUTION_FIELD_NAMES, SafeFieldValue
from .dispatcher import DirectExecutionDispatcher
from .executor import (
    ExecutionLaneSaturatedError,
    ExecutionLane,
    TaskHandle,
    TaskRequest,
    TaskSubmitter,
    TaskWork,
)
from .freshness import (
    DropReason,
    FreshnessDecision,
    FreshnessMismatch,
    FreshnessRequirement,
    StaleResultGuard,
)
from .identity import IdentityPartValue, TaskIdentity
from .outcome import TaskOutcome, TaskStatus, TaskTimings
from .policies import (
    BlockingSingleFlight,
    BoundedTaskQueue,
    FireAndLogSubmitter,
    KeyedSingleFlight,
    LatestWinsRequestChannel,
    ScopedKeyedSingleFlight,
    SerialTaskGate,
    SingleFlightCancelled,
)
from .task_scope import TaskScope

__all__ = [
    "BoundedTaskQueue",
    "BlockingSingleFlight",
    "CancellationController",
    "CancellationSource",
    "CancellationToken",
    "DropReason",
    "ExecutionContext",
    "ExecutionLaneSaturatedError",
    "ExecutionLane",
    "DirectExecutionDispatcher",
    "FireAndLogSubmitter",
    "FreshnessDecision",
    "FreshnessMismatch",
    "FreshnessRequirement",
    "IdentityPartValue",
    "KeyedSingleFlight",
    "LatestWinsRequestChannel",
    "NeverCancelled",
    "SAFE_EXECUTION_FIELD_NAMES",
    "SafeFieldValue",
    "ScopedKeyedSingleFlight",
    "SerialTaskGate",
    "SingleFlightCancelled",
    "StaleResultGuard",
    "TaskHandle",
    "TaskIdentity",
    "TaskOutcome",
    "TaskRequest",
    "TaskScope",
    "TaskStatus",
    "TaskSubmitter",
    "TaskTimings",
    "TaskWork",
]
