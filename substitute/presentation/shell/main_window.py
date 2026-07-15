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

"""Render the primary shell window and delegate workspace orchestration."""

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QWidget,
)
from substitute.application.workspace_state import (
    WorkflowSnapshot,
)
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)
from substitute.presentation.shell.main_window_dependencies import (
    MainWindowDependencies,
)
from substitute.presentation.shell.main_window_composition import (
    connect_shell_signals,
    capture_dependencies,
    compose_editor_busy_controller,
    compose_editor_metadata_controllers,
    compose_input_canvas_controllers,
    compose_output_canvas_controllers,
    compose_runtime_controllers,
    compose_shell_controllers,
    compose_workflow_lifecycle_services,
)
from substitute.presentation.shell.main_window_menu import build_main_window_menu
from substitute.presentation.shell.main_window_workspace import (
    build_main_window_workspace,
)
from substitute.presentation.shell.main_window_startup_trace import (
    startup_phase as _startup_phase,
)
from substitute.presentation.shell.app_orb_menu import AppOrbMenuButton
from substitute.presentation.shell.dock_widgets import handle_dock_closed
from substitute.presentation.shell.prompt_interaction_activity import (
    PromptInteractionActivityTracker,
)
from substitute.presentation.shell.shell_resize_handler import (
    handle_shell_resize_side_effects,
)
from substitute.presentation.shell.titlebar_buttons import (
    GenerationTitleBarRunControl,
)
from substitute.presentation.shell.window_frame import ShellBackdropMode
from substitute.presentation.workflows.cube_stack_view import (
    CubeStack,
)


class MainWindow(QMainWindow):
    """Render the top-level shell and wire widgets to workspace orchestration."""

    progress_update_signal = Signal(float, object)
    resize_requested = Signal(int)
    clear_output_signal = Signal(str)
    preview_image_signal = Signal(object)
    add_output_image_signal = Signal(str, QImage, object)
    comfy_output_panel_visibility_changed = Signal(bool)
    node_definition_refreshed = Signal(object)
    restore_finalized = Signal()
    backend_state_changed = Signal(str)
    cube_library_updates_pending = Signal()
    cube_library_follow_latest_updates_requested = Signal(object)

    def __init__(
        self,
        menu_container: QWidget,
        *,
        dependencies: MainWindowDependencies,
        startup_timer: Any | None = None,
        generation_action_cluster: GenerationTitleBarRunControl | None = None,
        backdrop_mode: ShellBackdropMode | None = ShellBackdropMode.MICA,
    ) -> None:
        """Construct shell widgets, workflow surfaces, and controller wiring."""

        super().__init__()

        self.prompt_interaction_activity_tracker = PromptInteractionActivityTracker(
            parent=self
        )
        app = QCoreApplication.instance()
        if app is not None:
            self.prompt_interaction_activity_tracker.install_on_application(app)
        self._pending_cubes: dict[str, int] = {}
        self._pending_restored_workflow_snapshots: dict[str, WorkflowSnapshot] = {}
        self._restored_workflow_snapshots_by_id: dict[str, WorkflowSnapshot] = {}
        self._detached_for_gui_reload = False
        self._comfy_restart_request_handler: Callable[[], None] | None = None
        self._startup_timer = startup_timer
        with _startup_phase(startup_timer, "mainwindow.capture_dependencies"):
            capture_dependencies(self, dependencies)
        with _startup_phase(startup_timer, "mainwindow.build_menu"):
            menu_parts = build_main_window_menu(
                self,
                backdrop_mode=backdrop_mode,
                workspace_controller=self.workspace_controller,
            )
        self.menu_bar = menu_parts.menu_bar
        self.menu_bar_layout = menu_parts.menu_bar_layout
        self.orbActionCluster = menu_parts.orb_action_cluster
        self.appOrbMenuButton: AppOrbMenuButton | None = None
        self.cubeStackModeButton = menu_parts.cube_stack_mode_button
        self.override_dropdown_btn = menu_parts.override_dropdown_btn
        self.pendingRestartButton = menu_parts.pending_restart_button
        self.settingsToolbarSearchBox = menu_parts.settings_toolbar_search_box
        self.contextSearchBox = menu_parts.context_search_box
        self._global_override_menu = menu_parts.global_override_menu
        self.override_managers = menu_parts.override_managers
        self.generationActionCluster = generation_action_cluster
        self.generation_titlebar_control_registry: (
            GenerationTitleBarControlRegistry | None
        ) = None
        self._generation_action_cluster_mode_callback: Callable[[str], None] | None = (
            None
        )
        with _startup_phase(startup_timer, "mainwindow.build_workspace"):
            workspace_parts = build_main_window_workspace(
                self,
                backdrop_mode=backdrop_mode,
                menu_container=menu_container,
                comfy_output_stream=dependencies.comfy_output_stream,
                output_preview_registry=self.output_preview_registry,
                open_single_external_editor=(
                    self.workspace_canvas_actions.open_image_in_external_editor
                ),
                open_all_external_editor=(
                    self.workspace_canvas_actions.open_images_in_external_editor
                ),
                reveal_output_asset=self.workspace_canvas_actions.reveal_output_asset,
                configure_output_thumbnail_context=(
                    dependencies.configure_output_thumbnail_context
                ),
            )
        self.workflow_tab_service = workspace_parts.workflow_tab_service
        self.workflow_session_service = workspace_parts.workflow_session_service
        compose_workflow_lifecycle_services(self)
        self.workflow_tabbar = workspace_parts.workflow_tabbar
        self.workspace_body_material_surface = (
            workspace_parts.workspace_body_material_surface
        )
        self.workspace_route_container = workspace_parts.workspace_route_container
        self.workflow_workspace_page = workspace_parts.workflow_workspace_page
        self.settings_workspace_page = workspace_parts.settings_workspace_page
        self.settings_workspace_layout = workspace_parts.settings_workspace_layout
        self.cube_stack_container = workspace_parts.cube_stack_container
        self.editor_output_container = workspace_parts.editor_output_container
        self.editor_panel_container = workspace_parts.editor_panel_container
        self.editorBusyOverlay = workspace_parts.editor_busy_overlay
        compose_editor_busy_controller(self)
        self.comfy_output_panel = workspace_parts.comfy_output_panel
        self.editor_output_splitter = workspace_parts.editor_output_splitter
        self.canvas_tabs = workspace_parts.canvas_tabs
        self.input_canvas_state_service = workspace_parts.input_canvas_state_service
        self.output_canvas_state_service = workspace_parts.output_canvas_state_service
        self.output_canvas_projection_coordinator = (
            workspace_parts.output_canvas_projection_coordinator
        )
        self.workflow_canvas_projection_coordinator = (
            workspace_parts.workflow_canvas_projection_coordinator
        )
        self.canvas_image_registry = workspace_parts.canvas_image_registry
        self.output_floating_chrome_factory = (
            workspace_parts.output_floating_chrome_factory
        )
        compose_output_canvas_controllers(self)
        compose_input_canvas_controllers(self)
        self.canvas_tabs_container = workspace_parts.canvas_tabs_container
        self.sidePanelHost = workspace_parts.side_panel_host
        self.splitter = workspace_parts.splitter
        self.progressOverlay = workspace_parts.progress_overlay
        self.workflowOverlayBar = workspace_parts.workflow_overlay_bar
        self.samplerOverlayBar = workspace_parts.sampler_overlay_bar
        self.cube_stacks: dict[str, CubeStack] = {}
        self.editor_panels: dict[str, EditorPanel] = {}
        compose_editor_metadata_controllers(self)
        compose_shell_controllers(self)
        compose_runtime_controllers(self, dependencies)

        central_layout = self.centralWidget().layout()
        central_layout.insertWidget(0, self.menu_bar)
        central_layout.setStretch(0, 0)
        central_layout.setStretch(1, 1)

        connect_shell_signals(
            self,
            startup_timer,
            single_shot=QTimer.singleShot,
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Route workspace fallback drag-enter events through the drop controller."""

        if self.workspace_drop_controller.handle_drag_enter(event):
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Route workspace fallback drag-move events through the drop controller."""

        if self.workspace_drop_controller.handle_drag_move(event):
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Route workspace fallback drops through shared recipe loading."""

        if self.workspace_drop_controller.handle_drop(event):
            return
        super().dropEvent(event)

    def request_reconfigure(self) -> None:
        """Open the shared onboarding surface in reconfigure mode."""

        self._reconfigure_window = self._open_reconfigure_window()

    def request_session_autosave(self) -> None:
        """Schedule a debounced save of the current session snapshot."""

        self.session_autosave_controller.request_session_autosave()

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        """Route global shell events to the owning presentation controllers."""

        result = self.shell_event_filter_controller.handle_event_filter_event(event)
        if result is not None:
            return cast(bool, result)
        return super().eventFilter(source, event)

    def get_active_workflow(self) -> object:
        """Return the currently active workflow session model."""

        return self.shell_active_surface_controller.get_active_workflow()

    @property
    def active_editor_panel(self) -> EditorPanel | None:
        """Returns the currently visible editor panel."""

        return self.shell_active_surface_controller.active_editor_panel()

    @property
    def active_cube_stack(self) -> "CubeStack | None":
        """Returns the currently visible cube stack."""

        return self.shell_active_surface_controller.active_cube_stack()

    @property
    def active_override_manager(self) -> object | None:
        """Returns the override manager for the currently active workflow."""

        return self.shell_active_surface_controller.active_override_manager()

    def on_dock_closed(self, dock_widget: QDockWidget, content_widget: QWidget) -> None:
        """Re-dock floating widgets instead of allowing them to close permanently."""

        handle_dock_closed(self, dock_widget, content_widget)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep shell overlays aligned when the main window geometry changes."""

        handle_shell_resize_side_effects(self)
        super().resizeEvent(event)
