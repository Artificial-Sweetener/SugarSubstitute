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

"""Compose MainWindow collaborators from application dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from substitute.application.generation import (
    VisualAuthorizationService,
    WorkflowProgressService,
)
from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.application.execution import DirectExecutionDispatcher
from substitute.application.workflows.closed_workflow_buffer import (
    ClosedWorkflowBuffer,
)
from substitute.application.workflows.closed_workflow_snapshot_service import (
    ClosedWorkflowSnapshotService,
)
from substitute.application.workflows.cube_runtime_issues import WorkflowIssueState
from substitute.application.workflows.input_canvas_capability_service import (
    InputCanvasCapabilityService,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_scene_run_service import (
    OutputSceneRunService,
)
from substitute.application.workflows.workflow_activity_service import (
    WorkflowActivityService,
)
from substitute.application.workflows.workflow_input_canvas_service import (
    WorkflowInputCanvasService,
)
from substitute.application.cubes import CubeStackService
from substitute.presentation.editor.panel.lora_metadata_refresh_controller import (
    PanelLoraMetadataRefreshController,
)
from substitute.presentation.errors import ErrorPresenter
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from substitute.presentation.restart_requirements import RestartRequirementUiController
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)

from .canvas_route_controller import CanvasRouteController
from .comfy_runtime_actions import ComfyRuntimeActions
from .cube_library_update_controller import CubeLibraryUpdateController
from .cube_stack_presentation_controller import (
    CubeStackMaterialSurface,
    CubeStackPresentationController,
)
from .direct_workflow_file_actions import DirectWorkflowFileActions
from .editor_busy_coordinator import EditorBusyCoordinator
from .editor_viewport_restore import EditorViewportRestoreController
from .generation_interrupt_failure_presenter import (
    GenerationInterruptFailurePresenter,
)
from .generation_action_controller import GenerationActionController
from .generation_feedback_coalescer import GenerationFeedbackCoalescer
from .generation_feedback_dispatcher import GenerationFeedbackDispatcher
from .generation_feedback_presenter import GenerationFeedbackPresenter
from .generation_queue_controller import GenerationQueueController
from .generation_queue_panel_transition import GenerationQueuePanelTransition
from .generation_result_workspace_materializer import (
    GenerationResultWorkspaceMaterializer,
)
from .initial_workspace_controller import InitialWorkspaceController
from .input_canvas_shell_adapter import InputCanvasShellAdapter
from .main_window_signal_binder import MainWindowSignalBinder
from .generation_feedback_sink import ShellGenerationFeedbackSink
from .generation_progress_strip_registry import GenerationProgressStripRegistry
from .main_window_dependencies import MainWindowDependencies
from .main_window_startup_trace import startup_phase
from .model_catalog_update_controller import ModelCatalogUpdateController
from .model_metadata_surface_refresh_controller import (
    ModelMetadataSurfaceRefreshController,
)
from .node_definition_refresh_controller import NodeDefinitionRefreshController
from .output_image_pipeline import (
    OutputCanvasProjectionCoordinatorProtocol,
    OutputImagePipeline,
)
from .output_image_preparation_dispatcher import (
    CanvasIoOutputImageLoader,
    OutputImagePreparationDispatcher,
)
from .progress_overlay_controller import ProgressOverlayController
from .restore_projection_controller import RestoreProjectionController
from .restored_workflow_materializer import RestoredWorkflowMaterializer
from .search_overlay_controller import SearchOverlayController
from .session_autosave_controller import SessionAutosaveController
from .session_snapshot_capture_adapter import SessionSnapshotCaptureAdapter
from .shell_active_surface_controller import ShellActiveSurfaceController
from .shell_event_filter_controller import ShellEventFilterController
from .shell_frame_integration_controller import ShellFrameIntegrationController
from .shell_chrome_controller import ShellChromeController
from .shell_layout_restore_controller import ShellLayoutRestoreController
from .shell_prehydrated_restore_controller import ShellPrehydratedRestoreController
from .shell_recipe_model_resolution_controller import (
    ShellRecipeModelResolutionController,
)
from .shell_reload_lifecycle_controller import ShellReloadLifecycleController
from .shell_restore_warmup_controller import ShellRestoreWarmupController
from .settings_route_controller import SettingsRouteController
from .workflow_surface_reconciler import ActiveWorkflowSurfaceRefresher
from .workflow_ui_factory import WorkflowUiFactory
from .workflow_surface_invalidation import WorkflowSurfaceInvalidationService
from .workspace_controller import WorkspaceController
from .workspace_drag_source import WorkspaceCanvasDragSourceClassifier
from .workspace_drop_controller import (
    DirectWorkflowDocumentClassifier,
    WorkflowRecipeDropClassifier,
    WorkspaceDropController,
)
from .workspace_restore_controller import WorkspaceRestoreController
from .workspace_restore_image_adapter import WorkspaceRestoreImageAdapter
from .workspace_splitter_controller import WorkspaceSplitterController
from .workspace_layout_controller import WorkspaceLayoutController
from substitute.presentation.canvas.input.input_canvas_presenter import (
    InputCanvasPresenter,
)
from substitute.presentation.canvas.input.input_mask_dirty_tracker import (
    InputMaskDirtyTracker,
)
from substitute.presentation.canvas.input.input_mask_save_controller import (
    InputMaskSaveController,
)
from substitute.presentation.canvas.input.input_mask_tool_controller import (
    InputMaskToolController,
)
from substitute.presentation.canvas.input.mask_color_provider import (
    input_mask_color,
)
from substitute.shared.startup_trace import trace_mark


@dataclass(frozen=True)
class MainWindowInitialComposition:
    """Hold controllers and services composed during initial shell dependency capture."""

    workflow_surface_invalidation_service: WorkflowSurfaceInvalidationService
    visual_authorization_service: VisualAuthorizationService
    workflow_progress_service: WorkflowProgressService
    output_scene_run_service: OutputSceneRunService
    output_preview_registry: OutputPreviewRegistry
    workspace_controller: WorkspaceController
    workspace_file_actions: Any
    direct_workflow_file_actions: DirectWorkflowFileActions
    workflow_workspace: Any
    workflow_duplicate_service: Any
    workspace_generation_actions: Any
    workspace_scene_generation_actions: Any
    workspace_loaded_cube_surface_actions: Any
    workspace_search_actions: Any
    workspace_cube_picker_actions: Any
    workspace_cube_stack_actions: Any
    workspace_canvas_actions: Any
    generation_feedback_sink: ShellGenerationFeedbackSink
    generation_feedback_dispatcher: GenerationFeedbackDispatcher
    workspace_canvas_drag_source_classifier: WorkspaceCanvasDragSourceClassifier
    workspace_drop_controller: WorkspaceDropController


@dataclass(frozen=True)
class MainWindowControllerComposition:
    """Hold shell controllers composed after widgets and workflow state exist."""

    workflow_issue_state: Any
    cube_stack_service: Any
    shell_chrome_controller: ShellChromeController
    shell_layout_restore_controller: ShellLayoutRestoreController
    workspace_layout_controller: WorkspaceLayoutController
    session_snapshot_capture_adapter: Any
    session_autosave_controller: Any
    workspace_restore_controller: Any
    restored_workflow_materializer: Any
    workspace_restore_image_adapter: Any
    editor_viewport_restore_controller: Any
    restore_projection_controller: Any
    generation_result_workspace_materializer: Any
    initial_workspace_controller: Any
    search_overlay_controller: Any
    progress_overlay_controller: Any
    generation_action_controller: Any
    generation_feedback_presenter: Any
    comfy_runtime_actions: Any
    workflow_ui_factory: Any
    active_workflow_surface_refresher: Any
    canvas_route_controller: Any
    main_window_signal_binder: Any
    shell_event_filter_controller: Any
    shell_frame_integration_controller: Any
    shell_reload_lifecycle_controller: Any
    shell_recipe_model_resolution_controller: Any
    shell_active_surface_controller: Any
    shell_restore_warmup_controller: Any
    shell_prehydrated_restore_controller: Any
    workspace_splitter_controller: WorkspaceSplitterController
    cube_stack_presentation_controller: CubeStackPresentationController
    generation_queue_panel_transition: Any
    generation_queue_controller: Any


@dataclass(frozen=True)
class MainWindowInputCanvasComposition:
    """Hold input-canvas collaborators composed after canvas widgets exist."""

    workflow_input_canvas_service: Any
    input_mask_tool_controller: Any
    input_canvas_shell_adapter: Any
    input_canvas_presenter: Any
    input_mask_dirty_tracker: Any
    input_mask_save_controller: Any
    input_canvas_capability_service: Any


@dataclass(frozen=True)
class MainWindowOutputCanvasComposition:
    """Hold output-canvas collaborators composed after canvas widgets exist."""

    output_image_pipeline: Any
    generation_progress_strip_registry: Any


@dataclass(frozen=True)
class MainWindowEditorBusyComposition:
    """Hold editor busy collaborators composed after workspace widgets exist."""

    editor_busy: Any


@dataclass(frozen=True)
class MainWindowEditorMetadataComposition:
    """Hold editor metadata refresh collaborators composed after editor maps exist."""

    lora_metadata_refresh_coordinator: Any
    model_metadata_surface_refresh_controller: Any


@dataclass(frozen=True)
class MainWindowRuntimeControllerComposition:
    """Hold runtime shell controllers composed after core shell controllers exist."""

    generation_job_queue_observer: Any
    generation_interrupt_failure_presenter: Any
    error_presenter: Any
    cube_library_update_controller: Any
    model_catalog_update_controller: Any
    settings_route_controller: Any
    restart_requirement_ui_controller: Any


@dataclass(frozen=True)
class MainWindowWorkflowLifecycleComposition:
    """Hold workflow lifecycle services composed after workspace creation."""

    closed_workflow_buffer: Any
    closed_workflow_snapshot_service: Any
    workflow_activity_service: Any
    node_definition_refresh_controller: Any


def _ensure_error_presenter(shell: Any) -> ErrorPresenter:
    """Return the shell-owned error presenter, creating it before consumers."""

    existing = getattr(shell, "_error_presenter", None)
    if existing is not None:
        return cast(ErrorPresenter, existing)
    error_presenter = ErrorPresenter(
        parent=shell,
        open_console=(
            lambda: shell.comfy_runtime_actions.set_comfy_output_panel_visible(True)
        ),
    )
    shell._error_presenter = error_presenter
    return error_presenter


def capture_dependencies(
    shell: Any,
    dependencies: MainWindowDependencies,
) -> MainWindowInitialComposition:
    """Store composed dependencies and create initial shell controllers."""

    shell.cube_load_service = dependencies.cube_load_service
    shell.cube_icon_factory = dependencies.cube_icon_factory
    shell.input_asset_endpoint_service = dependencies.input_asset_endpoint_service
    shell.input_canvas_plan_service = dependencies.input_canvas_plan_service
    shell.graph_section_service = dependencies.graph_section_service
    shell.recipe_io_service = dependencies.recipe_io_service
    shell.create_recipe_model_load_resolver = (
        dependencies.create_recipe_model_load_resolver
    )
    shell.recipe_model_download_resolution_service = (
        dependencies.recipe_model_download_resolution_service
    )
    shell.workflow_export_service = dependencies.workflow_export_service
    shell.progress_service = dependencies.progress_service
    shell.generation_service = dependencies.generation_service
    shell.invalidate_cube_catalog_cache = dependencies.invalidate_cube_catalog_cache
    shell.generation_job_queue_service = dependencies.generation_job_queue_service
    shell.shell_resource_lifecycle = dependencies.shell_resource_lifecycle
    shell.asset_reveal_service = dependencies.asset_reveal_service
    shell.canvas_io_service = dependencies.canvas_io_service
    shell.workflow_asset_service = dependencies.workflow_asset_service
    shell.workspace_generation_controller = dependencies.workspace_generation_controller
    shell.path_bundle = dependencies.path_bundle
    shell.node_definition_gateway = dependencies.node_definition_gateway
    shell.prompt_autocomplete_gateway = dependencies.prompt_autocomplete_gateway
    shell.prompt_wildcard_catalog_gateway = dependencies.prompt_wildcard_catalog_gateway
    shell.danbooru_url_import_service = dependencies.danbooru_url_import_service
    shell.danbooru_wiki_service = dependencies.danbooru_wiki_service
    shell.danbooru_image_preview_service = dependencies.danbooru_image_preview_service
    shell.danbooru_recent_posts_service = dependencies.danbooru_recent_posts_service
    shell.danbooru_preference_service = dependencies.danbooru_preference_service
    shell.danbooru_cache_repository = dependencies.danbooru_cache_repository
    shell.civitai_preference_service = dependencies.civitai_preference_service
    shell.civitai_credential_service = dependencies.civitai_credential_service
    shell.civitai_cache_service = dependencies.civitai_cache_service
    shell.prompt_wildcard_file_management_service = (
        dependencies.prompt_wildcard_file_management_service
    )
    shell.open_wildcard_management_modal = dependencies.open_wildcard_management_modal
    shell.open_autocomplete_list_management_modal = (
        dependencies.open_autocomplete_list_management_modal
    )
    shell.prompt_wildcard_preference_service = (
        dependencies.prompt_wildcard_preference_service
    )
    shell.prompt_wildcard_preprocessing_service = (
        dependencies.prompt_wildcard_preprocessing_service
    )
    shell.prompt_lora_catalog_service = dependencies.prompt_lora_catalog_service
    shell.prompt_scheduled_lora_service = dependencies.prompt_scheduled_lora_service
    shell.prompt_spellcheck_service = dependencies.prompt_spellcheck_service
    shell.scheduled_lora_provider = dependencies.scheduled_lora_provider
    shell.prompt_feature_profile_service = dependencies.prompt_feature_profile_service
    shell.user_preset_service = dependencies.user_preset_service
    shell.model_catalog_service = dependencies.model_catalog_service
    shell.model_choice_resolver = dependencies.model_choice_resolver
    shell.thumbnail_asset_repository = dependencies.thumbnail_asset_repository
    shell.model_metadata_context_action_handler = (
        dependencies.model_metadata_context_action_handler
    )
    shell.manual_model_metadata_update_sink = (
        dependencies.manual_model_metadata_update_sink
    )
    shell.node_behavior_service = dependencies.node_behavior_service
    shell.pinned_override_service = dependencies.pinned_override_service
    shell.prompt_editor_preference_service = (
        dependencies.prompt_editor_preference_service
    )
    shell._open_reconfigure_window = dependencies.open_reconfigure_window
    shell._reconfigure_window = None
    shell.appearance_runtime = dependencies.appearance_runtime
    shell.appearance_restart_coordinator = dependencies.appearance_restart_coordinator
    shell.about_info_service = dependencies.about_info_service
    shell.comfy_connection_settings_service = (
        dependencies.comfy_connection_settings_service
    )
    shell.restart_requirement_service = dependencies.restart_requirement_service
    shell._comfy_settings_webview_dialog = None
    shell.comfy_environment_service = dependencies.comfy_environment_service
    shell.cube_library_management_service = dependencies.cube_library_management_service
    shell.generation_preview_preference_service = (
        dependencies.generation_preview_preference_service
    )
    shell.output_preference_service = dependencies.output_preference_service
    shell.session_snapshot_repository = dependencies.session_snapshot_repository
    shell.session_autosave_service = dependencies.session_autosave_service
    shell.execution_runtime = dependencies.execution_runtime
    shell.settings_task_runner_factory = dependencies.settings_task_runner_factory
    shell.editor_panel_execution_factories = (
        dependencies.editor_panel_execution_factories
    )
    shell.restore_projection_cache_repository = (
        dependencies.restore_projection_cache_repository
    )
    shell.restore_projection_target_key = dependencies.restore_projection_target_key
    shell.cube_library_client = dependencies.cube_library_client
    shell._pending_restore_projection_cache_capture_workflow_id = ""
    shell.generation_result_snapshot_service = (
        dependencies.generation_result_snapshot_service
    )
    shell.recipe_output_sibling_discovery_service = (
        dependencies.recipe_output_sibling_discovery_service
    )
    _ensure_error_presenter(shell)
    workflow_surface_invalidation_service = WorkflowSurfaceInvalidationService()
    visual_authorization_service = VisualAuthorizationService()
    workflow_progress_service = WorkflowProgressService()
    output_scene_run_service = OutputSceneRunService()
    output_preview_registry = OutputPreviewRegistry()
    workspace_controller = WorkspaceController(shell)
    generation_feedback_sink = ShellGenerationFeedbackSink(shell)
    generation_feedback_dispatcher = GenerationFeedbackDispatcher(
        sink=generation_feedback_sink,
        coalescer=GenerationFeedbackCoalescer(
            _workflow_progress=workflow_progress_service,
            _visual_authorization=visual_authorization_service,
        ),
        idle_flush_interval_ms=16,
        active_prompt_flush_interval_ms=33,
        prompt_interaction_active=(
            shell.prompt_interaction_activity_tracker.is_prompt_interaction_active
        ),
        prompt_interaction_elapsed_ms=(
            shell.prompt_interaction_activity_tracker.ms_since_last_prompt_interaction
        ),
    )
    workspace_canvas_drag_source_classifier = WorkspaceCanvasDragSourceClassifier(shell)
    workspace_file_actions = workspace_controller.file_actions
    workflow_workspace = workspace_controller.workflow_workspace
    workflow_duplicate_service = workspace_controller.workflow_duplicate_service
    workspace_generation_actions = workspace_controller.generation_actions
    workspace_scene_generation_actions = workspace_controller.scene_generation_actions
    workspace_loaded_cube_surface_actions = (
        workspace_controller.loaded_cube_surface_actions
    )
    workspace_search_actions = workspace_controller.search_actions
    workspace_cube_picker_actions = workspace_controller.cube_picker_actions
    workspace_cube_stack_actions = workspace_controller.cube_stack_actions
    workspace_canvas_actions = workspace_controller.canvas_actions
    direct_workflow_repository = ComfyWorkflowDocumentRepository()
    direct_workflow_load_service = DirectWorkflowLoadService(
        direct_workflow_repository,
        node_definition_gateway=shell.node_definition_gateway,
    )
    direct_workflow_file_actions = DirectWorkflowFileActions(
        view=shell,
        load_service=direct_workflow_load_service,
        add_workflow_tab=workflow_workspace.add_workflow,
        refresh_active_workflow=lambda: workflow_workspace.project_workflow(
            shell.workflow_session_service.active_workflow_id,
            force_refresh=True,
            source="direct_workflow_loaded",
        ),
        materialize_loaded_section=lambda workflow_id, section_key: (
            shell.input_canvas_presenter.materialize_loaded_workflow_section(
                workflow_id,
                section_key,
            )
        ),
        error_presenter=_ensure_error_presenter(shell),
    )
    workspace_drop_controller = WorkspaceDropController(
        classifier=WorkflowRecipeDropClassifier(
            shell.recipe_io_service,
            DirectWorkflowDocumentClassifier(direct_workflow_load_service),
        ),
        ignored_drag_source=(
            workspace_canvas_drag_source_classifier.is_workspace_canvas_drag_source
        ),
        load_recipe_document=workspace_file_actions.load_recipe_document,
        load_direct_workflow_document=direct_workflow_file_actions.load_document,
    )
    composition = MainWindowInitialComposition(
        workflow_surface_invalidation_service=workflow_surface_invalidation_service,
        visual_authorization_service=visual_authorization_service,
        workflow_progress_service=workflow_progress_service,
        output_scene_run_service=output_scene_run_service,
        output_preview_registry=output_preview_registry,
        workspace_controller=workspace_controller,
        workspace_file_actions=workspace_file_actions,
        direct_workflow_file_actions=direct_workflow_file_actions,
        workflow_workspace=workflow_workspace,
        workflow_duplicate_service=workflow_duplicate_service,
        workspace_generation_actions=workspace_generation_actions,
        workspace_scene_generation_actions=workspace_scene_generation_actions,
        workspace_loaded_cube_surface_actions=workspace_loaded_cube_surface_actions,
        workspace_search_actions=workspace_search_actions,
        workspace_cube_picker_actions=workspace_cube_picker_actions,
        workspace_cube_stack_actions=workspace_cube_stack_actions,
        workspace_canvas_actions=workspace_canvas_actions,
        generation_feedback_sink=generation_feedback_sink,
        generation_feedback_dispatcher=generation_feedback_dispatcher,
        workspace_canvas_drag_source_classifier=(
            workspace_canvas_drag_source_classifier
        ),
        workspace_drop_controller=workspace_drop_controller,
    )
    shell.workflow_surface_invalidation_service = (
        composition.workflow_surface_invalidation_service
    )
    shell.visual_authorization_service = composition.visual_authorization_service
    shell.workflow_progress_service = composition.workflow_progress_service
    shell.output_scene_run_service = composition.output_scene_run_service
    shell.output_preview_registry = composition.output_preview_registry
    shell.workspace_controller = composition.workspace_controller
    shell.workspace_file_actions = composition.workspace_file_actions
    shell.direct_workflow_file_actions = composition.direct_workflow_file_actions
    shell.workflow_workspace = composition.workflow_workspace
    shell.workflow_duplicate_service = composition.workflow_duplicate_service
    shell.workspace_generation_actions = composition.workspace_generation_actions
    shell.workspace_scene_generation_actions = (
        composition.workspace_scene_generation_actions
    )
    shell.workspace_loaded_cube_surface_actions = (
        composition.workspace_loaded_cube_surface_actions
    )
    shell.workspace_search_actions = composition.workspace_search_actions
    shell.workspace_cube_picker_actions = composition.workspace_cube_picker_actions
    shell.workspace_cube_stack_actions = composition.workspace_cube_stack_actions
    shell.workspace_canvas_actions = composition.workspace_canvas_actions
    shell.generation_feedback_sink = composition.generation_feedback_sink
    shell.generation_feedback_dispatcher = composition.generation_feedback_dispatcher
    shell.workspace_canvas_drag_source_classifier = (
        composition.workspace_canvas_drag_source_classifier
    )
    shell.workspace_drop_controller = composition.workspace_drop_controller
    shell.setAcceptDrops(True)
    return composition


def compose_workflow_lifecycle_services(
    shell: Any,
) -> MainWindowWorkflowLifecycleComposition:
    """Create workflow lifecycle services and node-definition refresh owner."""

    composition = MainWindowWorkflowLifecycleComposition(
        closed_workflow_buffer=ClosedWorkflowBuffer(),
        closed_workflow_snapshot_service=ClosedWorkflowSnapshotService(),
        workflow_activity_service=WorkflowActivityService(),
        node_definition_refresh_controller=NodeDefinitionRefreshController(shell),
    )
    shell.closed_workflow_buffer = composition.closed_workflow_buffer
    shell.closed_workflow_snapshot_service = (
        composition.closed_workflow_snapshot_service
    )
    shell.workflow_activity_service = composition.workflow_activity_service
    shell.node_definition_refresh_controller = (
        composition.node_definition_refresh_controller
    )
    return composition


def compose_editor_busy_controller(shell: Any) -> MainWindowEditorBusyComposition:
    """Create editor busy coordination after the busy overlay exists."""

    editor_busy = EditorBusyCoordinator(
        active_workflow_id=lambda: shell.workflow_session_service.active_workflow_id,
        is_editor_surface_active=lambda: (
            getattr(shell, "_active_workspace_route", "")
            == shell.workflow_session_service.active_workflow_id
        ),
        overlay=shell.editorBusyOverlay,
    )
    shell.shell_resource_lifecycle.register("editor_busy", editor_busy.shutdown)
    shell.editorBusyOverlay.cancel_requested.connect(editor_busy.request_active_cancel)
    composition = MainWindowEditorBusyComposition(editor_busy=editor_busy)
    shell.editor_busy = composition.editor_busy
    return composition


def compose_output_canvas_controllers(shell: Any) -> MainWindowOutputCanvasComposition:
    """Create Output canvas pipeline and progress-strip collaborators."""

    preparation_dispatcher = _output_image_preparation_dispatcher(shell)
    shell.shell_resource_lifecycle.register(
        "output_image_preparation",
        preparation_dispatcher.shutdown,
    )
    pipeline_kwargs: dict[str, Any] = {
        "workflow_session_service": shell.workflow_session_service,
        "canvas_io_service": shell.canvas_io_service,
        "output_commit_handler": shell.workspace_canvas_actions,
        "output_canvas_projection_coordinator": cast(
            OutputCanvasProjectionCoordinatorProtocol,
            shell.output_canvas_projection_coordinator,
        ),
        "canvas_tabs": shell.canvas_tabs,
        "generation_timing_lookup": shell.generation_job_queue_service,
        "prompt_interaction_active": (
            shell.prompt_interaction_activity_tracker.is_prompt_interaction_active
        ),
        "prompt_interaction_elapsed_ms": (
            shell.prompt_interaction_activity_tracker.ms_since_last_prompt_interaction
        ),
        "preparation_dispatcher": preparation_dispatcher,
        "parent": shell,
    }
    output_image_pipeline = OutputImagePipeline(**pipeline_kwargs)
    generation_progress_strip_registry = GenerationProgressStripRegistry(shell)
    shell.output_floating_chrome_factory.set_progress_strip_registry(
        generation_progress_strip_registry
    )
    composition = MainWindowOutputCanvasComposition(
        output_image_pipeline=output_image_pipeline,
        generation_progress_strip_registry=generation_progress_strip_registry,
    )
    shell.output_image_pipeline = composition.output_image_pipeline
    shell.generation_progress_strip_registry = (
        composition.generation_progress_strip_registry
    )
    return composition


def _output_image_preparation_dispatcher(
    shell: Any,
) -> OutputImagePreparationDispatcher:
    """Create the runtime route for output image preparation."""

    execution_runtime = getattr(shell, "execution_runtime", None)
    if execution_runtime is None:
        raise RuntimeError(
            "execution_runtime is required for output image preparation."
        )
    submitter = execution_runtime.submitter(
        "image_decode",
        owner_id=f"output_image_preparation_{id(shell):x}",
        dispatcher=QtOwnerThreadDispatcher(shell),
    )
    return OutputImagePreparationDispatcher(
        loader=CanvasIoOutputImageLoader(shell.canvas_io_service),
        submitter=submitter,
        close_submitter=submitter.close,
        parent=shell,
    )


def compose_input_canvas_controllers(shell: Any) -> MainWindowInputCanvasComposition:
    """Create Input canvas services and presenter controllers for the shell."""

    input_canvas = shell.canvas_tabs.canvas_map.get("Input")
    if input_canvas is None:
        raise RuntimeError("Canvas tabs must include an Input canvas.")

    workflow_input_canvas_service = WorkflowInputCanvasService(
        input_canvas_plan_service=shell.input_canvas_plan_service,
        input_canvas_state_service=shell.input_canvas_state_service,
        canvas_io_service=shell.canvas_io_service,
        workflow_asset_service=shell.workflow_asset_service,
        graph_section_service=shell.graph_section_service,
    )
    input_mask_tool_controller = InputMaskToolController(
        input_pane=input_canvas.pane,
        current_image_id_provider=input_canvas.current_image_id_for_event,
        menu_state_sink=input_canvas.set_mask_tool_menu_state,
    )
    input_canvas.maskToolMenuStateRequested.connect(
        input_mask_tool_controller.refresh_tool_menu_state
    )
    input_canvas.maskToolModeRequested.connect(
        input_mask_tool_controller.request_tool_mode
    )
    input_canvas_shell_adapter = InputCanvasShellAdapter(shell)
    input_canvas_presenter = InputCanvasPresenter(
        input_pane=input_canvas.pane,
        current_image_id_provider=input_canvas.current_image_id_for_event,
        active_workflow_provider=shell.get_active_workflow,
        active_editor_panel_provider=lambda: shell.active_editor_panel,
        workflow_session_service=shell.workflow_session_service,
        workflow_input_canvas_service=workflow_input_canvas_service,
        input_canvas_state_service=shell.input_canvas_state_service,
        canvas_tabs_provider=lambda: shell.canvas_tabs,
        workflow_name_provider=input_canvas_shell_adapter.resolve_workflow_name,
        projects_dir_provider=lambda: Path(shell.path_bundle.projects_dir),
        mask_color_provider=input_mask_color,
        mask_tool_controller=input_mask_tool_controller,
        mark_canvas_changed=input_canvas_shell_adapter.mark_input_canvas_changed,
        error_presenter=getattr(shell, "_error_presenter", None),
    )
    input_mask_dirty_tracker = InputMaskDirtyTracker()

    def refresh_saved_input_mask(
        cube_alias: str,
        node_name: str,
        _path: str,
    ) -> None:
        """Refresh the editor mask picker after Input canvas saves a mask."""

        input_canvas_presenter.refresh_mask_picker_from_asset_state(
            cube_alias,
            node_name,
        )

    input_mask_save_controller = InputMaskSaveController(
        input_pane=input_canvas.pane,
        dirty_tracker=input_mask_dirty_tracker,
        workflow_session_service=shell.workflow_session_service,
        canvas_io_service=shell.canvas_io_service,
        workflow_input_canvas_service=workflow_input_canvas_service,
        workflow_name_provider=input_canvas_shell_adapter.resolve_workflow_name,
        projects_dir_provider=lambda: Path(shell.path_bundle.projects_dir),
        refresh_saved_mask=refresh_saved_input_mask,
    )
    input_canvas_capability_service = InputCanvasCapabilityService(
        shell.input_canvas_plan_service,
        shell.graph_section_service,
    )
    composition = MainWindowInputCanvasComposition(
        workflow_input_canvas_service=workflow_input_canvas_service,
        input_mask_tool_controller=input_mask_tool_controller,
        input_canvas_shell_adapter=input_canvas_shell_adapter,
        input_canvas_presenter=input_canvas_presenter,
        input_mask_dirty_tracker=input_mask_dirty_tracker,
        input_mask_save_controller=input_mask_save_controller,
        input_canvas_capability_service=input_canvas_capability_service,
    )
    shell.workflow_input_canvas_service = composition.workflow_input_canvas_service
    shell.input_mask_tool_controller = composition.input_mask_tool_controller
    shell.input_canvas_shell_adapter = composition.input_canvas_shell_adapter
    shell.input_canvas_presenter = composition.input_canvas_presenter
    shell.input_mask_dirty_tracker = composition.input_mask_dirty_tracker
    shell.input_mask_save_controller = composition.input_mask_save_controller
    shell.input_canvas_capability_service = composition.input_canvas_capability_service
    return composition


def compose_editor_metadata_controllers(
    shell: Any,
) -> MainWindowEditorMetadataComposition:
    """Create editor metadata refresh controllers after editor registries exist."""

    lora_metadata_executor = (
        shell.editor_panel_execution_factories.prompt_task_executor_factory(
            shell,
            f"panel-lora-metadata-refresh:{id(shell):x}",
        )
    )
    lora_metadata_refresh_coordinator = PanelLoraMetadataRefreshController(
        catalog_service=shell.prompt_lora_catalog_service,
        editor_panels=lambda: tuple(shell.editor_panels.values()),
        parent=shell,
        executor=lora_metadata_executor,
        executor_shutdown=lambda: lora_metadata_executor.shutdown(
            wait=False,
            cancel_futures=True,
        ),
    )
    model_catalog_snapshot_submitter = shell.execution_runtime.submitter(
        "model_catalog",
        owner_id=f"model_catalog_snapshot_refresh_{id(shell):x}",
        dispatcher=QtOwnerThreadDispatcher(shell),
    )
    model_metadata_surface_refresh_controller = ModelMetadataSurfaceRefreshController(
        shell,
        parent=shell,
        snapshot_refresh_submitter=model_catalog_snapshot_submitter,
        close_snapshot_refresh_submitter=model_catalog_snapshot_submitter.close,
    )
    composition = MainWindowEditorMetadataComposition(
        lora_metadata_refresh_coordinator=lora_metadata_refresh_coordinator,
        model_metadata_surface_refresh_controller=(
            model_metadata_surface_refresh_controller
        ),
    )
    shell._lora_metadata_refresh_coordinator = (
        composition.lora_metadata_refresh_coordinator
    )
    shell.model_metadata_surface_refresh_controller = (
        composition.model_metadata_surface_refresh_controller
    )
    shell.shell_resource_lifecycle.register(
        "panel_lora_metadata_refresh",
        composition.lora_metadata_refresh_coordinator.shutdown,
    )
    shell.shell_resource_lifecycle.register(
        "model_catalog_snapshot_refresh",
        composition.model_metadata_surface_refresh_controller.lora_refresh_coordinator.shutdown,
    )
    manual_update_sink = getattr(shell, "manual_model_metadata_update_sink", None)
    model_updated = getattr(manual_update_sink, "model_updated", None)
    connect = getattr(model_updated, "connect", None)
    if callable(connect):
        connect(
            composition.model_metadata_surface_refresh_controller.handle_model_metadata_updated
        )
    return composition


def compose_shell_controllers(shell: Any) -> MainWindowControllerComposition:
    """Create shell controllers after MainWindow has built its widgets."""

    search_overlay_controller = SearchOverlayController(shell)
    workspace_splitter_controller = WorkspaceSplitterController(
        splitter=shell.splitter,
        details_widget=shell.editor_output_container,
        canvas_widget=shell.canvas_tabs_container,
    )
    cube_stack_presentation_controller = CubeStackPresentationController(
        container=shell.cube_stack_container,
        stacks=lambda: tuple(shell.cube_stacks.values()),
        mode_button=shell.cubeStackModeButton,
        material_surface=cast(
            CubeStackMaterialSurface,
            shell.workspace_body_material_surface,
        ),
        active_editor_surface=lambda: shell.active_editor_panel,
        splitter_controller=workspace_splitter_controller,
        position_search_box=search_overlay_controller.position_search_box,
        request_autosave=shell.request_session_autosave,
        parent=shell,
    )
    workspace_layout_controller = WorkspaceLayoutController(shell)
    composition = MainWindowControllerComposition(
        workflow_issue_state=WorkflowIssueState(),
        cube_stack_service=CubeStackService(),
        shell_chrome_controller=ShellChromeController(shell),
        shell_layout_restore_controller=ShellLayoutRestoreController(shell),
        workspace_layout_controller=workspace_layout_controller,
        session_snapshot_capture_adapter=SessionSnapshotCaptureAdapter(shell),
        session_autosave_controller=SessionAutosaveController(shell),
        workspace_restore_controller=WorkspaceRestoreController(shell),
        restored_workflow_materializer=RestoredWorkflowMaterializer(shell),
        workspace_restore_image_adapter=WorkspaceRestoreImageAdapter(shell),
        editor_viewport_restore_controller=EditorViewportRestoreController(shell),
        restore_projection_controller=RestoreProjectionController(shell),
        generation_result_workspace_materializer=(
            GenerationResultWorkspaceMaterializer(shell)
        ),
        initial_workspace_controller=InitialWorkspaceController(shell),
        search_overlay_controller=search_overlay_controller,
        progress_overlay_controller=ProgressOverlayController(shell),
        generation_action_controller=GenerationActionController(shell),
        generation_feedback_presenter=GenerationFeedbackPresenter(shell),
        comfy_runtime_actions=ComfyRuntimeActions(shell),
        workflow_ui_factory=WorkflowUiFactory(shell),
        active_workflow_surface_refresher=ActiveWorkflowSurfaceRefresher(shell),
        canvas_route_controller=CanvasRouteController(shell),
        main_window_signal_binder=MainWindowSignalBinder(shell),
        shell_event_filter_controller=ShellEventFilterController(shell),
        shell_frame_integration_controller=ShellFrameIntegrationController(shell),
        shell_reload_lifecycle_controller=ShellReloadLifecycleController(shell),
        shell_recipe_model_resolution_controller=(
            ShellRecipeModelResolutionController(shell)
        ),
        shell_active_surface_controller=ShellActiveSurfaceController(shell),
        shell_restore_warmup_controller=ShellRestoreWarmupController(shell),
        shell_prehydrated_restore_controller=ShellPrehydratedRestoreController(shell),
        workspace_splitter_controller=workspace_splitter_controller,
        cube_stack_presentation_controller=cube_stack_presentation_controller,
        generation_queue_panel_transition=GenerationQueuePanelTransition(shell),
        generation_queue_controller=GenerationQueueController(shell),
    )
    shell.workflow_issue_state = composition.workflow_issue_state
    shell.cube_stack_service = composition.cube_stack_service
    shell.shell_chrome_controller = composition.shell_chrome_controller
    shell.shell_layout_restore_controller = composition.shell_layout_restore_controller
    shell.workspace_layout_controller = composition.workspace_layout_controller
    shell.session_snapshot_capture_adapter = (
        composition.session_snapshot_capture_adapter
    )
    shell.session_autosave_controller = composition.session_autosave_controller
    shell.workspace_restore_controller = composition.workspace_restore_controller
    shell.restored_workflow_materializer = composition.restored_workflow_materializer
    shell.workspace_restore_image_adapter = composition.workspace_restore_image_adapter
    shell.editor_viewport_restore_controller = (
        composition.editor_viewport_restore_controller
    )
    shell.restore_projection_controller = composition.restore_projection_controller
    shell.generation_result_workspace_materializer = (
        composition.generation_result_workspace_materializer
    )
    shell.initial_workspace_controller = composition.initial_workspace_controller
    shell.search_overlay_controller = composition.search_overlay_controller
    shell.progress_overlay_controller = composition.progress_overlay_controller
    shell.generation_action_controller = composition.generation_action_controller
    shell.generation_feedback_presenter = composition.generation_feedback_presenter
    shell.comfy_runtime_actions = composition.comfy_runtime_actions
    shell.workflow_ui_factory = composition.workflow_ui_factory
    shell.active_workflow_surface_refresher = (
        composition.active_workflow_surface_refresher
    )
    shell.canvas_route_controller = composition.canvas_route_controller
    shell.main_window_signal_binder = composition.main_window_signal_binder
    shell.shell_event_filter_controller = composition.shell_event_filter_controller
    shell.shell_frame_integration_controller = (
        composition.shell_frame_integration_controller
    )
    shell.shell_reload_lifecycle_controller = (
        composition.shell_reload_lifecycle_controller
    )
    shell.shell_recipe_model_resolution_controller = (
        composition.shell_recipe_model_resolution_controller
    )
    shell.shell_active_surface_controller = composition.shell_active_surface_controller
    shell.shell_restore_warmup_controller = composition.shell_restore_warmup_controller
    shell.shell_prehydrated_restore_controller = (
        composition.shell_prehydrated_restore_controller
    )
    shell.workspace_splitter_controller = composition.workspace_splitter_controller
    shell.cube_stack_presentation_controller = (
        composition.cube_stack_presentation_controller
    )
    shell._generation_queue_panel_visible = False
    shell._generation_queue_panel_transition = (
        composition.generation_queue_panel_transition
    )
    shell.generation_queue_controller = composition.generation_queue_controller
    shell.generation_queue_controller.install_surfaces()
    shell._active_workspace_route = shell.workflow_session_service.active_workflow_id
    shell._remembered_workflow_splitter_sizes = ()
    shell._restored_shell_layout_applied = False
    shell._pending_restored_shell_layout = None
    shell.shell_prehydrated_restore_controller.initialize_restore_state()
    shell._restore_asset_preload = None
    shell._startup_autosave_unmuted_marked = False
    shell.session_autosave_controller.ensure_coordinator()
    shell.workspace_layout_controller.log_editor_width_trace(
        "initialized durable layout state"
    )
    return composition


def compose_runtime_controllers(
    shell: Any,
    dependencies: MainWindowDependencies,
) -> MainWindowRuntimeControllerComposition:
    """Create runtime shell controllers after core shell controllers exist."""

    shell._current_generate_mode = "generate"
    shell._backend_state = "starting"
    shell._last_progress_view_state = None
    shell._sampler_progress_model_fields_cleared = False
    generation_job_queue_observer = (
        shell.generation_action_controller.handle_generation_queue_state_changed
    )
    shell.generation_job_queue_service.add_observer(generation_job_queue_observer)
    shell._comfy_output_stream = dependencies.comfy_output_stream
    generation_interrupt_failure_presenter = GenerationInterruptFailurePresenter(
        shell._comfy_output_stream
    )
    error_presenter = _ensure_error_presenter(shell)
    cube_library_update_submitter = shell.execution_runtime.submitter(
        "cube_library_update",
        owner_id="cube_library_update_controller",
        dispatcher=QtOwnerThreadDispatcher(shell),
    )
    cube_library_update_controller = CubeLibraryUpdateController(
        shell,
        dependencies,
        refresh_submitter=cube_library_update_submitter,
        close_refresh_submitter=cube_library_update_submitter.close,
    )
    shell.shell_resource_lifecycle.register(
        "cube_library_updates",
        cube_library_update_controller.stop_listener,
    )
    model_catalog_change_submitter = shell.execution_runtime.submitter(
        "node_definition",
        owner_id=f"model_catalog_change_{id(shell):x}",
        dispatcher=DirectExecutionDispatcher(),
    )
    model_catalog_update_controller = ModelCatalogUpdateController(
        shell,
        dependencies,
        node_definition_submitter=model_catalog_change_submitter,
        close_node_definition_submitter=model_catalog_change_submitter.close,
    )
    shell.shell_resource_lifecycle.register(
        "model_catalog_updates",
        model_catalog_update_controller.stop,
    )
    shell._initial_workspace_hydrated = False
    settings_route_controller = SettingsRouteController(
        shell,
        error_presenter=error_presenter,
    )
    restart_requirement_ui_controller = _compose_restart_requirement_ui_controller(
        shell
    )
    composition = MainWindowRuntimeControllerComposition(
        generation_job_queue_observer=generation_job_queue_observer,
        generation_interrupt_failure_presenter=(generation_interrupt_failure_presenter),
        error_presenter=error_presenter,
        cube_library_update_controller=cube_library_update_controller,
        model_catalog_update_controller=model_catalog_update_controller,
        settings_route_controller=settings_route_controller,
        restart_requirement_ui_controller=restart_requirement_ui_controller,
    )
    shell._generation_job_queue_observer = composition.generation_job_queue_observer
    shell.generation_interrupt_failure_presenter = (
        composition.generation_interrupt_failure_presenter
    )
    shell.cube_library_update_controller = composition.cube_library_update_controller
    shell.model_catalog_update_controller = composition.model_catalog_update_controller
    shell.settings_route_controller = composition.settings_route_controller
    shell.restart_requirement_ui_controller = (
        composition.restart_requirement_ui_controller
    )
    settings_route_controller.create_settings_workspace()
    return composition


def _compose_restart_requirement_ui_controller(shell: Any) -> object | None:
    """Attach the restart cart controller to the toolbar button when available."""

    button = getattr(shell, "pendingRestartButton", None)
    service = getattr(shell, "restart_requirement_service", None)
    actions = getattr(shell, "comfy_runtime_actions", None)
    restart_full_app = getattr(actions, "request_comfy_restart", None)
    if button is None or service is None or not callable(restart_full_app):
        return None
    return cast(
        object,
        RestartRequirementUiController(
            service=service,
            button=button,
            restart_full_app=restart_full_app,
            restart_window=lambda: _request_shell_gui_reload(shell),
            parent=shell,
        ),
    )


def _request_shell_gui_reload(shell: Any) -> None:
    """Invoke the current shell GUI reload callback when the restart cart asks."""

    reload_gui = getattr(shell, "request_full_gui_reload", None)
    if callable(reload_gui):
        reload_gui()


def connect_shell_signals(
    shell: Any,
    startup_timer: Any | None,
    *,
    single_shot: Callable[[int, Callable[[], None]], None],
) -> None:
    """Connect shell signals and schedule initial overlay/layout positioning."""

    with startup_phase(startup_timer, "mainwindow.connect_signals"):
        shell.main_window_signal_binder.connect_generation_feedback_signals()
        shell.main_window_signal_binder.connect_search_signals()
        shell.main_window_signal_binder.connect_menu_action_signals()
        shell.main_window_signal_binder.connect_workflow_tab_signals()

    output_canvas = shell.canvas_tabs.canvas_map.get("Output")
    input_canvas = shell.canvas_tabs.canvas_map.get("Input")
    if input_canvas is None or output_canvas is None:
        raise RuntimeError("Canvas tabs must include Input and Output canvases.")
    shell.main_window_signal_binder.connect_canvas_signals(
        input_canvas=input_canvas,
        output_canvas=output_canvas,
    )
    shell.canvas_route_controller.connect_canvas_route_signals()
    shell.canvas_tabs.visibility_changed.connect(
        shell.workspace_layout_controller.toggle_canvas_tabs
    )
    shell.session_autosave_controller.connect_canvas_layout_autosave()
    shell.splitter.splitterMoved.connect(
        shell.workspace_layout_controller.handle_main_splitter_moved
    )
    shell.editor_output_splitter.splitterMoved.connect(
        shell.workspace_layout_controller.handle_editor_output_splitter_moved
    )
    current_panel_changed = getattr(
        shell.editor_panel_container, "currentChanged", None
    )
    if current_panel_changed is not None:
        current_panel_changed.connect(
            lambda _index: shell.search_overlay_controller.position_search_box()
        )

    shell.generation_action_controller.set_generation_selected_mode("generate")
    if shell.generationActionCluster is not None:
        shell._generation_action_cluster_mode_callback = (
            shell.generation_action_controller.set_generation_selected_mode
        )
        shell.generationActionCluster.generateModeSelected.connect(
            shell._generation_action_cluster_mode_callback
        )

    shell.comfy_runtime_actions.set_comfy_output_panel_visible(False)

    shell.workspace_layout_controller.log_editor_width_trace(
        "scheduling startup default splitter layout",
    )
    trace_mark(
        "main_window.apply_startup_default_splitter_layout",
        delay_ms=0,
    )
    single_shot(
        0,
        shell.workspace_layout_controller.apply_startup_default_splitter_layout,
    )
    trace_mark(
        "main_window.position_progress_overlay",
        delay_ms=0,
    )
    single_shot(0, shell.progress_overlay_controller.position_progress_overlay)
    trace_mark(
        "main_window.position_search_box",
        delay_ms=0,
    )
    single_shot(0, shell.search_overlay_controller.position_search_box)
    shell.installEventFilter(shell)


__all__ = [
    "connect_shell_signals",
    "MainWindowControllerComposition",
    "MainWindowEditorBusyComposition",
    "MainWindowEditorMetadataComposition",
    "MainWindowInitialComposition",
    "MainWindowInputCanvasComposition",
    "MainWindowOutputCanvasComposition",
    "MainWindowRuntimeControllerComposition",
    "MainWindowWorkflowLifecycleComposition",
    "capture_dependencies",
    "compose_editor_busy_controller",
    "compose_editor_metadata_controllers",
    "compose_input_canvas_controllers",
    "compose_output_canvas_controllers",
    "compose_runtime_controllers",
    "compose_shell_controllers",
    "compose_workflow_lifecycle_services",
]
