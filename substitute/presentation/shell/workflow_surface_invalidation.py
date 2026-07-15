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

"""Track workflow surface maintenance requests for shell tab policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class WorkflowSurface(StrEnum):
    """Name workflow-scoped presentation surfaces that can need maintenance."""

    EDITOR = "editor"
    CANVAS = "canvas"
    OVERRIDES = "overrides"
    GENERATION_AVAILABILITY = "generation_availability"


class WorkflowInvalidationReason(StrEnum):
    """Describe why workflow surface maintenance was requested."""

    CUBE_ADDED = "cube_added"
    CUBE_DUPLICATED = "cube_duplicated"
    CUBE_REMOVED = "cube_removed"
    CUBE_REORDERED = "cube_reordered"
    CUBE_BYPASS_CHANGED = "cube_bypass_changed"
    CUBE_LOADED = "cube_loaded"
    RECIPE_LOADED = "recipe_loaded"
    WORKFLOW_DUPLICATED = "workflow_duplicated"
    WORKFLOW_RESTORED = "workflow_restored"
    NODE_DEFINITIONS_REFRESHED = "node_definitions_refreshed"
    GLOBAL_OVERRIDES_CHANGED = "global_overrides_changed"
    GENERATION_RESULT_MATERIALIZED = "generation_result_materialized"
    CANVAS_STATE_CHANGED = "canvas_state_changed"
    SEARCH_STATE_CHANGED = "search_state_changed"
    SESSION_ROUTE_CHANGED = "session_route_changed"
    EXPLICIT_RELOAD = "explicit_reload"


@dataclass(frozen=True, slots=True)
class WorkflowSurfaceDirtyState:
    """Return pending maintenance state for one workflow."""

    workflow_id: str
    dirty_surfaces: frozenset[WorkflowSurface]
    reasons: tuple[WorkflowInvalidationReason, ...]
    marked_dirty_at: datetime | None = None
    last_reconciled_at: datetime | None = None


@dataclass(slots=True)
class _WorkflowSurfaceRecord:
    """Store mutable maintenance state for one workflow."""

    dirty_surfaces: set[WorkflowSurface]
    reasons: list[WorkflowInvalidationReason]
    marked_dirty_at: datetime | None = None
    last_reconciled_at: datetime | None = None


class WorkflowSurfaceInvalidationService:
    """Track requested workflow surface maintenance for tab-switch policy."""

    def __init__(self) -> None:
        """Initialize an empty workflow maintenance registry."""

        self._records: dict[str, _WorkflowSurfaceRecord] = {}

    def mark_dirty(
        self,
        workflow_id: str,
        surfaces: set[WorkflowSurface] | frozenset[WorkflowSurface],
        reason: WorkflowInvalidationReason,
    ) -> None:
        """Mark workflow surfaces dirty for a specific reason."""

        if not workflow_id or not surfaces:
            return
        record = self._records.setdefault(
            workflow_id,
            _WorkflowSurfaceRecord(dirty_surfaces=set(), reasons=[]),
        )
        record.dirty_surfaces.update(surfaces)
        if reason not in record.reasons:
            record.reasons.append(reason)
        record.marked_dirty_at = datetime.now(UTC)

    def mark_clean(
        self,
        workflow_id: str,
        surfaces: set[WorkflowSurface] | frozenset[WorkflowSurface] | None = None,
    ) -> None:
        """Mark selected surfaces, or all surfaces, clean."""

        record = self._records.get(workflow_id)
        if record is None:
            self._records[workflow_id] = _WorkflowSurfaceRecord(
                dirty_surfaces=set(),
                reasons=[],
                last_reconciled_at=datetime.now(UTC),
            )
            return
        if surfaces is None:
            record.dirty_surfaces.clear()
            record.reasons.clear()
        else:
            record.dirty_surfaces.difference_update(surfaces)
            if not record.dirty_surfaces:
                record.reasons.clear()
        record.last_reconciled_at = datetime.now(UTC)

    def dirty_state(self, workflow_id: str) -> WorkflowSurfaceDirtyState:
        """Return current dirty state for one workflow."""

        record = self._records.get(workflow_id)
        if record is None:
            return WorkflowSurfaceDirtyState(
                workflow_id=workflow_id,
                dirty_surfaces=frozenset(),
                reasons=(),
            )
        return WorkflowSurfaceDirtyState(
            workflow_id=workflow_id,
            dirty_surfaces=frozenset(record.dirty_surfaces),
            reasons=tuple(record.reasons),
            marked_dirty_at=record.marked_dirty_at,
            last_reconciled_at=record.last_reconciled_at,
        )

    def is_clean(self, workflow_id: str) -> bool:
        """Return whether no tracked surface has pending maintenance."""

        return not self.dirty_state(workflow_id).dirty_surfaces

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Move pending maintenance state to a renamed workflow id."""

        if old_workflow_id == new_workflow_id:
            return
        record = self._records.pop(old_workflow_id, None)
        if record is None:
            return
        existing = self._records.get(new_workflow_id)
        if existing is None:
            self._records[new_workflow_id] = record
            return
        existing.dirty_surfaces.update(record.dirty_surfaces)
        for reason in record.reasons:
            if reason not in existing.reasons:
                existing.reasons.append(reason)
        existing.marked_dirty_at = record.marked_dirty_at or existing.marked_dirty_at

    def remove_workflow(self, workflow_id: str) -> None:
        """Forget pending maintenance state for a closed workflow."""

        self._records.pop(workflow_id, None)


ALL_WORKFLOW_SURFACES = frozenset(WorkflowSurface)
CUBE_STRUCTURE_SURFACES = frozenset(
    {
        WorkflowSurface.EDITOR,
        WorkflowSurface.CANVAS,
        WorkflowSurface.OVERRIDES,
        WorkflowSurface.GENERATION_AVAILABILITY,
    }
)
CANVAS_AND_GENERATION_SURFACES = frozenset(
    {
        WorkflowSurface.CANVAS,
        WorkflowSurface.GENERATION_AVAILABILITY,
    }
)

__all__ = [
    "ALL_WORKFLOW_SURFACES",
    "CANVAS_AND_GENERATION_SURFACES",
    "CUBE_STRUCTURE_SURFACES",
    "WorkflowInvalidationReason",
    "WorkflowSurface",
    "WorkflowSurfaceDirtyState",
    "WorkflowSurfaceInvalidationService",
]
