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

"""Build workflow surface reconciliation ports."""

from __future__ import annotations

from collections.abc import Callable, Mapping


from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceLifecycleState,
)
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    surface_result,
)


class _SessionPort:
    """Session-state port double for reconciler tests."""

    def __init__(self, active_workflow_id: str = "wf-a") -> None:
        """Store active workflow id and workflow mapping."""

        self._active_workflow_id = active_workflow_id
        self._workflows: Mapping[str, object] = {
            "wf-a": object(),
            "wf-b": object(),
        }

    @property
    def active_workflow_id(self) -> str:
        """Return active workflow id."""

        return self._active_workflow_id

    @property
    def workflows(self) -> Mapping[str, object]:
        """Return workflow state by id."""

        return self._workflows


class _CanvasPort:
    """Canvas port double recording route projection."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS

    def project_workflow_canvas(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record one canvas projection."""

        self._calls.append(f"canvas:{workflow_id}")
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=self.status,
            operation="project_workflow_canvas",
            elapsed_ms=1.0,
            cleanable=self.status is SurfaceRefreshStatus.SUCCESS,
        )

    def refresh_input_canvas_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Record input-canvas availability refresh."""

        self._calls.append(f"canvas-input:{workflow_id}")
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="refresh_input_canvas_availability",
            elapsed_ms=1.0,
        )


class _EditorPort:
    """Editor port double controlling projection results."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS
        self.call_complete = True

    def current_projection_state(
        self,
        workflow_id: str,
    ) -> WorkflowSurfaceLifecycleState:
        """Return a clean state for simple tests."""

        del workflow_id
        return WorkflowSurfaceLifecycleState.CLEAN

    def refresh_editor_surface(
        self,
        workflow_id: str,
        *,
        force: bool,
        on_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> SurfaceRefreshResult:
        """Record editor refresh and optionally complete synchronously."""

        self._calls.append(f"editor:{workflow_id}:{force}")
        result = surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.EDITOR,
            status=self.status,
            operation="refresh_editor_surface",
            elapsed_ms=1.0,
            cleanable=self.status
            in {SurfaceRefreshStatus.SUCCESS, SurfaceRefreshStatus.SKIPPED_CLEAN},
        )
        if on_complete is not None and self.call_complete:
            on_complete(result)
        return result

    def refresh_clean_editor_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh a clean editor projection."""

        return self.refresh_editor_surface(
            workflow_id,
            force=False,
            on_complete=None,
        )


class _OverridePort:
    """Override port double recording override reconciliation."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS
        self.schedule_status = SurfaceRefreshStatus.SUCCESS

    def last_materialized_defaults(self, workflow_id: str) -> bool:
        """Return no default materialization for tests."""

        del workflow_id
        return False

    def sync_override_state(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record override state sync."""

        return self._result(workflow_id, "override-sync")

    def apply_overrides_before_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Record pre-projection override apply."""

        return self._result(workflow_id, "override-pre")

    def materialize_default_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record default override materialization."""

        return self._result(workflow_id, "override-defaults")

    def apply_overrides_after_projection(
        self,
        workflow_id: str,
        *,
        materialized_defaults: bool,
    ) -> SurfaceRefreshResult:
        """Record post-projection override apply."""

        self._calls.append(f"override-post-defaults:{materialized_defaults}")
        return self._result(workflow_id, "override-post")

    def schedule_override_presentation_rebuild(
        self,
        workflow_id: str,
        token: ReconciliationToken,
        on_complete: Callable[[SurfaceRefreshResult], None] | None = None,
    ) -> SurfaceRefreshResult:
        """Record override rebuild scheduling and complete synchronously."""

        self._calls.append(f"override-schedule:{token.generation}")
        result = surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=self.schedule_status,
            operation="schedule_override_presentation_rebuild",
            elapsed_ms=1.0,
            cleanable=self.schedule_status is SurfaceRefreshStatus.SUCCESS,
        )
        if on_complete is not None:
            on_complete(result)
        return result

    def _result(self, workflow_id: str, operation: str) -> SurfaceRefreshResult:
        """Return configured override result for one operation."""

        self._calls.append(operation)
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=self.status,
            operation=operation,
            elapsed_ms=1.0,
            cleanable=self.status is SurfaceRefreshStatus.SUCCESS,
        )


class _GenerationPort:
    """Generation availability port double recording refreshes."""

    def __init__(self, calls: list[str]) -> None:
        """Store shared call log."""

        self._calls = calls
        self.status = SurfaceRefreshStatus.SUCCESS

    def refresh_generation_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Record generation availability refresh."""

        return self._result(workflow_id, "generation")

    def refresh_input_availability(self, workflow_id: str) -> SurfaceRefreshResult:
        """Record input availability refresh."""

        return self._result(workflow_id, "input")

    def _result(self, workflow_id: str, operation: str) -> SurfaceRefreshResult:
        """Return configured generation result."""

        self._calls.append(operation)
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.GENERATION_AVAILABILITY,
            status=self.status,
            operation=operation,
            elapsed_ms=1.0,
            cleanable=self.status is SurfaceRefreshStatus.SUCCESS,
        )
