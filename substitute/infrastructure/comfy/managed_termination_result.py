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

"""Define immutable termination evidence shared by lifecycle producers and consumers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sugarsubstitute_shared.localization import ApplicationText


class ManagedProcessTerminationStatus(Enum):
    """Describe the normalized result of one managed-process termination attempt."""

    NO_ACTION_REQUIRED = "no_action_required"
    TERMINATED_CONFIRMED = "terminated_confirmed"
    TERMINATION_UNCONFIRMED = "termination_unconfirmed"
    TERMINATION_COMMAND_FAILED = "termination_command_failed"


@dataclass(frozen=True)
class ManagedProcessTerminationResult:
    """Describe normalized termination facts for one managed process."""

    status: ManagedProcessTerminationStatus
    pid: int | None
    attempted: bool
    verification_timed_out: bool = False
    termination_command_timed_out: bool = False
    elapsed_ms: int = 0
    user_safe_detail: ApplicationText = ""
    diagnostic_detail: str = ""
