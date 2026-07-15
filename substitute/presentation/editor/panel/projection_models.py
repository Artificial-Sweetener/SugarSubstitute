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

"""Define data models shared by editor projection pipelines."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .projection_preparation import EditorProjectionPreparation
from .projection_session import ActiveProjectionSession, InsertCompletionPhase


@dataclass(frozen=True)
class ProjectedCubeBuild:
    """Track one staged cube-section build during full workflow projection."""

    cube_alias: str
    final_widget: object
    build_session: object
    started_at: float
    token: object
    build_elapsed_ms: float | None = None
    completed_at: float | None = None


@dataclass(frozen=True, slots=True)
class EditorFullProjectionLoadRequest:
    """Capture stable inputs for one full editor projection load."""

    cube_entries: tuple[tuple[str, object], ...]
    cube_states: dict[str, object] | None
    stack_order: Sequence[str] | None
    projection_signature: object | None
    on_complete: Callable[[], None] | None
    workflow_id: str
    previous_cube_states: dict[str, object] | None
    previous_stack_order: list[str] | None
    started_at: float


@dataclass(frozen=True, slots=True)
class EditorFullProjectionLoadPlan:
    """Carry prepared full-projection state through live and staged completion."""

    request: EditorFullProjectionLoadRequest
    projection_session: ActiveProjectionSession
    preparation: EditorProjectionPreparation
    ordered_widgets: tuple[tuple[str, object], ...]
    projected_builds: tuple[ProjectedCubeBuild, ...]


@dataclass(frozen=True, slots=True)
class EditorFullProjectionBusyState:
    """Track shell busy-overlay ownership for one staged full projection."""

    token: object | None
    started: bool


@dataclass(frozen=True, slots=True)
class EditorIncrementalInsertRequest:
    """Capture stable inputs for one incremental cube-section insert."""

    cube_alias: str
    cube_state: object
    cube_states: dict[str, object] | None
    stack_order: Sequence[str] | None
    on_complete: Callable[[], None] | None
    completion_phase: InsertCompletionPhase
    workflow_id: str
    previous_cube_states: dict[str, object] | None
    previous_stack_order: list[str] | None
    started_at: float


@dataclass(frozen=True, slots=True)
class EditorIncrementalInsertPlan:
    """Carry one incremental insert through build, first-usable, and completion."""

    request: EditorIncrementalInsertRequest
    preparation: EditorProjectionPreparation
    cube_widget: object
    build_token: object
    build_session: object | None
    built_new_widget: bool


@dataclass(slots=True)
class EditorIncrementalInsertCompletionState:
    """Track once-only first-usable and completion callbacks for an insert."""

    first_usable_completed: bool = False
    insert_completion_reported: bool = False
