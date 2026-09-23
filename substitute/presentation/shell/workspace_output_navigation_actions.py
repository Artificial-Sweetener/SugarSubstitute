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

"""Own user navigation and transient preview actions for Output canvas."""

from __future__ import annotations

from typing import Protocol

from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)
from substitute.presentation.shell.workspace_preview_actions import (
    WorkspacePreviewActions,
)


class _WorkflowSessionProtocol(Protocol):
    """Expose the active workflow identity used by Output navigation."""

    active_workflow_id: str


class _NavigationSessionProtocol(Protocol):
    """Own automatic versus user-authored Output navigation mode."""

    def mark_user_navigation(self, workflow_id: str, workflow: object) -> object:
        """Make user-selected navigation sticky for the current session."""


class _OutputFocusProtocol(Protocol):
    """Persist user-authored Output route intent."""

    def set_active_output_uuid(self, workflow: object, uuid_str: str) -> object:
        """Persist one concrete Output selection."""

    def set_active_output_grid(
        self,
        workflow: object,
        source_key: str | None,
        scene_key: str | None = None,
    ) -> object:
        """Persist one Output grid selection."""

    def set_active_output_scene(
        self,
        workflow: object,
        selection: OutputSceneNavigationSelection,
    ) -> object:
        """Persist one scene-level Output selection."""

    def set_output_compare_state(self, workflow: object, state: object) -> None:
        """Persist Output comparison state."""


class WorkspaceOutputNavigationView(Protocol):
    """Describe the workspace boundary used by Output navigation actions."""

    workflow_session_service: _WorkflowSessionProtocol
    output_navigation_session_service: _NavigationSessionProtocol
    output_canvas_focus_service: _OutputFocusProtocol

    def get_active_workflow(self) -> object | None:
        """Return the active workflow state."""


class WorkspaceOutputNavigationActions:
    """Own persisted Output navigation intent and preview presentation."""

    def __init__(self, view: WorkspaceOutputNavigationView) -> None:
        """Store the Output workspace view and preview lifecycle owner."""

        self._view = view
        self._preview_actions = WorkspacePreviewActions(
            view,
            self._log_missing_output_canvas,
        )

    def on_active_output_changed(self, uuid_str: str) -> None:
        """Persist the currently selected output image id into workflow state."""

        active_workflow = self._view.get_active_workflow()
        if active_workflow is None:
            return
        self._mark_user_navigation(active_workflow)
        self._view.output_canvas_focus_service.set_active_output_uuid(
            active_workflow,
            uuid_str,
        )
        self._project_user_selected_output()

    def on_active_output_grid_changed(self, source_key: str) -> None:
        """Persist the currently selected output grid source into workflow state."""

        active_workflow = self._view.get_active_workflow()
        if active_workflow is None:
            return
        self._mark_user_navigation(active_workflow)
        self._view.output_canvas_focus_service.set_active_output_grid(
            active_workflow,
            source_key,
        )
        self._project_user_selected_output()

    def on_active_output_scene_changed(
        self,
        selection: OutputSceneNavigationSelection,
    ) -> None:
        """Persist one atomic scene-level Output route selection."""

        active_workflow = self._view.get_active_workflow()
        if active_workflow is None:
            return
        self._mark_user_navigation(active_workflow)
        self._view.output_canvas_focus_service.set_active_output_scene(
            active_workflow,
            selection,
        )
        self._project_user_selected_output()

    def on_output_compare_changed(self, state: object) -> None:
        """Persist output compare viewing state into workflow state."""

        active_workflow = self._view.get_active_workflow()
        if active_workflow is None:
            return
        self._mark_user_navigation(active_workflow)
        self._view.output_canvas_focus_service.set_output_compare_state(
            active_workflow,
            state,
        )
        self._project_user_selected_output()

    def display_preview_image(self, preview: object) -> None:
        """Display preview image only after strict identity and session checks."""

        self._preview_actions.display_preview_image(preview)

    def clear_output_previews(self, workflow_id: str) -> None:
        """Clear transient output previews for the active workflow only."""

        self._preview_actions.clear_output_previews(workflow_id)

    def _mark_user_navigation(self, active_workflow: object) -> None:
        """Make the active workflow's user-selected route sticky."""

        self._view.output_navigation_session_service.mark_user_navigation(
            self._view.workflow_session_service.active_workflow_id,
            active_workflow,
        )

    def _project_user_selected_output(self) -> None:
        """Request immediate projection after Output selection intent persists."""

        workflow_id = str(
            getattr(self._view.workflow_session_service, "active_workflow_id", "") or ""
        )
        if not workflow_id:
            return
        schedule = getattr(
            getattr(self._view, "output_image_pipeline", None),
            "schedule_user_selected_output_projection",
            None,
        )
        if callable(schedule):
            schedule(workflow_id)

    def _log_missing_output_canvas(self, workflow_id: str) -> None:
        """Log missing output canvas state through the feedback presenter."""

        generation_feedback_presenter_for(self._view).log_missing_output_canvas(
            workflow_id
        )


__all__ = ["WorkspaceOutputNavigationActions", "WorkspaceOutputNavigationView"]
