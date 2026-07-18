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

"""Adapt MainWindow workflow routing to its narrow projection port."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import cast


from substitute.domain.workflow import WorkflowState

from substitute.presentation.shell.search_overlay_controller import (
    search_overlay_controller_for,
)
from substitute.presentation.shell.workflow_surface_results import (
    WorkflowUiSurfaces,
)
from substitute.presentation.shell.restored_workflow_materializer import (
    restored_workflow_materializer_for,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
)

_LOGGER = get_logger("presentation.shell.main_window_workflow_route_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowWorkflowRouteAdapter:
    """Expose immediate workflow-route operations from a MainWindow instance."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind a narrow route API."""

        self._shell = shell

    @property
    def active_workflow_id(self) -> str:
        """Return the workflow session's active workflow id."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

    def show_workflow_workspace(self) -> None:
        """Show the workflow workspace route through the settings-route owner."""

        settings_route_controller = getattr(
            self._shell,
            "settings_route_controller",
            None,
        )
        show_workflow_workspace = getattr(
            settings_route_controller,
            "show_workflow_workspace",
            None,
        )
        if callable(show_workflow_workspace):
            show_workflow_workspace()

    def set_active_workspace_route(self, workflow_id: str) -> None:
        """Record the active workflow route on the shell."""

        setattr(self._shell, "_active_workspace_route", workflow_id)
        generation_action_controller = getattr(
            self._shell,
            "generation_action_controller",
            None,
        )
        apply_generation_action_availability = getattr(
            generation_action_controller,
            "apply_generation_action_availability",
            None,
        )
        if callable(apply_generation_action_availability):
            apply_generation_action_availability()

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Select the workflow tab through the shell tab bar."""

        tabbar = getattr(self._shell, "workflow_tabbar", None)
        select_workflow_tab = getattr(tabbar, "select_workflow_tab", None)
        if callable(select_workflow_tab):
            select_workflow_tab(workflow_id, emit=emit)

    def ensure_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Ensure cached workflow widgets exist without exposing shell maps."""

        return restored_workflow_materializer_for(self._shell).ensure_workflow_ui(
            workflow_id,
            set_as_current=set_as_current,
        )

    def set_current_cube_stack(self, workflow_id: str) -> bool:
        """Show the cached cube stack for one workflow."""

        cube_stack = self._cube_stacks().get(workflow_id)
        container = getattr(self._shell, "cube_stack_container", None)
        set_current_widget = getattr(container, "setCurrentWidget", None)
        if cube_stack is None or not callable(set_current_widget):
            return False
        set_current_widget(cube_stack)
        if hasattr(self._shell, "cube_stack"):
            setattr(self._shell, "cube_stack", cube_stack)
        return True

    def set_current_editor_panel(self, workflow_id: str) -> bool:
        """Show the cached editor panel for one workflow."""

        editor_panel = self._editor_panels().get(workflow_id)
        container = getattr(self._shell, "editor_panel_container", None)
        set_current_widget = getattr(container, "setCurrentWidget", None)
        if editor_panel is None or not callable(set_current_widget):
            return False
        set_current_widget(editor_panel)
        self._finalize_pending_visible_projection(editor_panel, workflow_id)
        if hasattr(self._shell, "editor_panel"):
            setattr(self._shell, "editor_panel", editor_panel)
        return True

    def present_cube_stack_for_workflow(
        self,
        workflow_id: str,
        *,
        animated: bool = True,
    ) -> None:
        """Project the active workflow's document kind through its sole owner."""

        session = getattr(self._shell, "workflow_session_service", None)
        workflows = getattr(session, "workflows", {})
        if not isinstance(workflows, Mapping):
            return
        workflow = workflows.get(workflow_id)
        if not isinstance(workflow, WorkflowState):
            return
        controller = getattr(
            self._shell,
            "cube_stack_presentation_controller",
            None,
        )
        activate_document_kind = getattr(controller, "activate_document_kind", None)
        if callable(activate_document_kind):
            activate_document_kind(workflow.document_kind, animated=animated)

    def _finalize_pending_visible_projection(
        self,
        editor_panel: object,
        workflow_id: str,
    ) -> None:
        """Flush completed editor background work after the panel becomes current."""

        finalize_pending = getattr(
            editor_panel,
            "finalize_pending_visible_projection",
            None,
        )
        if not callable(finalize_pending):
            return
        try:
            finalized = bool(finalize_pending())
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to finalize pending editor projection during route swap",
                workflow_id=workflow_id,
                error=error,
            )
            return
        if finalized:
            log_debug(
                _LOGGER,
                "Finalized pending editor projection during route swap",
                workflow_id=workflow_id,
            )

    def position_search_box(self) -> None:
        """Reposition lightweight editor overlays."""

        search_overlay_controller = getattr(
            self._shell,
            "search_overlay_controller",
            None,
        )
        position_search_box = getattr(
            search_overlay_controller,
            "position_search_box",
            None,
        )
        if callable(position_search_box):
            position_search_box()
            return
        search_overlay_controller_for(self._shell).position_search_box()

    def refresh_editor_busy_surface(self) -> None:
        """Refresh active editor busy presentation."""

        editor_busy = getattr(self._shell, "editor_busy", None)
        refresh_active_surface = getattr(editor_busy, "refresh_active_surface", None)
        if callable(refresh_active_surface):
            refresh_active_surface()

    def _cube_stacks(self) -> MutableMapping[str, object]:
        """Return workflow cube-stack mapping from the shell."""

        return cast(
            MutableMapping[str, object],
            getattr(self._shell, "cube_stacks", {}),
        )

    def _editor_panels(self) -> MutableMapping[str, object]:
        """Return workflow editor-panel mapping from the shell."""

        return cast(
            MutableMapping[str, object],
            getattr(self._shell, "editor_panels", {}),
        )
