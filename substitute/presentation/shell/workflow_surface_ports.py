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

"""Define narrow ports for workflow surface reconciliation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceDirtyState,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceLifecycleState,
)
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshResult,
)


class EditorSurfacePort(Protocol):
    """Expose editor projection operations without exposing the shell."""

    def current_projection_state(
        self,
        workflow_id: str,
    ) -> WorkflowSurfaceLifecycleState:
        """Return the authoritative editor projection state."""

    def refresh_editor_surface(
        self,
        workflow_id: str,
        *,
        force: bool,
        on_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> SurfaceRefreshResult:
        """Refresh the editor surface or prove it is already clean."""

    def refresh_clean_editor_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh lightweight clean editor projection state."""


class OverrideSurfacePort(Protocol):
    """Expose override toolbar reconciliation without exposing the shell."""

    def sync_override_state(self, workflow_id: str) -> SurfaceRefreshResult:
        """Synchronize override state from the workflow."""

    def apply_overrides_before_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Apply override state before editor projection."""

    def materialize_default_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Materialize default override controls after projection."""

    def apply_overrides_after_projection(
        self,
        workflow_id: str,
        *,
        materialized_defaults: bool,
    ) -> SurfaceRefreshResult:
        """Apply override state after editor projection."""

    def schedule_override_presentation_rebuild(
        self,
        workflow_id: str,
        token: ReconciliationToken,
        on_complete: Callable[[SurfaceRefreshResult], None] | None = None,
    ) -> SurfaceRefreshResult:
        """Schedule active override presentation rebuild."""


class GenerationAvailabilityPort(Protocol):
    """Expose lightweight generation/input availability refresh operations."""

    def refresh_generation_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh generation action availability for one workflow."""

    def refresh_input_availability(self, workflow_id: str) -> SurfaceRefreshResult:
        """Refresh input-canvas availability for one workflow."""


class WorkflowSessionStatePort(Protocol):
    """Expose workflow session state required by reconciliation."""

    @property
    def active_workflow_id(self) -> str:
        """Return the currently active workflow id."""

    @property
    def workflows(self) -> Mapping[str, object]:
        """Return workflow models by id."""


class WorkflowSurfaceInvalidationPort(Protocol):
    """Expose dirty-state maintenance used by workflow tab policy."""

    def mark_dirty(
        self,
        workflow_id: str,
        surfaces: set[WorkflowSurface] | frozenset[WorkflowSurface],
        reason: WorkflowInvalidationReason,
    ) -> None:
        """Mark surfaces dirty for one workflow."""

    def mark_clean(
        self,
        workflow_id: str,
        surfaces: set[WorkflowSurface] | frozenset[WorkflowSurface] | None = None,
    ) -> None:
        """Mark selected surfaces, or all surfaces, clean."""

    def dirty_state(self, workflow_id: str) -> WorkflowSurfaceDirtyState:
        """Return pending dirty state for one workflow."""

    def is_clean(self, workflow_id: str) -> bool:
        """Return whether the workflow has no dirty tracked surfaces."""


class SessionAutosavePort(Protocol):
    """Expose debounced session autosave requests to shell policy."""

    def request(self, category: SessionAutosaveRequestCategory) -> None:
        """Request a debounced save for one interaction category."""

    def flush(self, category: SessionAutosaveRequestCategory) -> None:
        """Flush a pending save category immediately."""


__all__ = [
    "EditorSurfacePort",
    "GenerationAvailabilityPort",
    "OverrideSurfacePort",
    "SessionAutosavePort",
    "WorkflowSessionStatePort",
    "WorkflowSurfaceInvalidationPort",
]
