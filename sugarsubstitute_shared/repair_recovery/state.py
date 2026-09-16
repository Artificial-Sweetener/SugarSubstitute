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

"""Define durable repair transition state independently of filesystem execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from sugarsubstitute_shared.repair_recovery.disposition import RepairDisposition


class RepairPhase(str, Enum):
    """Distinguish candidate work, rollback, and the durable commit decision."""

    PREPARED = "prepared"
    RELOCATING = "relocating"
    PROMOTING = "promoting"
    APPLYING = "applying"
    VALIDATING = "validating"
    ROLLING_BACK = "rolling_back"
    COMMITTED = "committed"


class RepairPathState(str, Enum):
    """Record move intent before execution and completion after execution."""

    PREPARED = "prepared"
    RELOCATING = "relocating"
    RELOCATED = "relocated"
    PROMOTING = "promoting"
    PROMOTED = "promoted"
    RESTORING = "restoring"
    RESTORED = "restored"


@dataclass(slots=True)
class RepairPathRecord:
    """Track one relative destination through an atomic move and its reversal."""

    destination: Path
    disposition: RepairDisposition
    had_destination: bool
    state: RepairPathState = RepairPathState.PREPARED


@dataclass(slots=True)
class RepairJournal:
    """Own the recovery decision and ordered path transitions for one repair."""

    quarantine_root: Path
    records: list[RepairPathRecord]
    phase: RepairPhase = RepairPhase.PREPARED
