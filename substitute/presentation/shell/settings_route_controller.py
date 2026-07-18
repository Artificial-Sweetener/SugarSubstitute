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

"""Own integrated Settings creation and shell route projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from substitute.presentation.settings.settings_workspace import (
    GENERATION_SECTION_ID,
    MODEL_SOURCES_SECTION_ID,
    create_settings_workspace,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.shell.search_overlay_controller import (
    search_overlay_controller_for,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.shell.settings_route_controller")


class SettingsRouteController:
    """Create Settings widgets and project the Settings route in the shell."""

    def __init__(
        self,
        shell: Any,
        *,
        error_presenter: ErrorReportPresenterProtocol | None,
    ) -> None:
        """Store shell route collaborators required for Settings creation."""

        self._shell = shell
        self._error_presenter = error_presenter

    def create_settings_workspace(self) -> None:
        """Create Settings widgets and attach them to workspace containers."""

        shell = self._shell
        settings_workspace = create_settings_workspace(
            comfy_environment_service=shell.comfy_environment_service,
            cube_library_management_service=shell.cube_library_management_service,
            cube_library_catalog_invalidated=shell.invalidate_cube_catalog_cache,
            cube_library_restart_required_changed=(
                self.handle_cube_library_restart_required_changed
            ),
            cube_library_post_restart_refresh=(
                self.refresh_runtime_contracts_after_cube_dependency_restart
            ),
            about_info_service=shell.about_info_service,
            appearance_runtime=shell.appearance_runtime,
            appearance_restart_coordinator=shell.appearance_restart_coordinator,
            comfy_connection_settings_service=shell.comfy_connection_settings_service,
            prompt_editor_preference_service=shell.prompt_editor_preference_service,
            danbooru_preference_service=shell.danbooru_preference_service,
            danbooru_cache_repository=shell.danbooru_cache_repository,
            civitai_preference_service=shell.civitai_preference_service,
            civitai_credential_service=shell.civitai_credential_service,
            civitai_cache_service=shell.civitai_cache_service,
            generation_preview_preference_service=(
                shell.generation_preview_preference_service
            ),
            output_organization_preference_service=(
                shell.output_organization_preference_service
            ),
            prompt_wildcard_preference_service=(
                shell.prompt_wildcard_preference_service
            ),
            prompt_wildcard_file_management_service=(
                shell.prompt_wildcard_file_management_service
            ),
            open_wildcard_management_modal=shell.open_wildcard_management_modal,
            prompt_editor_preferences_changed=(
                self.handle_prompt_editor_preferences_changed
            ),
            open_reconfigure_window=shell.request_reconfigure,
            show_restart_requirements=self.show_pending_restart_requirements,
            error_presenter=self._error_presenter,
            task_runner_factory=shell.settings_task_runner_factory,
            parent=shell,
        )
        shell.settings_navigation_pane = settings_workspace.navigation_pane
        shell.settings_workspace_panel = settings_workspace.panel
        shell.settings_workspace_layout.addWidget(shell.settings_navigation_pane)
        shell.settings_workspace_layout.addWidget(shell.settings_workspace_panel)
        shell.settings_workspace_layout.setStretch(0, 0)
        shell.settings_workspace_layout.setStretch(1, 1)
        self.connect_settings_toolbar_search()

    def connect_settings_toolbar_search(self) -> None:
        """Connect shell-toolbar Settings search to the Settings panel query."""

        search_box = getattr(self._shell, "settingsToolbarSearchBox", None)
        panel = getattr(self._shell, "settings_workspace_panel", None)
        if search_box is None or panel is None:
            return

        query_changed = getattr(search_box, "searchQueryChanged", None)
        connect_query_changed = getattr(query_changed, "connect", None)
        set_search_query = getattr(panel, "set_search_query", None)
        if callable(connect_query_changed) and callable(set_search_query):
            connect_query_changed(set_search_query)

        panel_query_changed = getattr(panel, "searchQueryChanged", None)
        connect_panel_query_changed = getattr(panel_query_changed, "connect", None)
        set_search_text = getattr(search_box, "set_search_text", None)
        if callable(connect_panel_query_changed) and callable(set_search_text):
            connect_panel_query_changed(set_search_text)

        search_query = getattr(panel, "search_query", None)
        if callable(search_query) and callable(set_search_text):
            set_search_text(str(search_query()))

    def handle_prompt_editor_preferences_changed(self) -> None:
        """Refresh active editor surfaces after prompt preference changes."""

        self._shell.active_workflow_surface_refresher.refresh_active_workflow_surface()

    def show_pending_restart_requirements(self) -> None:
        """Open the shared pending restart dialog from the toolbar controller."""

        controller = getattr(self._shell, "restart_requirement_ui_controller", None)
        show_if_pending = getattr(controller, "show_if_pending", None)
        if callable(show_if_pending):
            show_if_pending()

    def refresh_runtime_contracts_after_cube_dependency_restart(self) -> None:
        """Invalidate runtime caches after Cube Library dependency restart."""

        self._shell.invalidate_cube_catalog_cache()
        clear_object_info_cache = getattr(
            self._shell.node_definition_gateway,
            "clear_cache",
            None,
        )
        if callable(clear_object_info_cache):
            clear_object_info_cache()

    def handle_cube_library_restart_required_changed(self, required: bool) -> None:
        """Block generation while Cube Library dependency repair needs restart."""

        if required:
            self._shell._backend_state = "unavailable"
            self._shell.workspace_generation_controller.set_backend_available(
                False,
                message=(
                    "ComfyUI must restart before repaired cube dependencies can be used."
                ),
            )
            self._shell.generation_action_controller.apply_generation_action_availability()
            return
        self._shell.generation_action_controller.set_backend_state("ready")

    def project_settings_workspace(self) -> None:
        """Show the integrated Settings navigation pane and active page host."""

        self._shell._active_workspace_route = SETTINGS_WORKSPACE_ROUTE
        self._shell.shell_chrome_controller.set_workflow_override_toolbar_visible(False)
        self._shell.generation_action_controller.apply_generation_action_availability()
        self._shell.workflow_tabbar.clear_selection()
        self.show_settings_workspace()
        self._shell.contextSearchBox.hide()
        self._position_search_box()
        self._shell.editor_busy.refresh_active_surface()

    def project_model_sources_settings(self) -> None:
        """Project Settings directly to external model source configuration."""

        self.project_settings_workspace()
        self._shell.settings_workspace_panel.select_page(
            MODEL_SOURCES_SECTION_ID,
            animated=False,
        )

    def project_generation_model_download_settings(self) -> None:
        """Project Settings directly to missing-model and download controls."""

        self.project_settings_workspace()
        self._shell.settings_workspace_panel.select_page(
            GENERATION_SECTION_ID,
            animated=False,
        )

    def show_settings_workspace(self) -> None:
        """Show the Settings workspace route without changing workflow geometry."""

        self._shell.workspace_route_container.setCurrentWidget(
            self._shell.settings_workspace_page
        )
        chrome = self._shell.shell_chrome_controller
        self._shell.cube_stack_presentation_controller.set_workflow_route_active(False)
        chrome.set_orb_action_cluster_visible(False)
        chrome.set_settings_toolbar_search_visible(True)
        chrome.set_app_orb_workflow_file_actions_enabled(False)
        settings_panel = getattr(self._shell, "settings_workspace_panel", None)
        set_route_active = getattr(settings_panel, "set_route_active", None)
        if callable(set_route_active):
            set_route_active(True)

    def _position_search_box(self) -> None:
        """Ask the search overlay owner to refresh floating search geometry."""

        controller = getattr(self._shell, "search_overlay_controller", None)
        position_search_box = getattr(controller, "position_search_box", None)
        if callable(position_search_box):
            position_search_box()
            return
        search_overlay_controller_for(self._shell).position_search_box()

    def show_workflow_workspace(self) -> None:
        """Show the workflow workspace route without changing workflow geometry."""

        self._shell.workspace_route_container.setCurrentWidget(
            self._shell.workflow_workspace_page
        )
        chrome = self._shell.shell_chrome_controller
        self._shell.cube_stack_presentation_controller.set_workflow_route_active(True)
        chrome.set_orb_action_cluster_visible(True)
        chrome.set_settings_toolbar_search_visible(False)
        chrome.set_app_orb_workflow_file_actions_enabled(True)
        settings_panel = getattr(self._shell, "settings_workspace_panel", None)
        set_route_active = getattr(settings_panel, "set_route_active", None)
        if callable(set_route_active):
            set_route_active(False)

    def request_shell_appearance_reload(self) -> None:
        """Ask the top-level shell frame to rebuild around the current MainWindow."""

        full_gui_reload = getattr(self._shell, "request_full_gui_reload", None)
        workflow_session_service = getattr(
            self._shell,
            "workflow_session_service",
            None,
        )
        workflows = getattr(workflow_session_service, "workflows", {})
        log_info(
            _LOGGER,
            "mainwindow appearance reload requested",
            full_gui_reload_available=callable(full_gui_reload),
            active_workspace_route=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_id=getattr(
                workflow_session_service,
                "active_workflow_id",
                "",
            ),
            workflow_ids=tuple(workflows) if isinstance(workflows, Mapping) else (),
        )
        if callable(full_gui_reload):
            full_gui_reload()
            return
        top_level_window = self._shell.window()
        reload_shell = getattr(
            top_level_window,
            "reload_shell_backdrop_from_preferences",
            None,
        )
        if callable(reload_shell):
            reload_shell()


__all__ = ["SettingsRouteController"]
