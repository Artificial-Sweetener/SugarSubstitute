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

"""Bind shell signals to their owning presentation controllers."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.presentation.shell.comfy_runtime_actions import (
    comfy_runtime_actions_for,
)
from substitute.presentation.shell.cube_loader import load_cube_async
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)
from substitute.presentation.shell.workspace_input_canvas_adapter import (
    materialize_loaded_cube_input_canvas_for_view,
)
from substitute.presentation.shell.workflow_duplicate_controller import (
    duplicate_workflow_tab_for_view,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)


class MainWindowSignalBinder:
    """Own signal wiring that connects shell widgets to controller entry points."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose signals should be connected."""

        self._shell = shell

    def connect_generation_feedback_signals(self) -> None:
        """Connect generation feedback signals to view and controller handlers."""

        self._shell.clear_output_signal.connect(
            self._shell.generation_feedback_presenter.clear_output_for_workflow
        )
        self._shell.progress_update_signal.connect(
            self._shell.generation_action_controller.update_progress_labels
        )
        self._shell.preview_image_signal.connect(
            self._shell.workspace_canvas_actions.display_preview_image
        )
        self._shell.add_output_image_signal.connect(
            self._shell.workspace_canvas_actions.handle_add_output_image
        )

    def connect_menu_action_signals(self) -> None:
        """Connect shell menu and toolbar actions to controller entry points."""

        self._shell.cubeStackModeButton.toggled.connect(
            self._shell.cube_stack_presentation_controller.request_preference
        )
        self._shell._global_override_menu.triggered.connect(
            self._shell.workspace_search_actions.proxy_override_menu_toggled
        )

    def attach_app_orb_menu(self, app_orb_menu: Any) -> None:
        """Connect the frame-owned app orb menu to controller entry points."""

        self._shell.appOrbMenuButton = app_orb_menu
        self._shell.shell_chrome_controller.set_app_orb_workflow_file_actions_enabled(
            getattr(self._shell, "_active_workspace_route", None)
            != SETTINGS_WORKSPACE_ROUTE,
        )
        file_actions = self._shell.workspace_file_actions
        direct_workflow_actions = self._shell.direct_workflow_file_actions
        app_orb_menu.openRequested.connect(
            lambda: file_actions.on_load_clicked(
                file_dialog=QFileDialog,
                cube_loader=load_cube_async,
                icon_provider=FIF,
                message_box=QMessageBox,
                load_direct_workflow_document=direct_workflow_actions.load_document,
                can_load_direct_workflow_document=(
                    direct_workflow_actions.can_load_document
                ),
            )
        )
        app_orb_menu.saveRequested.connect(file_actions.on_save_clicked)
        app_orb_menu.saveAsRequested.connect(
            lambda: file_actions.on_save_as_clicked(
                file_dialog=QFileDialog,
            )
        )
        app_orb_menu.exportRequested.connect(
            lambda: file_actions.on_export_comfy_workflow_clicked(
                file_dialog=QFileDialog,
                message_box=QMessageBox,
            )
        )
        app_orb_menu.settingsRequested.connect(
            self._shell.workspace_controller.on_settings_tab_selected
        )
        app_orb_menu.comfyUiSettingsRequested.connect(
            self._open_comfyui_settings_webview
        )
        app_orb_menu.restartGuiRequested.connect(self._request_gui_restart)
        app_orb_menu.restartComfyRequested.connect(self._request_comfy_restart)

    def connect_search_signals(self) -> None:
        """Connect floating search UI signals to search action handlers."""

        search_actions = self._shell.workspace_search_actions
        self._shell.contextSearchBox.contextSearchChanged.connect(
            search_actions.on_context_search_changed
        )
        self._shell.contextSearchBox.cycleSearchMatchRequested.connect(
            search_actions.on_cycle_search_match
        )
        self._shell.contextSearchBox.cycleSearchMatchRequestedBackward.connect(
            search_actions.on_cycle_search_match_backward
        )
        closed_signal = getattr(self._shell.contextSearchBox, "closed", None)
        if closed_signal is not None:
            closed_signal.connect(search_actions.on_search_closed)

    def connect_workflow_tab_signals(self) -> None:
        """Connect workflow-tab signals to workflow lifecycle orchestration."""

        tabbar = self._shell.workflow_tabbar
        workflow_workspace = self._shell.workflow_workspace
        tabbar.workflowRenameRequested.connect(workflow_workspace.rename_workflow)
        tabbar.workflowRenameRequested.connect(
            lambda *_args: self._request_tab_structure_autosave()
        )
        tabbar.workflowAddRequested.connect(workflow_workspace.add_workflow)
        tabbar.workflowAddRequested.connect(
            lambda *_args: self._request_tab_structure_autosave()
        )
        tabbar.workflowSelected.connect(
            lambda workflow_id: workflow_workspace.activate_workflow(
                workflow_id,
                source="workflow_tab",
            )
        )
        tabbar.workflowSelected.connect(
            lambda *_args: self._request_tab_selection_autosave()
        )
        tabbar.workflowCloseRequested.connect(workflow_workspace.close_workflow)
        tabbar.workflowCloseRequested.connect(
            lambda *_args: self._request_tab_structure_autosave()
        )
        duplicate_requested = getattr(tabbar, "workflowDuplicateRequested", None)
        if duplicate_requested is not None:
            duplicate_requested.connect(self._duplicate_workflow_tab)
            duplicate_requested.connect(
                lambda *_args: self._request_tab_structure_autosave()
            )
        reopen_closed_requested = getattr(
            tabbar,
            "workflowReopenClosedRequested",
            None,
        )
        if reopen_closed_requested is not None:
            reopen_closed_requested.connect(self._reopen_latest_closed_workflow)
            reopen_closed_requested.connect(
                lambda *_args: self._request_tab_structure_autosave()
            )

    def connect_canvas_signals(
        self,
        *,
        input_canvas: Any,
        output_canvas: Any,
    ) -> None:
        """Connect canvas signals to workspace handlers and autosave requests."""

        canvas_actions = self._shell.workspace_canvas_actions
        output_canvas.activeOutputChanged.connect(
            canvas_actions.on_active_output_changed
        )
        output_canvas.activeOutputChanged.connect(
            lambda *_args: self._request_canvas_selection_autosave()
        )
        output_canvas.activeOutputGridChanged.connect(
            canvas_actions.on_active_output_grid_changed
        )
        output_canvas.activeOutputGridChanged.connect(
            lambda *_args: self._request_canvas_selection_autosave()
        )
        output_canvas.activeOutputSceneChanged.connect(
            canvas_actions.on_active_output_scene_changed
        )
        output_canvas.activeOutputSceneChanged.connect(
            lambda *_args: self._request_canvas_selection_autosave()
        )
        output_compare_changed = getattr(
            output_canvas,
            "activeOutputCompareChanged",
            None,
        )
        if output_compare_changed is not None:
            output_compare_changed.connect(canvas_actions.on_output_compare_changed)
            output_compare_changed.connect(
                lambda *_args: self._request_canvas_selection_autosave()
            )
        input_canvas.inputMaskSaved.connect(
            lambda *_args: self._request_canvas_selection_autosave()
        )
        input_canvas.inputImageLoaded.connect(
            lambda *_args: self._request_canvas_selection_autosave()
        )

    def connect_editor_panel_signals(self, editor_panel: Any) -> None:
        """Connect editor-panel signals to controller and presenter handlers."""

        editor_panel.currentCubeVisibleChanged.connect(
            self._shell.workspace_cube_stack_actions.highlight_tab_for_cube
        )
        editor_panel.inputImageChanged.connect(
            self._shell.input_canvas_presenter.handle_input_image_changed
        )
        editor_panel.inputImageClicked.connect(
            self._shell.input_canvas_presenter.handle_input_image_clicked
        )
        editor_panel.inputMaskChanged.connect(
            self._shell.input_canvas_presenter.handle_input_mask_changed
        )
        editor_panel.inputMaskClicked.connect(
            self._shell.input_canvas_presenter.handle_input_mask_clicked
        )
        editor_panel.promptSceneQueueRequested.connect(
            self._shell.workspace_scene_generation_actions.enqueue_prompt_scene
        )
        prompt_layout_changed = getattr(
            editor_panel,
            "promptEditorLayoutChanged",
            None,
        )
        if prompt_layout_changed is not None:
            prompt_layout_changed.connect(self._request_prompt_layout_autosave)

    def connect_cube_stack_signals(self, cube_stack: Any) -> None:
        """Connect cube-stack widget signals to cube action orchestration."""

        cube_picker_actions = self._shell.workspace_cube_picker_actions
        cube_stack_actions = self._shell.workspace_cube_stack_actions
        cube_stack.cubeRenameEditRequested.connect(
            cube_stack_actions.on_cube_rename_edit_requested
        )
        cube_stack.cubeRenameRequested.connect(
            lambda old_key, new_key: cube_stack_actions.on_cube_rename_requested(
                old_key,
                new_key,
                timer=QTimer,
            )
        )
        cube_stack.aliasEditingFinished.connect(
            cube_stack_actions.on_cube_rename_edit_finished
        )
        cube_stack.cubeMoveFinished.connect(cube_stack_actions.on_cube_move_finished)
        cube_stack.tabMouseReleased.connect(cube_stack_actions.on_tab_mouse_released)
        cube_stack.cubeAddRequested.connect(cube_picker_actions.show_cube_picker)
        cube_stack.cubeCloseRequested.connect(
            cube_stack_actions.on_cube_close_requested
        )
        cube_stack.cubeDuplicateRequested.connect(
            cube_stack_actions.on_cube_duplicate_requested
        )
        bypass_toggle_requested = getattr(
            cube_stack,
            "cubeBypassToggleRequested",
            None,
        )
        if bypass_toggle_requested is not None and hasattr(
            bypass_toggle_requested,
            "connect",
        ):
            bypass_toggle_requested.connect(
                cube_stack_actions.on_cube_bypass_toggle_requested
            )
        output_persistence_requested = getattr(
            cube_stack,
            "cubeOutputPersistenceToggleRequested",
            None,
        )
        if output_persistence_requested is not None and hasattr(
            output_persistence_requested,
            "connect",
        ):
            output_persistence_requested.connect(
                cube_stack_actions.on_cube_output_persistence_toggle_requested
            )
        reroute_signal = getattr(cube_stack, "cubeStackWheelRerouteRequested", None)
        if reroute_signal is not None and hasattr(reroute_signal, "connect"):
            reroute_signal.connect(self.route_cube_stack_wheel_to_editor_panel)

    def route_cube_stack_wheel_to_editor_panel(self, event: Any) -> None:
        """Forward non-scrollable cube-stack wheel input to the active editor."""

        active_panel = self._shell.active_editor_panel
        if active_panel is None:
            event.ignore()
            return
        active_panel.handle_external_wheel(event)

    def _reopen_latest_closed_workflow(self) -> None:
        """Reopen a closed workflow and autosave only after a real restoration."""

        reopened = self._shell.workflow_workspace.reopen_latest_closed_workflow()
        if not reopened:
            return
        request_session_autosave = getattr(
            self._shell,
            "request_session_autosave",
            None,
        )
        if callable(request_session_autosave):
            request_session_autosave()

    def _duplicate_workflow_tab(self, workflow_id: str) -> None:
        """Duplicate a workflow tab through the extracted duplicate owner."""

        duplicate_workflow_tab_for_view(
            view=self._shell,
            workflow_workspace=self._shell.workflow_workspace,
            workflow_duplicate_service=self._shell.workflow_duplicate_service,
            workflow_id=workflow_id,
            materialize_loaded_cube_input_canvas=lambda workflow_id, cube_alias: (
                materialize_loaded_cube_input_canvas_for_view(
                    self._shell,
                    workflow_id,
                    cube_alias,
                )
            ),
            schedule_rehydration=lambda callback: QTimer.singleShot(0, callback),
        )

    def _request_tab_structure_autosave(self) -> None:
        """Request autosave for workflow tab structure changes."""

        self._request_categorized_autosave(SessionAutosaveRequestCategory.TAB_STRUCTURE)

    def _request_canvas_selection_autosave(self) -> None:
        """Request autosave for canvas selection changes."""

        self._request_categorized_autosave(
            SessionAutosaveRequestCategory.CANVAS_SELECTION
        )

    def _request_prompt_layout_autosave(self) -> None:
        """Request autosave when prompt editor layout changes."""

        request_session_autosave = getattr(
            self._shell,
            "request_session_autosave",
            None,
        )
        if callable(request_session_autosave):
            request_session_autosave()

    def _request_tab_selection_autosave(self) -> None:
        """Request autosave for workflow tab selection changes."""

        controller = getattr(self._shell, "session_autosave_controller", None)
        request_tab_selection = getattr(
            controller,
            "request_tab_selection_autosave",
            None,
        )
        if callable(request_tab_selection):
            request_tab_selection()
            return
        request_session_autosave = getattr(
            self._shell,
            "request_session_autosave",
            None,
        )
        if callable(request_session_autosave):
            request_session_autosave()

    def _request_categorized_autosave(
        self,
        category: SessionAutosaveRequestCategory,
    ) -> None:
        """Request autosave for one category through the available shell port."""

        request_categorized = getattr(
            getattr(self._shell, "session_autosave_controller", None),
            "request_categorized_session_autosave",
            None,
        )
        if callable(request_categorized):
            request_categorized(category)
            return
        request_session_autosave = getattr(
            self._shell,
            "request_session_autosave",
            None,
        )
        if callable(request_session_autosave):
            request_session_autosave()

    def _request_comfy_restart(self) -> None:
        """Request a ComfyUI restart through the shell-owned restart hook."""

        actions = getattr(self._shell, "comfy_runtime_actions", None)
        request_restart = getattr(actions, "request_comfy_restart", None)
        if callable(request_restart):
            request_restart()
            return
        comfy_runtime_actions_for(self._shell).request_comfy_restart()

    def _request_gui_restart(self) -> None:
        """Request a full GUI reload through the bootstrap-installed hook."""

        request_restart = getattr(self._shell, "request_full_gui_reload", None)
        if callable(request_restart):
            request_restart()
            return
        QMessageBox.warning(
            self._shell,
            render_application_text(app_text("Restart the GUI")),
            render_application_text(
                app_text("GUI restart is not available in this session.")
            ),
        )

    def _open_comfyui_settings_webview(self) -> None:
        """Open ComfyUI Settings through the shell-owned runtime action."""

        actions = getattr(self._shell, "comfy_runtime_actions", None)
        open_settings = getattr(actions, "open_comfyui_settings_webview", None)
        if callable(open_settings):
            open_settings()
            return
        comfy_runtime_actions_for(self._shell).open_comfyui_settings_webview()


def main_window_signal_binder_for(shell: Any) -> MainWindowSignalBinder:
    """Return the composed signal binder for a shell."""

    binder = getattr(shell, "main_window_signal_binder", None)
    if isinstance(binder, MainWindowSignalBinder):
        return binder
    binder = MainWindowSignalBinder(shell)
    setattr(shell, "main_window_signal_binder", binder)
    return binder


__all__ = [
    "MainWindowSignalBinder",
    "main_window_signal_binder_for",
]
