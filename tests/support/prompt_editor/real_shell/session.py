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

"""Mount the production shell composition used by real prompt-editor scenarios."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import warnings

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QWidget,
)
from substitute.presentation.shell.app_orb_action_cluster import (
    AppOrbCubeStackButton,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.generation import (
    VisualAuthorizationService,
    WorkflowProgressService,
)
from substitute.application.localization import (
    ActiveComfyNodeCatalogStore,
    NodePresentationService,
)
from substitute.application.danbooru import (
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    ThumbnailAssetRepository,
)
from substitute.application.node_behavior import NodeBehaviorService
from substitute.application.overrides import PinnedOverrideService
from substitute.application.ports import (
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.application.user_presets import UserPresetService
from substitute.application.workflows import WorkflowSessionService
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.cube_stack_presentation_controller import (
    CubeStackPresentationController,
)
from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)
from substitute.presentation.shell.main_window_dependencies import (
    InstallationPathBundle,
)
from substitute.presentation.shell.main_window_workspace import (
    build_main_window_workspace,
)
from substitute.presentation.shell.workspace_canvas_actions import (
    WorkspaceCanvasActions,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_workspace_coordinator import (
    WorkflowWorkspaceCoordinator,
    WorkflowWorkspaceView,
)
from substitute.presentation.shell.workflow_ui_factory import WorkflowUiFactory
from substitute.presentation.shell.workspace_splitter_controller import (
    WorkspaceSplitterController,
)
from substitute.presentation.workflows.cube_stack_view import CubeStack
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptWildcardCatalogGateway,
    RecordingPromptAutocompleteGateway,
)
from tests.support.execution import immediate_editor_panel_execution_factories
from tests.support.prompt_editor.real_shell.session_support import (
    _ErrorPresenter,
    _GenerationJobQueueService,
    _ProgressBar,
    _PromptInteractionTracker,
    _PromptNodeDefinitionGateway,
    _StaticPromptFeatureProfileService,
)
from cutecanvas import ExecutionRuntime


class PromptEditorRealShell(QMainWindow):
    """Own the real workspace and real prompt editor panel under test."""

    progress_update_signal = Signal(float, object)
    resize_requested = Signal(int)
    clear_output_signal = Signal(str)
    preview_image_signal = Signal(object)
    add_output_image_signal = Signal(str, QImage, object)
    workflow_tabbar: Any
    workflow_workspace: WorkflowWorkspaceCoordinator
    editor_panel: EditorPanel

    def __init__(
        self,
        autocomplete_gateway: RecordingPromptAutocompleteGateway,
        *,
        canvas_execution_runtime: ExecutionRuntime,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway | None = None,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        danbooru_url_import_service: DanbooruUrlImportService | None = None,
        danbooru_wiki_service: DanbooruWikiContentService | None = None,
        prompt_feature_profile: PromptEditorFeatureProfile | None = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        user_preset_service: UserPresetService | None = None,
        model_catalog_service: ModelCatalogLookup | None = None,
    ) -> None:
        """Build the real shell scaffold and deterministic prompt services."""

        super().__init__()
        self.resize(1040, 760)
        self.node_definition_gateway = _PromptNodeDefinitionGateway()
        self.prompt_autocomplete_gateway = autocomplete_gateway
        self.prompt_wildcard_catalog_gateway = (
            prompt_wildcard_catalog_gateway or EmptyPromptWildcardCatalogGateway()
        )
        self.node_behavior_service = NodeBehaviorService(
            node_definition_gateway=self.node_definition_gateway
        )
        self._node_catalog_store = ActiveComfyNodeCatalogStore()
        self.node_presentation_service = NodePresentationService(
            lambda: self._node_catalog_store.snapshot("en"),
            application_text_renderer=render_application_text,
        )
        self.danbooru_url_import_service = danbooru_url_import_service
        self.danbooru_wiki_service = danbooru_wiki_service
        self.danbooru_image_preview_service = None
        self.danbooru_recent_posts_service = None
        self.prompt_lora_catalog_service = prompt_lora_catalog_service
        self.scheduled_lora_provider = None
        self.prompt_scheduled_lora_service = None
        self.prompt_spellcheck_service = prompt_spellcheck_service
        self.prompt_feature_profile_service = (
            None
            if prompt_feature_profile is None
            else _StaticPromptFeatureProfileService(prompt_feature_profile)
        )
        self.prompt_editor_preference_service = SimpleNamespace(
            load_preferences=lambda: SimpleNamespace(
                wheel_adjustment_mode=wheel_adjustment_mode
            )
        )
        self.prompt_wheel_adjustment_mode = wheel_adjustment_mode
        self.model_catalog_service = model_catalog_service
        self.model_choice_resolver = None
        self.model_metadata_context_action_handler = None
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.user_preset_service = user_preset_service
        self.workflow_issue_state = None
        self.editor_panel_execution_factories = (
            immediate_editor_panel_execution_factories()
        )

        self.path_bundle = _path_bundle()
        self.output_preview_registry = OutputPreviewRegistry()
        self.visual_authorization_service = VisualAuthorizationService()
        self.workflow_progress_service = WorkflowProgressService()
        self.prompt_interaction_activity_tracker = _PromptInteractionTracker()
        self.generation_job_queue_service = _GenerationJobQueueService()
        self.workflow_surface_invalidation_service = (
            WorkflowSurfaceInvalidationService()
        )
        self.workflow_activity_service = SimpleNamespace(
            record_output=lambda *_args, **_kwargs: False
        )
        self.progressOverlay = QWidget()
        self.workflowOverlayBar = _ProgressBar()
        self.samplerOverlayBar = _ProgressBar()
        self.progress_overlay_controller = SimpleNamespace(
            position_progress_overlay=lambda *_args, **_kwargs: None
        )
        self.generation_progress_strip_registry = SimpleNamespace(
            apply_progress_view=lambda *_args, **_kwargs: None
        )
        self.generation_action_controller = GenerationActionController(self)
        self.settings_route_controller = SimpleNamespace(
            show_workflow_workspace=lambda *_args, **_kwargs: None
        )
        self.search_overlay_controller = SimpleNamespace(
            position_search_box=lambda *_args, **_kwargs: None
        )
        self.editor_busy = SimpleNamespace(
            refresh_active_surface=lambda *_args, **_kwargs: None
        )
        self.output_scene_run_service = SimpleNamespace(run_for_id=lambda _run_id: None)
        self._comfy_output_stream = TerminalOutputStream(max_lines=50)
        self._taskbar_progress_presenter = SimpleNamespace(
            clear_progress=lambda: None,
            set_progress=lambda _value: None,
        )
        self.cube_stacks: dict[str, CubeStack] = {}
        self.editor_panels: dict[str, EditorPanel] = {}
        self.override_managers: dict[str, object] = {}
        self._pending_restored_workflow_snapshots: dict[str, object] = {}
        self._restored_workflow_snapshots_by_id: dict[str, object] = {}
        self.generationActionCluster = None
        self.error_reports: list[object] = []
        self.workspace_cube_stack_actions = SimpleNamespace(
            highlight_tab_for_cube=lambda *_args, **_kwargs: None
        )
        self.input_node_interaction_controller = SimpleNamespace(
            handle_image_changed=lambda *_args, **_kwargs: None,
            handle_image_clicked=lambda *_args, **_kwargs: None,
            handle_mask_changed=lambda *_args, **_kwargs: None,
            handle_mask_clicked=lambda *_args, **_kwargs: None,
        )
        self.input_mask_visual_opacity_controller = SimpleNamespace(
            handle=lambda *_args, **_kwargs: None,
            handle_commit=lambda *_args, **_kwargs: None,
        )
        self.workspace_scene_generation_actions = SimpleNamespace(
            enqueue_prompt_scene=lambda *_args, **_kwargs: None
        )

        self.workspace_canvas_actions = WorkspaceCanvasActions(
            cast(Any, self),
            error_presenter=_ErrorPresenter(self.error_reports),
        )
        self._error_presenter = _ErrorPresenter(self.error_reports)
        self._menu_container = QWidget()
        self._menu_container.setLayout(QHBoxLayout())
        self.menu_bar = self._menu_container
        self.focus_sentinel = QPushButton("focus-sentinel", self)
        self.focus_sentinel.setObjectName("PromptHarnessFocusSentinel")
        self.focus_sentinel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.focus_sentinel.setFixedSize(4, 4)
        self.focus_sentinel.show()
        menu_layout = self._menu_container.layout()
        if menu_layout is None:
            raise RuntimeError("Harness menu container must have a layout.")
        self.menu_bar_layout = menu_layout
        self.override_dropdown_btn = None
        self._global_override_menu = None
        self.pinned_override_service = PinnedOverrideService()
        workspace_parts = build_main_window_workspace(
            self,
            canvas_execution_runtime=canvas_execution_runtime,
            backdrop_mode=None,
            menu_container=self._menu_container,
            comfy_output_stream=self._comfy_output_stream,
            output_preview_registry=self.output_preview_registry,
            open_single_external_editor=(
                cast(
                    Any,
                    self.workspace_canvas_actions.open_image_in_external_editor,
                )
            ),
            open_all_external_editor=(
                cast(
                    Any,
                    self.workspace_canvas_actions.open_images_in_external_editor,
                )
            ),
        )
        self.workflow_tab_service = workspace_parts.workflow_tab_service
        self.workflow_session_service: WorkflowSessionService[WorkflowState] = cast(
            WorkflowSessionService[WorkflowState],
            workspace_parts.workflow_session_service,
        )
        self.workflow_tabbar = workspace_parts.workflow_tabbar
        self.workspace_body_material_surface = (
            workspace_parts.workspace_body_material_surface
        )
        self.canvas_host = workspace_parts.canvas_host
        self.cube_stack_container: QStackedWidget = workspace_parts.cube_stack_container
        self.editor_output_container = workspace_parts.editor_output_container
        self.editor_panel_container: QStackedWidget = (
            workspace_parts.editor_panel_container
        )
        self.input_canvas_state_service = workspace_parts.input_canvas_state_service
        self.output_canvas_state_service = workspace_parts.output_canvas_state_service
        self.output_canvas_projection_coordinator = (
            workspace_parts.output_canvas_projection_coordinator
        )
        self.workflow_canvas_projection_coordinator = (
            workspace_parts.workflow_canvas_projection_coordinator
        )
        self.canvas_image_registry = workspace_parts.canvas_image_registry
        self.output_canvas = self.canvas_host.canvas_for("Output")
        self.canvas_host_container = workspace_parts.canvas_host_container
        self.splitter = workspace_parts.splitter
        self.cubeStackModeButton = AppOrbCubeStackButton(self)
        self.workspace_splitter_controller = WorkspaceSplitterController(
            splitter=self.splitter,
            details_widget=self.editor_output_container,
            canvas_widget=self.canvas_host_container,
        )
        self.cube_stack_presentation_controller = CubeStackPresentationController(
            container=self.cube_stack_container,
            stacks=lambda: tuple(self.cube_stacks.values()),
            mode_button=self.cubeStackModeButton,
            material_surface=self.workspace_body_material_surface,
            active_editor_surface=lambda: self.active_editor_panel,
            splitter_controller=self.workspace_splitter_controller,
            position_search_box=self.search_overlay_controller.position_search_box,
            request_autosave=self.request_session_autosave,
            parent=self,
        )
        self.synthetic_canvas_resolution_role_service = SimpleNamespace(
            resolve_for_node=lambda **_kwargs: None,
        )
        self.synthetic_canvas_resolution_controller = SimpleNamespace(
            open_for_role=lambda *_args, **_kwargs: None,
        )
        self.workflow_ui_factory = WorkflowUiFactory(self)
        self.workflow_workspace = WorkflowWorkspaceCoordinator(
            cast(WorkflowWorkspaceView, self)
        )
        self.main_window_signal_binder = MainWindowSignalBinder(self)
        self.main_window_signal_binder.connect_canvas_signals(
            input_canvas=self.canvas_host.canvas_for("Input"),
            output_canvas=self.output_canvas,
        )
        self.canvas_host.activate_canvas("Input", keyboard_focus=False)
        self.activate_for_input()

    def activate_for_input(self) -> None:
        """Own the active top-level precondition for native harness input."""

        self.show()
        if QApplication.activeWindow() is self:
            return
        self.raise_()
        self.activateWindow()
        if QApplication.activeWindow() is self:
            return
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Function: 'QApplication\.setActiveWindow.*",
                category=DeprecationWarning,
            )
            QApplication.setActiveWindow(self)

    def install_workflow_surface(self, workflow_id: str) -> None:
        """Install real workflow widgets used by coordinator route switching."""

        cube_stack = self.cube_stacks.get(workflow_id)
        if cube_stack is None:
            cube_stack = CubeStack(self)
            cube_stack.setObjectName(f"{workflow_id}-cube-stack")
            self.cube_stack_presentation_controller.prepare_stack(cube_stack)
            self.cube_stacks[workflow_id] = cube_stack
            self.cube_stack_container.addWidget(cast(QWidget, cube_stack))
        editor_panel = self.editor_panels.get(workflow_id)
        if editor_panel is None:
            editor_panel = EditorPanel(
                node_definition_gateway=self.node_definition_gateway,
                prompt_autocomplete_gateway=self.prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=(self.prompt_wildcard_catalog_gateway),
                node_behavior_service=self.node_behavior_service,
                node_presentation_service=self.node_presentation_service,
                danbooru_url_import_service=self.danbooru_url_import_service,
                danbooru_wiki_service=self.danbooru_wiki_service,
                prompt_lora_catalog_service=self.prompt_lora_catalog_service,
                prompt_spellcheck_service=self.prompt_spellcheck_service,
                prompt_feature_profile_service=cast(
                    Any,
                    self.prompt_feature_profile_service,
                ),
                wheel_adjustment_mode=self.prompt_wheel_adjustment_mode,
                model_catalog_service=self.model_catalog_service,
                thumbnail_asset_repository=self.thumbnail_asset_repository,
                user_preset_service=self.user_preset_service,
                workflow_id=workflow_id,
                editor_panel_execution_factories=(
                    immediate_editor_panel_execution_factories()
                ),
            )
            editor_panel.mainwindow = self
            editor_panel.setObjectName(f"{workflow_id}-editor-panel")
            editor_panel.setMinimumWidth(412)
            self.main_window_signal_binder.connect_editor_panel_signals(editor_panel)
            self.editor_panels[workflow_id] = editor_panel
            self.editor_panel_container.addWidget(editor_panel)
        if workflow_id not in self.override_managers:
            manager = GlobalOverridesManager(
                self,
                pinned_override_service=self.pinned_override_service,
                node_definition_gateway=self.node_definition_gateway,
                prompt_autocomplete_gateway=self.prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=self.prompt_wildcard_catalog_gateway,
                prompt_lora_catalog_service=self.prompt_lora_catalog_service,
                model_choice_snapshot_controller=(
                    editor_panel.model_choice_snapshot_controller
                ),
                thumbnail_asset_repository=self.thumbnail_asset_repository,
            )
            self.override_managers[workflow_id] = manager

    @property
    def active_editor_panel(self) -> EditorPanel | None:
        """Return the editor panel for the active workflow."""

        return self.editor_panels.get(self.workflow_session_service.active_workflow_id)

    @property
    def active_override_manager(self) -> GlobalOverridesManager | None:
        """Return the override manager for the active workflow."""

        manager = self.override_managers.get(
            self.workflow_session_service.active_workflow_id
        )
        return manager if isinstance(manager, GlobalOverridesManager) else None

    def get_active_workflow(self) -> WorkflowState | None:
        """Return the active workflow state."""

        return self.workflow_session_service.get_workflow(
            self.workflow_session_service.active_workflow_id
        )

    def _resolve_workflow_name(self, workflow_id: str) -> str:
        """Return the workflow display name used by shell collaborators."""

        workflow = self.workflow_session_service.get_workflow(workflow_id)
        if workflow is None:
            return workflow_id
        value = workflow.metadata.get("name", workflow_id)
        return str(value)

    def request_session_autosave(self) -> None:
        """Ignore autosave requests in the real-shell harness."""


def _path_bundle() -> InstallationPathBundle:
    """Return deterministic local paths for shell collaborators."""

    root = Path("E:/devprojects/SugarSubstitute").resolve()
    return InstallationPathBundle(
        install_root=root,
        user_dir=root / ".tmp-user",
        projects_dir=root / ".tmp-projects",
        outputs_dir=root / ".tmp-outputs",
        sugar_scripts_dir=root / ".tmp-scripts",
        wildcards_dir=root / ".tmp-wildcards",
        managed_comfy_dir=root / ".tmp-comfy",
        session_dir=root / ".tmp-session",
    )
