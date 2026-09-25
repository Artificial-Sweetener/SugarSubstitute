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

"""Define projection-session and completion ownership records."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

InsertCompletionPhase = Literal["first_usable", "complete"]


@dataclass(slots=True)
class PendingInsertCompletion:
    """Carry an incremental insert completion across a replacing projection."""

    workflow_id: str
    cube_alias: str
    token: object
    completion_phase: InsertCompletionPhase
    on_complete: Callable[[], None] | None
    reason: str
    superseded_reason: str | None = None
    resolved: bool = False


@dataclass(slots=True)
class PendingProjectionCompletion:
    """Carry a full-projection completion across a replacing projection."""

    workflow_id: str
    aliases: frozenset[str]
    on_complete: Callable[[], None]
    reason: str
    superseded_reason: str | None = None
    resolved: bool = False


@dataclass(slots=True)
class ActiveProjectionSession:
    """Track full-projection ownership for aliases being rebuilt."""

    workflow_id: str
    aliases: set[str]
    token: object
    claimed_completions: list[PendingInsertCompletion]
    projection_completions: list[PendingProjectionCompletion]
    resolved: bool = False


@dataclass(frozen=True, slots=True)
class ProjectionCompletionTransferResult:
    """Report completion ownership moved while superseding a projection session."""

    transferred_insert_count: int
    cancelled_insert_count: int
    transferred_projection_count: int
    cancelled_projection_count: int
