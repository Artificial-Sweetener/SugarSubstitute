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

"""Create and hydrate the shell's blank initial workflow."""

from __future__ import annotations

from typing import Any
from typing import cast

from substitute.application.workflows import DEFAULT_WORKFLOW_TAB_LABEL
from substitute.presentation.shell.main_window_startup_trace import startup_phase
from substitute.presentation.shell.workflow_ui_factory import workflow_ui_factory_for
from substitute.shared.logging.logger import get_logger, log_info
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("presentation.shell.initial_workspace_controller")


class InitialWorkspaceController:
    """Own blank initial workspace creation for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose blank workspace should be initialized."""

        self._shell = shell

    def initialize_initial_workspace(self) -> None:
        """Create the first workflow UI pair and hydrate the editor surface."""

        initial_workflow_id = self._shell.workflow_session_service.active_workflow_id
        trace_mark(
            "main_window.initialize_initial_workspace.start",
            active_workflow_id=initial_workflow_id,
        )
        log_info(
            _LOGGER,
            "initial workspace initialization started",
            workflow_id=initial_workflow_id,
        )
        self.ensure_initial_workflow_tab(initial_workflow_id)
        cube_stack, editor_panel = self._create_workflow_ui(
            initial_workflow_id,
            set_as_current=True,
        )
        self._shell.cube_stack = cube_stack
        self._shell.editor_panel = editor_panel

        initial_manager = self._shell.active_override_manager
        if initial_manager is not None:
            initial_manager.sync_state_from_workflow()
            self._shell.active_workflow_surface_refresher.refresh_active_workflow_surface()

        with startup_phase(
            getattr(self._shell, "_startup_timer", None),
            "mainwindow.load_initial_editor_cubes",
        ):
            self.load_initial_editor_cubes(editor_panel)
        self._shell.canvas_route_controller.refresh_input_canvas_availability()
        trace_mark(
            "main_window.initialize_initial_workspace.end",
            workflow_id=initial_workflow_id,
        )
        log_info(
            _LOGGER,
            "initial workspace initialization completed",
            workflow_id=initial_workflow_id,
        )

    def ensure_initial_workflow_tab(self, workflow_id: str) -> None:
        """Create and select the fallback workflow tab when startup needs it."""

        trace_mark(
            "main_window.ensure_initial_workflow_tab.start", workflow_id=workflow_id
        )
        item_map = getattr(self._shell.workflow_tabbar, "itemMap", {})
        if workflow_id not in item_map:
            self._shell.workflow_tabbar.addTab(
                workflow_id,
                DEFAULT_WORKFLOW_TAB_LABEL,
            )
        select_workflow_tab = getattr(
            self._shell.workflow_tabbar,
            "select_workflow_tab",
            None,
        )
        if callable(select_workflow_tab):
            select_workflow_tab(workflow_id, emit=False)
            trace_mark(
                "main_window.ensure_initial_workflow_tab.end",
                workflow_id=workflow_id,
                selection_method="select_workflow_tab",
            )
            return
        self._shell.workflow_tabbar.setCurrentIndex(0)
        trace_mark(
            "main_window.ensure_initial_workflow_tab.end",
            workflow_id=workflow_id,
            selection_method="setCurrentIndex",
        )

    def _create_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool,
    ) -> tuple[object, object]:
        """Create workflow widgets through the composed workflow UI owner."""

        factory = getattr(self._shell, "workflow_ui_factory", None)
        create_workflow_ui = getattr(factory, "create_workflow_ui", None)
        if callable(create_workflow_ui):
            return cast(
                "tuple[object, object]",
                create_workflow_ui(workflow_id, set_as_current=set_as_current),
            )
        return workflow_ui_factory_for(self._shell).create_workflow_ui(
            workflow_id,
            set_as_current=set_as_current,
        )

    def load_initial_editor_cubes(self, editor_panel: Any) -> None:
        """Hydrate the initial editor surface from the active workflow."""

        workflow = self._shell.get_active_workflow()
        cube_count = len(workflow.cubes)
        stack_order_length = len(workflow.stack_order)
        trace_mark(
            "main_window.load_initial_editor_cubes.start",
            cube_count=cube_count,
            stack_order_length=stack_order_length,
        )
        log_info(
            _LOGGER,
            "initial editor cube load started",
            cube_count=cube_count,
            stack_order_length=stack_order_length,
        )

        def refresh_initial_lora_catalog() -> None:
            """Request startup LoRA metadata refresh after editor cube load."""

            self._shell.model_metadata_surface_refresh_controller.request_initial_lora_model_catalog_refresh(
                "initial_editor_cubes"
            )

        editor_panel.load_all_cubes(
            cube_entries=[],
            cube_states=workflow.cubes,
            stack_order=workflow.stack_order,
            on_complete=refresh_initial_lora_catalog,
        )
        trace_mark("main_window.load_initial_editor_cubes.end")
        log_info(
            _LOGGER,
            "initial editor cube load requested",
            cube_count=cube_count,
            stack_order_length=stack_order_length,
        )


def initial_workspace_controller_for(shell: Any) -> InitialWorkspaceController:
    """Return the composed initial workspace controller for a shell."""

    controller = getattr(shell, "initial_workspace_controller", None)
    if isinstance(controller, InitialWorkspaceController):
        return controller
    controller = InitialWorkspaceController(shell)
    setattr(shell, "initial_workspace_controller", controller)
    return controller


__all__ = [
    "InitialWorkspaceController",
    "initial_workspace_controller_for",
]
