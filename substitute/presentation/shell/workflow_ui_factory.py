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

"""Create and register live workflow widgets for the shell."""

from __future__ import annotations

from typing import Any, cast

from substitute.domain.workflow import WorkflowDocumentKind, WorkflowState
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.shell.main_window_signal_binder import (
    main_window_signal_binder_for,
)
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces
from substitute.presentation.workflows.cube_stack_view import (
    CubeCloseButtonDisplayMode,
    CubeStack,
)
from substitute.shared.startup_trace import trace_mark, trace_span


class WorkflowUiFactory:
    """Own workflow editor, cube-stack, and override-manager construction."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose workflow widgets should be created."""

        self._shell = shell

    def create_editor_panel(self, workflow_id: str) -> EditorPanel:
        """Create and configure a new editor panel for one workflow."""

        trace_mark(
            "main_window.create_new_editor_panel.start",
            workflow_id=workflow_id,
        )
        editor_panel = cast(
            EditorPanel,
            cast(Any, EditorPanel)(
                node_definition_gateway=self._shell.node_definition_gateway,
                prompt_autocomplete_gateway=self._shell.prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=(
                    self._shell.prompt_wildcard_catalog_gateway
                ),
                danbooru_url_import_service=self._shell.danbooru_url_import_service,
                danbooru_wiki_service=self._shell.danbooru_wiki_service,
                danbooru_image_preview_service=(
                    self._shell.danbooru_image_preview_service
                ),
                danbooru_recent_posts_service=(
                    self._shell.danbooru_recent_posts_service
                ),
                prompt_lora_catalog_service=self._shell.prompt_lora_catalog_service,
                scheduled_lora_provider=self._shell.scheduled_lora_provider,
                prompt_scheduled_lora_service=(
                    self._shell.prompt_scheduled_lora_service
                ),
                prompt_spellcheck_service=self._shell.prompt_spellcheck_service,
                prompt_feature_profile_service=(
                    self._shell.prompt_feature_profile_service
                ),
                wheel_adjustment_mode=(
                    self._shell.prompt_editor_preference_service.load_preferences().wheel_adjustment_mode
                ),
                model_catalog_service=self._shell.model_catalog_service,
                model_choice_resolver=self._shell.model_choice_resolver,
                thumbnail_asset_repository=self._shell.thumbnail_asset_repository,
                model_metadata_action_handler=(
                    self._shell.model_metadata_context_action_handler
                ),
                node_behavior_service=self._shell.node_behavior_service,
                user_preset_service=self._shell.user_preset_service,
                error_presenter=self._shell._error_presenter,
                workflow_issue_state=self._shell.workflow_issue_state,
                workflow_id=workflow_id,
                editor_panel_execution_factories=(
                    self._shell.editor_panel_execution_factories
                ),
            ),
        )
        editor_panel.mainwindow = self._shell
        editor_panel.setMinimumWidth(412)
        main_window_signal_binder_for(self._shell).connect_editor_panel_signals(
            editor_panel
        )
        trace_mark(
            "main_window.create_new_editor_panel.end",
            workflow_id=workflow_id,
        )
        return editor_panel

    def create_cube_stack(self, workflow_id: str) -> CubeStack:
        """Create and configure a new cube stack for one workflow."""

        trace_mark(
            "main_window.create_new_cube_stack.start",
            workflow_id=workflow_id,
        )
        cube_stack = CubeStack(self._shell)
        cube_stack.setMovable(True)
        cube_stack.setTabMaximumWidth(220)
        cube_stack.setCloseButtonDisplayMode(CubeCloseButtonDisplayMode.ON_HOVER)
        cube_stack.cubeMoved.connect(self.handle_cube_moved)
        main_window_signal_binder_for(self._shell).connect_cube_stack_signals(
            cube_stack
        )
        cube_stack.currentCubeChanged.connect(self.handle_cube_changed)
        self._shell.cube_stack_presentation_controller.prepare_stack(cube_stack)
        trace_mark(
            "main_window.create_new_cube_stack.end",
            workflow_id=workflow_id,
        )
        return cube_stack

    def handle_cube_changed(self, index: int) -> None:
        """Ignore per-step cube-tab changes; refresh happens on move completion."""

        _ = index

    def handle_cube_moved(self, from_index: int, to_index: int) -> None:
        """Ignore drag-in-progress updates until the cube move is finalized."""

        _ = from_index, to_index

    def create_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create required editor/override surfaces and an optional cube stack."""

        trace_mark(
            "main_window.create_new_workflow_ui.start",
            workflow_id=workflow_id,
            set_as_current=set_as_current,
        )
        with trace_span("main_window.create_new_workflow_ui.editor_panel"):
            editor_panel = self.create_editor_panel(workflow_id)
        with trace_span("main_window.create_new_workflow_ui.override_manager"):
            manager = GlobalOverridesManager(
                self._shell,
                pinned_override_service=self._shell.pinned_override_service,
                node_definition_gateway=self._shell.node_definition_gateway,
                prompt_autocomplete_gateway=self._shell.prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=(
                    self._shell.prompt_wildcard_catalog_gateway
                ),
                danbooru_url_import_service=(self._shell.danbooru_url_import_service),
                danbooru_wiki_service=self._shell.danbooru_wiki_service,
                danbooru_image_preview_service=(
                    self._shell.danbooru_image_preview_service
                ),
                danbooru_recent_posts_service=(
                    self._shell.danbooru_recent_posts_service
                ),
                prompt_lora_catalog_service=self._shell.prompt_lora_catalog_service,
                model_choice_snapshot_controller=(
                    editor_panel.model_choice_snapshot_controller
                ),
                thumbnail_asset_repository=self._shell.thumbnail_asset_repository,
                model_metadata_action_handler=(
                    self._shell.model_metadata_context_action_handler
                ),
            )
        manager.override_dropdown_btn = self._shell.override_dropdown_btn
        manager._global_override_menu = self._shell._global_override_menu

        self._shell.editor_panels[workflow_id] = editor_panel
        self._shell.override_managers[workflow_id] = manager

        self._shell.editor_panel_container.addWidget(editor_panel)
        with trace_span("main_window.create_new_workflow_ui.cube_stack"):
            cube_stack = self.reconcile_cube_stack_surface(
                workflow_id,
                set_as_current=set_as_current,
            )

        if set_as_current:
            self._shell.editor_panel_container.setCurrentWidget(editor_panel)
            self._shell.editor_panel = editor_panel

        trace_mark(
            "main_window.create_new_workflow_ui.end",
            workflow_id=workflow_id,
            editor_panel_count=len(self._shell.editor_panels),
            cube_stack_count=len(self._shell.cube_stacks),
        )
        return WorkflowUiSurfaces(
            cube_stack=cube_stack,
            editor_panel=editor_panel,
            created=True,
        )

    def reconcile_cube_stack_surface(
        self,
        workflow_id: str,
        *,
        set_as_current: bool,
    ) -> CubeStack | None:
        """Create or dispose the cube stack required by the workflow document kind."""

        workflow = self._workflow(workflow_id)
        cube_stack = cast(
            "CubeStack | None",
            self._shell.cube_stacks.get(workflow_id),
        )
        if workflow.document_kind is WorkflowDocumentKind.DIRECT_COMFY:
            if cube_stack is not None:
                self._shell.cube_stack_container.removeWidget(cube_stack)
                self._shell.cube_stacks.pop(workflow_id, None)
                cube_stack.deleteLater()
            if set_as_current:
                self._shell.cube_stack = None
            return None

        if cube_stack is None:
            cube_stack = self.create_cube_stack(workflow_id)
            self._shell.cube_stacks[workflow_id] = cube_stack
            self._shell.cube_stack_container.addWidget(cube_stack)
        if set_as_current:
            self._shell.cube_stack_container.setCurrentWidget(cube_stack)
            self._shell.cube_stack = cube_stack
        return cube_stack

    def _workflow(self, workflow_id: str) -> WorkflowState:
        """Return the typed workflow whose UI surfaces are being reconciled."""

        workflow = self._shell.workflow_session_service.workflows.get(workflow_id)
        if not isinstance(workflow, WorkflowState):
            raise RuntimeError(f"Workflow state is unavailable for {workflow_id!r}.")
        return workflow


def workflow_ui_factory_for(shell: Any) -> WorkflowUiFactory:
    """Return the composed workflow UI factory for a shell."""

    factory = getattr(shell, "workflow_ui_factory", None)
    if isinstance(factory, WorkflowUiFactory):
        return factory
    if callable(getattr(factory, "create_workflow_ui", None)):
        return cast(WorkflowUiFactory, factory)
    factory = WorkflowUiFactory(shell)
    setattr(shell, "workflow_ui_factory", factory)
    return factory


__all__ = [
    "WorkflowUiFactory",
    "workflow_ui_factory_for",
]
