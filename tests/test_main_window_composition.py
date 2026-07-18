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

"""Verify MainWindow dependency composition stays outside the shell class."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.presentation.shell import main_window_composition


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "main_window_composition.py"
)


class _PromptInteractionActivityTracker:
    """Provide prompt activity callbacks consumed by feedback composition."""

    def is_prompt_interaction_active(self) -> bool:
        """Return a stable inactive prompt interaction state."""

        return False

    def ms_since_last_prompt_interaction(self) -> int:
        """Return a deterministic elapsed interaction interval."""

        return 0


class _Shell(SimpleNamespace):
    """Capture shell mutation performed by dependency composition."""

    def __init__(self) -> None:
        """Create a shell with the callbacks required by composition."""

        super().__init__(
            prompt_interaction_activity_tracker=_PromptInteractionActivityTracker(),
            accept_drops_enabled=None,
        )

    def setAcceptDrops(self, enabled: bool) -> None:
        """Record whether shell drops were enabled."""

        self.accept_drops_enabled = enabled


class _FakeWorkspaceController:
    """Stand in for the workspace controller created during composition."""

    def __init__(self, shell: _Shell) -> None:
        """Keep the owning shell for assertions."""

        self.shell = shell
        self.error_presenter_during_creation = getattr(
            shell,
            "_error_presenter",
            None,
        )
        self.file_actions = _FakeWorkspaceFileActions()
        self.workflow_workspace = _FakeWorkflowWorkspace()
        self.workflow_duplicate_service = _FakeWorkflowDuplicateService()
        self.generation_actions = _FakeWorkspaceGenerationActions()
        self.scene_generation_actions = _FakeWorkspaceSceneGenerationActions()
        self.loaded_cube_surface_actions = _FakeWorkspaceLoadedCubeSurfaceActions()
        self.search_actions = _FakeWorkspaceSearchActions()
        self.cube_picker_actions = _FakeWorkspaceCubePickerActions()
        self.cube_stack_actions = _FakeWorkspaceCubeStackActions()
        self.canvas_actions = _FakeWorkspaceCanvasActions()


class _FakeWorkspaceFileActions:
    """Stand in for workspace file actions exposed by the controller."""

    def load_recipe_document(self, document: object) -> object:
        """Return the document unchanged for drop-controller wiring."""

        return document


class _FakeWorkflowWorkspace:
    """Stand in for workflow lifecycle coordination exposed by the controller."""

    def add_workflow(self) -> str:
        """Return a stable fake workflow id for document-action wiring."""

        return "workflow-new"

    def reconcile_active_workflow_after_structural_mutation(
        self,
        *,
        force_refresh: bool,
    ) -> None:
        """Accept direct-document refresh wiring without performing UI work."""

        _ = force_refresh


class _FakeWorkflowDuplicateService:
    """Stand in for workflow duplication service exposed by the controller."""


class _FakeWorkspaceGenerationActions:
    """Stand in for generation actions exposed by the controller."""


class _FakeWorkspaceSceneGenerationActions:
    """Stand in for scene generation actions exposed by the controller."""


class _FakeWorkspaceLoadedCubeSurfaceActions:
    """Stand in for loaded-cube surface actions exposed by the controller."""


class _FakeWorkspaceSearchActions:
    """Stand in for workspace search actions exposed by the controller."""


class _FakeWorkspaceCubePickerActions:
    """Stand in for workspace cube picker actions exposed by the controller."""


class _FakeWorkspaceCubeStackActions:
    """Stand in for workspace cube-card actions exposed by the controller."""


class _FakeWorkspaceCanvasActions:
    """Stand in for workspace canvas actions exposed by the controller."""


class _FakeGenerationFeedbackCoalescer:
    """Capture coalescer collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for verification."""

        self.kwargs = kwargs


class _FakeGenerationFeedbackDispatcher:
    """Capture dispatcher collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for verification."""

        self.kwargs = kwargs


class _FakeShellGenerationFeedbackSink:
    """Capture the shell used for dispatcher sink composition."""

    def __init__(self, shell: _Shell) -> None:
        """Keep the owning shell for assertions."""

        self.shell = shell


class _FakeWorkflowRecipeDropClassifier:
    """Capture the recipe IO service used for workflow drops."""

    def __init__(
        self,
        recipe_io_service: object,
        direct_workflow_classifier: object | None = None,
    ) -> None:
        """Store the recipe IO dependency."""

        self.recipe_io_service = recipe_io_service
        self.direct_workflow_classifier = direct_workflow_classifier


class _FakeWorkspaceCanvasDragSourceClassifier:
    """Capture the shell used for workspace drag-source classification."""

    def __init__(self, shell: _Shell) -> None:
        """Keep the owning shell for assertions."""

        self.shell = shell

    def is_workspace_canvas_drag_source(self, source: object | None) -> bool:
        """Return a stable classification for composition tests."""

        return source is self.shell


class _FakeWorkspaceDropController:
    """Capture workspace drop collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for verification."""

        self.kwargs = kwargs


class _FakeController:
    """Generic shell controller fake for controller composition tests."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Store constructor inputs and initialize lifecycle flags."""

        self.args = args
        self.kwargs = kwargs
        self.installed = False
        self.restore_initialized = False
        self.coordinator_ensured = False
        self.layout_trace_messages: list[str] = []

    def install_surfaces(self) -> None:
        """Record generation queue surface installation."""

        self.installed = True

    def initialize_restore_state(self) -> None:
        """Record prehydrated restore state initialization."""

        self.restore_initialized = True

    def ensure_coordinator(self) -> None:
        """Record autosave coordinator initialization."""

        self.coordinator_ensured = True

    def log_editor_width_trace(self, message: str) -> None:
        """Record shell layout trace messages."""

        self.layout_trace_messages.append(message)

    def position_search_box(self) -> None:
        """Accept search-overlay positioning during controller composition."""


class _Signal:
    """Record connected slots for signal-composition tests."""

    def __init__(self) -> None:
        """Initialize with no connected slots."""

        self.connected: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected slot."""

        self.connected.append(slot)


class _FakeService:
    """Represent a zero-argument composed service."""


class _FakeSignal(_Signal):
    """Alias signal fake for readability in input-canvas composition tests."""


class _FakeInputMaskToolController:
    """Capture mask-tool controller wiring inputs."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs
        self.refresh_tool_menu_state = object()
        self.request_tool_mode = object()


class _FakeInputCanvasShellAdapter:
    """Provide shell adapter callbacks for input-canvas composition."""

    def __init__(self, shell: object) -> None:
        """Keep the owning shell for assertions."""

        self.shell = shell
        self.resolve_workflow_name = object()
        self.mark_input_canvas_changed = object()


class _FakeInputCanvasPresenter:
    """Capture presenter wiring and mask-picker refresh requests."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs
        self.refreshed_masks: list[tuple[object, object]] = []

    def refresh_mask_picker_from_asset_state(
        self,
        cube_alias: object,
        node_name: object,
    ) -> None:
        """Record a saved-mask refresh routed from the save controller."""

        self.refreshed_masks.append((cube_alias, node_name))


class _FakeInputMaskDirtyTracker:
    """Represent the input-mask dirty tracker."""


class _FakeInputMaskSaveController:
    """Capture save-controller wiring inputs."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs


class _FakeWorkflowInputCanvasService:
    """Capture workflow input-canvas service dependencies."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs


class _FakeInputCanvasCapabilityService:
    """Capture input-canvas capability service dependency."""

    def __init__(
        self,
        input_canvas_plan_service: object,
        graph_section_service: object,
    ) -> None:
        """Store canvas planning and graph section services for assertions."""

        self.input_canvas_plan_service = input_canvas_plan_service
        self.graph_section_service = graph_section_service


class _FakeOutputImagePipeline:
    """Capture Output image pipeline collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs


class _FakeShellResourceLifecycle:
    """Capture shell resource cleanup registrations."""

    def __init__(self) -> None:
        """Create an empty registration list."""

        self.registrations: list[tuple[str, object]] = []

    def register(self, resource_name: str, cleanup: object) -> None:
        """Record one named cleanup operation."""

        self.registrations.append((resource_name, cleanup))


class _FakeGenerationProgressStripRegistry:
    """Capture the progress-strip registry parent."""

    def __init__(self, parent: object) -> None:
        """Store the parent shell for assertions."""

        self.parent = parent


class _FakeEditorBusyCoordinator:
    """Capture editor busy coordinator collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs
        self.request_active_cancel = object()

    def shutdown(self) -> None:
        """Represent synchronous busy presentation cleanup."""


class _FakePanelLoraMetadataRefreshController:
    """Capture panel LoRA metadata refresh collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs

    def shutdown(self) -> None:
        """Represent prompt metadata cleanup."""


class _FakeModelMetadataSurfaceRefreshController:
    """Capture model metadata surface refresh collaborators."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Store constructor inputs for assertions."""

        self.args = args
        self.kwargs = kwargs
        self.lora_refresh_coordinator = SimpleNamespace(shutdown=lambda: None)


class _FakeGenerationInterruptFailurePresenter:
    """Capture Comfy output stream dependency."""

    def __init__(self, output_stream: object) -> None:
        """Store the output stream for assertions."""

        self.output_stream = output_stream


class _FakeErrorPresenter:
    """Capture error presenter collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs


class _FakeDependencyController:
    """Capture shell and dependency construction for runtime controllers."""

    def __init__(self, shell: object, dependencies: object, **kwargs: object) -> None:
        """Store constructor arguments for assertions."""

        self.shell = shell
        self.dependencies = dependencies
        self.kwargs = kwargs

    def stop_listener(self) -> None:
        """Represent Cube Library listener cleanup."""

    def stop(self) -> None:
        """Represent model catalog listener cleanup."""


class _FakeSettingsRouteController:
    """Capture Settings route construction and workspace creation."""

    def __init__(self, shell: object, *, error_presenter: object | None) -> None:
        """Store the owning shell and injected presenter for assertions."""

        self.shell = shell
        self.error_presenter = error_presenter
        self.created_settings_workspace = False
        self.error_presenter_during_creation: object | None = None
        self.shell_error_presenter_during_creation: object | None = None

    def create_settings_workspace(self) -> None:
        """Record Settings workspace creation with injected collaborators."""

        self.error_presenter_during_creation = self.error_presenter
        self.shell_error_presenter_during_creation = getattr(
            self.shell,
            "_error_presenter",
            None,
        )
        self.created_settings_workspace = True


class _FakeWorkflowLifecycleService:
    """Represent a zero-argument workflow lifecycle service."""


class _FakeNodeDefinitionRefreshController:
    """Capture node-definition refresh controller ownership."""

    def __init__(self, shell: object) -> None:
        """Store the owning shell for assertions."""

        self.shell = shell


def _dependencies() -> SimpleNamespace:
    """Create dependency values matching the capture surface."""

    dependency_names = [
        "cube_load_service",
        "cube_icon_factory",
        "input_asset_endpoint_service",
        "input_canvas_plan_service",
        "graph_section_service",
        "recipe_io_service",
        "create_recipe_model_load_resolver",
        "recipe_model_download_resolution_service",
        "workflow_export_service",
        "progress_service",
        "generation_service",
        "invalidate_cube_catalog_cache",
        "generation_job_queue_service",
        "shell_resource_lifecycle",
        "asset_reveal_service",
        "canvas_io_service",
        "workflow_asset_service",
        "workspace_generation_controller",
        "path_bundle",
        "node_definition_gateway",
        "prompt_autocomplete_gateway",
        "prompt_wildcard_catalog_gateway",
        "danbooru_url_import_service",
        "danbooru_wiki_service",
        "danbooru_image_preview_service",
        "danbooru_recent_posts_service",
        "danbooru_preference_service",
        "danbooru_cache_repository",
        "civitai_preference_service",
        "civitai_credential_service",
        "civitai_cache_service",
        "prompt_wildcard_file_management_service",
        "open_wildcard_management_modal",
        "prompt_wildcard_preference_service",
        "prompt_wildcard_preprocessing_service",
        "prompt_lora_catalog_service",
        "prompt_scheduled_lora_service",
        "prompt_spellcheck_service",
        "scheduled_lora_provider",
        "prompt_feature_profile_service",
        "user_preset_service",
        "model_catalog_service",
        "model_choice_resolver",
        "thumbnail_asset_repository",
        "model_metadata_context_action_handler",
        "manual_model_metadata_update_sink",
        "node_behavior_service",
        "pinned_override_service",
        "prompt_editor_preference_service",
        "open_reconfigure_window",
        "appearance_runtime",
        "appearance_restart_coordinator",
        "about_info_service",
        "comfy_connection_settings_service",
        "restart_requirement_service",
        "comfy_environment_service",
        "cube_library_management_service",
        "generation_preview_preference_service",
        "output_organization_preference_service",
        "session_snapshot_repository",
        "session_autosave_service",
        "execution_runtime",
        "settings_task_runner_factory",
        "editor_panel_execution_factories",
        "restore_projection_cache_repository",
        "restore_projection_target_key",
        "cube_library_client",
        "generation_result_snapshot_service",
        "recipe_output_sibling_discovery_service",
    ]
    return SimpleNamespace(**{name: object() for name in dependency_names})


@pytest.fixture
def composition_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace heavy collaborators with deterministic composition fakes."""

    monkeypatch.setattr(
        main_window_composition,
        "WorkflowSurfaceInvalidationService",
        _FakeService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "VisualAuthorizationService",
        _FakeService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "WorkflowProgressService",
        _FakeService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "OutputSceneRunService",
        _FakeService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "OutputPreviewRegistry",
        _FakeService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ErrorPresenter",
        _FakeErrorPresenter,
    )
    monkeypatch.setattr(
        main_window_composition,
        "WorkspaceController",
        _FakeWorkspaceController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "GenerationFeedbackCoalescer",
        _FakeGenerationFeedbackCoalescer,
    )
    monkeypatch.setattr(
        main_window_composition,
        "GenerationFeedbackDispatcher",
        _FakeGenerationFeedbackDispatcher,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ShellGenerationFeedbackSink",
        _FakeShellGenerationFeedbackSink,
    )
    monkeypatch.setattr(
        main_window_composition,
        "WorkflowRecipeDropClassifier",
        _FakeWorkflowRecipeDropClassifier,
    )
    monkeypatch.setattr(
        main_window_composition,
        "WorkspaceCanvasDragSourceClassifier",
        _FakeWorkspaceCanvasDragSourceClassifier,
    )
    monkeypatch.setattr(
        main_window_composition,
        "WorkspaceDropController",
        _FakeWorkspaceDropController,
    )


def test_capture_dependencies_assigns_dependencies_and_composes_controllers(
    composition_fakes: None,
) -> None:
    """Ensure dependency capture remains behaviorally equivalent after extraction."""

    shell = _Shell()
    dependencies = _dependencies()

    composition = main_window_composition.capture_dependencies(shell, dependencies)  # type: ignore[arg-type]

    assert shell.cube_load_service is dependencies.cube_load_service
    assert shell.recipe_io_service is dependencies.recipe_io_service
    assert shell.asset_reveal_service is dependencies.asset_reveal_service
    assert shell.prompt_lora_catalog_service is dependencies.prompt_lora_catalog_service
    assert shell._open_reconfigure_window is dependencies.open_reconfigure_window
    assert shell._reconfigure_window is None
    assert shell._comfy_settings_webview_dialog is None
    assert shell._pending_restore_projection_cache_capture_workflow_id == ""
    assert shell.accept_drops_enabled is True
    assert isinstance(shell.workflow_surface_invalidation_service, _FakeService)
    assert isinstance(shell.visual_authorization_service, _FakeService)
    assert isinstance(shell.workflow_progress_service, _FakeService)
    assert isinstance(shell.output_scene_run_service, _FakeService)
    assert isinstance(shell.output_preview_registry, _FakeService)
    assert isinstance(shell._error_presenter, _FakeErrorPresenter)
    assert (
        composition.workspace_controller.error_presenter_during_creation
        is shell._error_presenter
    )
    assert composition.workspace_controller is shell.workspace_controller
    assert composition.workspace_file_actions is shell.workspace_file_actions
    assert shell.workspace_file_actions is shell.workspace_controller.file_actions
    assert composition.workflow_workspace is shell.workflow_workspace
    assert shell.workflow_workspace is shell.workspace_controller.workflow_workspace
    assert (
        composition.workflow_duplicate_service
        is shell.workspace_controller.workflow_duplicate_service
    )
    assert shell.workflow_duplicate_service is composition.workflow_duplicate_service
    assert (
        composition.workspace_generation_actions
        is shell.workspace_controller.generation_actions
    )
    assert (
        shell.workspace_generation_actions is composition.workspace_generation_actions
    )
    assert (
        composition.workspace_scene_generation_actions
        is shell.workspace_controller.scene_generation_actions
    )
    assert (
        shell.workspace_scene_generation_actions
        is composition.workspace_scene_generation_actions
    )
    assert (
        composition.workspace_loaded_cube_surface_actions
        is shell.workspace_controller.loaded_cube_surface_actions
    )
    assert (
        shell.workspace_loaded_cube_surface_actions
        is composition.workspace_loaded_cube_surface_actions
    )
    assert composition.workspace_search_actions is shell.workspace_search_actions
    assert shell.workspace_search_actions is shell.workspace_controller.search_actions
    assert (
        composition.workspace_cube_picker_actions is shell.workspace_cube_picker_actions
    )
    assert (
        shell.workspace_cube_picker_actions
        is shell.workspace_controller.cube_picker_actions
    )
    assert (
        composition.workspace_cube_stack_actions is shell.workspace_cube_stack_actions
    )
    assert (
        shell.workspace_cube_stack_actions
        is shell.workspace_controller.cube_stack_actions
    )
    assert composition.workspace_canvas_actions is shell.workspace_canvas_actions
    assert shell.workspace_canvas_actions is shell.workspace_controller.canvas_actions
    assert (
        composition.workspace_canvas_drag_source_classifier
        is shell.workspace_canvas_drag_source_classifier
    )
    assert shell.workspace_controller.shell is shell
    assert shell.generation_feedback_sink.shell is shell
    assert (
        shell.generation_feedback_dispatcher.kwargs["sink"]
        is shell.generation_feedback_sink
    )
    assert isinstance(
        shell.generation_feedback_dispatcher.kwargs["coalescer"],
        _FakeGenerationFeedbackCoalescer,
    )
    assert (
        shell.workspace_drop_controller.kwargs["load_recipe_document"]
        == shell.workspace_file_actions.load_recipe_document
    )
    assert (
        shell.workspace_drop_controller.kwargs["ignored_drag_source"]
        == shell.workspace_canvas_drag_source_classifier.is_workspace_canvas_drag_source
    )
    assert (
        shell.workspace_canvas_drag_source_classifier.is_workspace_canvas_drag_source(
            shell
        )
        is True
    )


def test_compose_shell_controllers_assigns_controllers_and_initial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure controller construction stays outside MainWindow.__init__."""

    controller_names = [
        "WorkflowIssueState",
        "CubeStackService",
        "ShellChromeController",
        "ShellLayoutRestoreController",
        "WorkspaceLayoutController",
        "SessionSnapshotCaptureAdapter",
        "SessionAutosaveController",
        "WorkspaceRestoreController",
        "RestoredWorkflowMaterializer",
        "WorkspaceRestoreImageAdapter",
        "EditorViewportRestoreController",
        "RestoreProjectionController",
        "GenerationResultWorkspaceMaterializer",
        "InitialWorkspaceController",
        "SearchOverlayController",
        "ProgressOverlayController",
        "GenerationActionController",
        "GenerationFeedbackPresenter",
        "ComfyRuntimeActions",
        "WorkflowUiFactory",
        "ActiveWorkflowSurfaceRefresher",
        "CanvasRouteController",
        "MainWindowSignalBinder",
        "ShellEventFilterController",
        "ShellFrameIntegrationController",
        "ShellReloadLifecycleController",
        "ShellRecipeModelResolutionController",
        "ShellActiveSurfaceController",
        "ShellRestoreWarmupController",
        "ShellPrehydratedRestoreController",
        "WorkspaceSplitterController",
        "CubeStackPresentationController",
        "GenerationQueuePanelTransition",
        "GenerationQueueController",
    ]
    for name in controller_names:
        monkeypatch.setattr(main_window_composition, name, _FakeController)
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        splitter=object(),
        editor_output_container=object(),
        canvas_tabs_container=object(),
        cube_stack_container=object(),
        cube_stacks={},
        cubeStackModeButton=object(),
        workspace_body_material_surface=object(),
        request_session_autosave=lambda: None,
    )

    composition = main_window_composition.compose_shell_controllers(shell)

    assert composition.shell_chrome_controller is shell.shell_chrome_controller
    assert (
        composition.shell_layout_restore_controller
        is shell.shell_layout_restore_controller
    )
    assert composition.workspace_layout_controller is shell.workspace_layout_controller
    assert composition.canvas_route_controller is shell.canvas_route_controller
    assert shell.generation_queue_controller.installed is True
    assert shell.shell_prehydrated_restore_controller.restore_initialized is True
    assert shell.session_autosave_controller.coordinator_ensured is True
    assert getattr(shell.workspace_layout_controller, "layout_trace_messages") == [
        "initialized durable layout state"
    ]
    assert shell._generation_queue_panel_visible is False
    assert shell._active_workspace_route == "wf-a"
    assert shell._remembered_workflow_splitter_sizes == ()
    assert shell._restored_shell_layout_applied is False
    assert shell._pending_restored_shell_layout is None
    assert shell._restore_asset_preload is None
    assert shell._startup_autosave_unmuted_marked is False


def test_compose_input_canvas_controllers_assigns_presenter_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure Input canvas presenter composition stays outside MainWindow.__init__."""

    monkeypatch.setattr(
        main_window_composition,
        "WorkflowInputCanvasService",
        _FakeWorkflowInputCanvasService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "InputMaskToolController",
        _FakeInputMaskToolController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "InputCanvasShellAdapter",
        _FakeInputCanvasShellAdapter,
    )
    monkeypatch.setattr(
        main_window_composition,
        "InputCanvasPresenter",
        _FakeInputCanvasPresenter,
    )
    monkeypatch.setattr(
        main_window_composition,
        "InputMaskDirtyTracker",
        _FakeInputMaskDirtyTracker,
    )
    monkeypatch.setattr(
        main_window_composition,
        "InputMaskSaveController",
        _FakeInputMaskSaveController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "InputCanvasCapabilityService",
        _FakeInputCanvasCapabilityService,
    )
    pane = object()
    current_image_id_for_event = object()
    menu_state_sink = object()
    input_canvas = SimpleNamespace(
        pane=pane,
        current_image_id_for_event=current_image_id_for_event,
        set_mask_tool_menu_state=menu_state_sink,
        maskToolMenuStateRequested=_FakeSignal(),
        maskToolModeRequested=_FakeSignal(),
    )
    shell = SimpleNamespace(
        canvas_tabs=SimpleNamespace(canvas_map={"Input": input_canvas}),
        input_canvas_plan_service=object(),
        graph_section_service=object(),
        input_canvas_state_service=object(),
        canvas_io_service=object(),
        workflow_asset_service=object(),
        workflow_session_service=object(),
        path_bundle=SimpleNamespace(projects_dir="E:\\projects"),
        get_active_workflow=lambda: object(),
        active_editor_panel=object(),
        _error_presenter=object(),
    )

    composition = main_window_composition.compose_input_canvas_controllers(shell)

    assert (
        composition.workflow_input_canvas_service is shell.workflow_input_canvas_service
    )
    assert composition.input_canvas_presenter is shell.input_canvas_presenter
    assert composition.input_mask_save_controller is shell.input_mask_save_controller
    assert shell.workflow_input_canvas_service.kwargs == {
        "input_canvas_plan_service": shell.input_canvas_plan_service,
        "input_canvas_state_service": shell.input_canvas_state_service,
        "canvas_io_service": shell.canvas_io_service,
        "workflow_asset_service": shell.workflow_asset_service,
        "graph_section_service": shell.graph_section_service,
    }
    assert shell.input_mask_tool_controller.kwargs == {
        "input_pane": pane,
        "current_image_id_provider": current_image_id_for_event,
        "menu_state_sink": menu_state_sink,
    }
    assert input_canvas.maskToolMenuStateRequested.connected == [
        shell.input_mask_tool_controller.refresh_tool_menu_state
    ]
    assert input_canvas.maskToolModeRequested.connected == [
        shell.input_mask_tool_controller.request_tool_mode
    ]
    assert shell.input_canvas_shell_adapter.shell is shell
    assert shell.input_canvas_presenter.kwargs["input_pane"] is pane
    assert (
        shell.input_canvas_presenter.kwargs["workflow_input_canvas_service"]
        is shell.workflow_input_canvas_service
    )
    assert (
        shell.input_canvas_presenter.kwargs["workflow_name_provider"]
        is shell.input_canvas_shell_adapter.resolve_workflow_name
    )
    assert (
        shell.input_canvas_presenter.kwargs["mark_canvas_changed"]
        is shell.input_canvas_shell_adapter.mark_input_canvas_changed
    )
    assert (
        shell.input_mask_save_controller.kwargs["dirty_tracker"]
        is shell.input_mask_dirty_tracker
    )
    refresh_saved_mask = shell.input_mask_save_controller.kwargs["refresh_saved_mask"]
    refresh_saved_mask("cube-a", "node-a", object())
    assert shell.input_canvas_presenter.refreshed_masks == [("cube-a", "node-a")]
    assert (
        shell.input_canvas_capability_service.input_canvas_plan_service
        is shell.input_canvas_plan_service
    )
    assert (
        shell.input_canvas_capability_service.graph_section_service
        is shell.graph_section_service
    )


def test_compose_output_canvas_controllers_assigns_pipeline_and_strip_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure Output canvas pipeline composition stays outside MainWindow.__init__."""

    monkeypatch.setattr(
        main_window_composition,
        "OutputImagePipeline",
        _FakeOutputImagePipeline,
    )
    monkeypatch.setattr(
        main_window_composition,
        "GenerationProgressStripRegistry",
        _FakeGenerationProgressStripRegistry,
    )
    preparation_dispatcher = SimpleNamespace(shutdown=lambda: None)
    monkeypatch.setattr(
        main_window_composition,
        "_output_image_preparation_dispatcher",
        lambda _shell: preparation_dispatcher,
    )
    progress_strip_registrations: list[object] = []
    shell = SimpleNamespace(
        workflow_session_service=object(),
        canvas_io_service=object(),
        workspace_controller=object(),
        workspace_canvas_actions=object(),
        output_canvas_projection_coordinator=object(),
        canvas_tabs=object(),
        generation_job_queue_service=object(),
        output_floating_chrome_factory=SimpleNamespace(
            set_progress_strip_registry=progress_strip_registrations.append
        ),
        prompt_interaction_activity_tracker=_PromptInteractionActivityTracker(),
        shell_resource_lifecycle=_FakeShellResourceLifecycle(),
    )

    composition = main_window_composition.compose_output_canvas_controllers(shell)

    assert composition.output_image_pipeline is shell.output_image_pipeline
    assert (
        composition.generation_progress_strip_registry
        is shell.generation_progress_strip_registry
    )
    assert shell.output_image_pipeline.kwargs == {
        "workflow_session_service": shell.workflow_session_service,
        "canvas_io_service": shell.canvas_io_service,
        "output_commit_handler": shell.workspace_canvas_actions,
        "output_canvas_projection_coordinator": (
            shell.output_canvas_projection_coordinator
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
    assert shell.generation_progress_strip_registry.parent is shell
    assert progress_strip_registrations == [shell.generation_progress_strip_registry]
    assert shell.shell_resource_lifecycle.registrations == [
        ("output_image_preparation", preparation_dispatcher.shutdown)
    ]


def test_compose_editor_busy_controller_assigns_busy_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure editor busy overlay wiring stays outside MainWindow.__init__."""

    monkeypatch.setattr(
        main_window_composition,
        "EditorBusyCoordinator",
        _FakeEditorBusyCoordinator,
    )
    cancel_requested = _FakeSignal()
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-b"),
        editorBusyOverlay=SimpleNamespace(cancel_requested=cancel_requested),
        shell_resource_lifecycle=_FakeShellResourceLifecycle(),
        _active_workspace_route="wf-b",
    )

    composition = main_window_composition.compose_editor_busy_controller(shell)

    assert composition.editor_busy is shell.editor_busy
    assert shell.editor_busy.kwargs["overlay"] is shell.editorBusyOverlay
    active_workflow_id = shell.editor_busy.kwargs["active_workflow_id"]
    assert active_workflow_id() == "wf-b"
    is_editor_surface_active = shell.editor_busy.kwargs["is_editor_surface_active"]
    assert is_editor_surface_active() is True
    shell._active_workspace_route = "settings"
    assert is_editor_surface_active() is False
    assert shell.shell_resource_lifecycle.registrations == [
        ("editor_busy", shell.editor_busy.shutdown)
    ]
    assert cancel_requested.connected == [shell.editor_busy.request_active_cancel]


def test_compose_workflow_lifecycle_services_assigns_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure workflow lifecycle services stay outside MainWindow.__init__."""

    monkeypatch.setattr(
        main_window_composition,
        "ClosedWorkflowBuffer",
        _FakeWorkflowLifecycleService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ClosedWorkflowSnapshotService",
        _FakeWorkflowLifecycleService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "WorkflowActivityService",
        _FakeWorkflowLifecycleService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "NodeDefinitionRefreshController",
        _FakeNodeDefinitionRefreshController,
    )
    shell = SimpleNamespace()

    composition = main_window_composition.compose_workflow_lifecycle_services(shell)

    assert composition.closed_workflow_buffer is shell.closed_workflow_buffer
    assert (
        composition.closed_workflow_snapshot_service
        is shell.closed_workflow_snapshot_service
    )
    assert composition.workflow_activity_service is shell.workflow_activity_service
    assert (
        composition.node_definition_refresh_controller
        is shell.node_definition_refresh_controller
    )
    assert shell.node_definition_refresh_controller.shell is shell


def test_compose_editor_metadata_controllers_assigns_metadata_refreshers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure editor metadata refresh construction stays outside MainWindow."""

    monkeypatch.setattr(
        main_window_composition,
        "PanelLoraMetadataRefreshController",
        _FakePanelLoraMetadataRefreshController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ModelMetadataSurfaceRefreshController",
        _FakeModelMetadataSurfaceRefreshController,
    )
    executor = object()
    executor_requests: list[tuple[object, str]] = []
    model_catalog_dispatcher = object()
    monkeypatch.setattr(
        main_window_composition,
        "QtOwnerThreadDispatcher",
        lambda parent: model_catalog_dispatcher,
    )

    def _create_prompt_task_executor(owner: object, owner_id: str) -> object:
        """Record one prompt task executor factory request."""

        executor_requests.append((owner, owner_id))
        return executor

    model_catalog_submitter = SimpleNamespace(close=lambda: None)
    runtime_submitter_requests: list[dict[str, object]] = []

    def _runtime_submitter(
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> object:
        runtime_submitter_requests.append(
            {
                "name": name,
                "owner_id": owner_id,
                "dispatcher": dispatcher,
            }
        )
        return model_catalog_submitter

    execution_runtime = SimpleNamespace(submitter=_runtime_submitter)
    editor_a = object()
    editor_b = object()
    shell = SimpleNamespace(
        prompt_lora_catalog_service=object(),
        editor_panels={"a": editor_a, "b": editor_b},
        execution_runtime=execution_runtime,
        editor_panel_execution_factories=SimpleNamespace(
            prompt_task_executor_factory=_create_prompt_task_executor,
        ),
        shell_resource_lifecycle=_FakeShellResourceLifecycle(),
    )

    composition = main_window_composition.compose_editor_metadata_controllers(shell)

    assert (
        composition.lora_metadata_refresh_coordinator
        is shell._lora_metadata_refresh_coordinator
    )
    assert (
        composition.model_metadata_surface_refresh_controller
        is shell.model_metadata_surface_refresh_controller
    )
    lora_kwargs = shell._lora_metadata_refresh_coordinator.kwargs
    assert lora_kwargs["catalog_service"] is shell.prompt_lora_catalog_service
    assert lora_kwargs["parent"] is shell
    assert lora_kwargs["editor_panels"]() == (editor_a, editor_b)
    assert lora_kwargs["executor"] is executor
    assert executor_requests == [(shell, f"panel-lora-metadata-refresh:{id(shell):x}")]
    assert shell.model_metadata_surface_refresh_controller.args == (shell,)
    surface_kwargs = shell.model_metadata_surface_refresh_controller.kwargs
    assert surface_kwargs["parent"] is shell
    assert surface_kwargs["snapshot_refresh_submitter"] is model_catalog_submitter
    assert surface_kwargs["close_snapshot_refresh_submitter"] is (
        model_catalog_submitter.close
    )
    assert len(runtime_submitter_requests) == 1
    runtime_submitter_request = runtime_submitter_requests[0]
    assert runtime_submitter_request["name"] == "model_catalog"
    assert runtime_submitter_request["owner_id"] == (
        f"model_catalog_snapshot_refresh_{id(shell):x}"
    )
    assert runtime_submitter_request["dispatcher"] is model_catalog_dispatcher
    assert [
        name for name, _cleanup in shell.shell_resource_lifecycle.registrations
    ] == ["panel_lora_metadata_refresh", "model_catalog_snapshot_refresh"]


def test_compose_runtime_controllers_assigns_runtime_controllers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure runtime controller construction stays outside MainWindow.__init__."""

    monkeypatch.setattr(
        main_window_composition,
        "GenerationInterruptFailurePresenter",
        _FakeGenerationInterruptFailurePresenter,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ErrorPresenter",
        _FakeErrorPresenter,
    )
    monkeypatch.setattr(
        main_window_composition,
        "CubeLibraryUpdateController",
        _FakeDependencyController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ModelCatalogUpdateController",
        _FakeDependencyController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "SettingsRouteController",
        _FakeSettingsRouteController,
    )
    cube_library_dispatcher = object()
    monkeypatch.setattr(
        main_window_composition,
        "QtOwnerThreadDispatcher",
        lambda parent: cube_library_dispatcher,
    )
    observers: list[object] = []
    comfy_visibility_calls: list[bool] = []
    queue_observer = object()
    cube_library_submitter = SimpleNamespace(close=lambda: None)
    model_catalog_change_submitter = SimpleNamespace(close=lambda: None)
    runtime_submitter_requests: list[dict[str, object]] = []

    def _runtime_submitter(
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> object:
        runtime_submitter_requests.append(
            {"name": name, "owner_id": owner_id, "dispatcher": dispatcher}
        )
        if name == "node_definition":
            return model_catalog_change_submitter
        return cube_library_submitter

    shell = SimpleNamespace(
        generation_action_controller=SimpleNamespace(
            handle_generation_queue_state_changed=queue_observer
        ),
        generation_job_queue_service=SimpleNamespace(add_observer=observers.append),
        comfy_runtime_actions=SimpleNamespace(
            set_comfy_output_panel_visible=comfy_visibility_calls.append
        ),
        execution_runtime=SimpleNamespace(submitter=_runtime_submitter),
        shell_resource_lifecycle=_FakeShellResourceLifecycle(),
    )
    dependencies = SimpleNamespace(comfy_output_stream=object())

    composition = main_window_composition.compose_runtime_controllers(
        shell,
        dependencies,  # type: ignore[arg-type]
    )

    assert composition.generation_job_queue_observer is queue_observer
    assert observers == [queue_observer]
    assert shell._current_generate_mode == "generate"
    assert shell._backend_state == "starting"
    assert shell._last_progress_view_state is None
    assert shell._sampler_progress_model_fields_cleared is False
    assert shell._comfy_output_stream is dependencies.comfy_output_stream
    assert (
        shell.generation_interrupt_failure_presenter.output_stream
        is dependencies.comfy_output_stream
    )
    shell._error_presenter.kwargs["open_console"]()
    assert comfy_visibility_calls == [True]
    assert shell.cube_library_update_controller.shell is shell
    assert shell.cube_library_update_controller.dependencies is dependencies
    assert shell.cube_library_update_controller.kwargs["refresh_submitter"] is (
        cube_library_submitter
    )
    assert shell.cube_library_update_controller.kwargs["close_refresh_submitter"] is (
        cube_library_submitter.close
    )
    assert len(runtime_submitter_requests) == 2
    assert runtime_submitter_requests[0]["name"] == "cube_library_update"
    assert runtime_submitter_requests[0]["owner_id"] == "cube_library_update_controller"
    assert runtime_submitter_requests[0]["dispatcher"] is cube_library_dispatcher
    assert shell.model_catalog_update_controller.shell is shell
    assert shell.model_catalog_update_controller.dependencies is dependencies
    assert shell.model_catalog_update_controller.kwargs[
        "node_definition_submitter"
    ] is (model_catalog_change_submitter)
    assert (
        shell.model_catalog_update_controller.kwargs["close_node_definition_submitter"]
        is model_catalog_change_submitter.close
    )
    assert runtime_submitter_requests[1]["name"] == "node_definition"
    assert runtime_submitter_requests[1]["owner_id"] == (
        f"model_catalog_change_{id(shell):x}"
    )
    assert shell._initial_workspace_hydrated is False
    assert shell.settings_route_controller.shell is shell
    assert shell.settings_route_controller.created_settings_workspace is True
    assert [
        name for name, _cleanup in shell.shell_resource_lifecycle.registrations
    ] == ["cube_library_updates", "model_catalog_updates"]
    assert (
        shell.settings_route_controller.error_presenter_during_creation
        is shell._error_presenter
    )
    assert (
        shell.settings_route_controller.shell_error_presenter_during_creation
        is shell._error_presenter
    )


def test_connect_shell_signals_wires_controllers_and_startup_callbacks() -> None:
    """Ensure signal wiring stays outside MainWindow.__init__."""

    binder_calls: list[str] = []
    scheduled: list[tuple[int, object]] = []
    installed_filters: list[object] = []
    generation_mode_calls: list[str] = []
    comfy_visibility_calls: list[bool] = []
    canvas_route_calls: list[str] = []
    autosave_calls: list[str] = []
    layout_trace_calls: list[str] = []
    visibility_changed = _Signal()
    splitter_moved = _Signal()
    output_splitter_moved = _Signal()
    panel_changed = _Signal()
    mode_selected = _Signal()
    input_canvas = object()
    output_canvas = object()
    shell = SimpleNamespace(
        main_window_signal_binder=SimpleNamespace(
            connect_generation_feedback_signals=lambda: binder_calls.append(
                "generation"
            ),
            connect_search_signals=lambda: binder_calls.append("search"),
            connect_menu_action_signals=lambda: binder_calls.append("menu"),
            connect_workflow_tab_signals=lambda: binder_calls.append("tabs"),
            connect_canvas_signals=lambda **kwargs: binder_calls.append(
                f"canvas:{kwargs['input_canvas'] is input_canvas}:"
                f"{kwargs['output_canvas'] is output_canvas}"
            ),
        ),
        canvas_tabs=SimpleNamespace(
            canvas_map={"Input": input_canvas, "Output": output_canvas},
            visibility_changed=visibility_changed,
        ),
        canvas_route_controller=SimpleNamespace(
            connect_canvas_route_signals=lambda: canvas_route_calls.append("connect")
        ),
        workspace_layout_controller=SimpleNamespace(
            toggle_canvas_tabs=lambda: None,
            handle_main_splitter_moved=lambda: None,
            handle_editor_output_splitter_moved=lambda: None,
            apply_startup_default_splitter_layout=lambda: None,
            log_editor_width_trace=lambda message: layout_trace_calls.append(message),
        ),
        session_autosave_controller=SimpleNamespace(
            connect_canvas_layout_autosave=lambda: autosave_calls.append("canvas")
        ),
        splitter=SimpleNamespace(splitterMoved=splitter_moved),
        editor_output_splitter=SimpleNamespace(splitterMoved=output_splitter_moved),
        editor_panel_container=SimpleNamespace(currentChanged=panel_changed),
        search_overlay_controller=SimpleNamespace(position_search_box=lambda: None),
        progress_overlay_controller=SimpleNamespace(
            position_progress_overlay=lambda: None
        ),
        generation_action_controller=SimpleNamespace(
            set_generation_selected_mode=lambda mode: generation_mode_calls.append(mode)
        ),
        generationActionCluster=SimpleNamespace(generateModeSelected=mode_selected),
        _generation_action_cluster_mode_callback=None,
        comfy_runtime_actions=SimpleNamespace(
            set_comfy_output_panel_visible=lambda visible: (
                comfy_visibility_calls.append(visible)
            )
        ),
        installEventFilter=lambda target: installed_filters.append(target),
    )

    main_window_composition.connect_shell_signals(
        shell,
        startup_timer=None,
        single_shot=lambda delay, callback: scheduled.append((delay, callback)),
    )

    assert binder_calls == [
        "generation",
        "search",
        "menu",
        "tabs",
        "canvas:True:True",
    ]
    assert canvas_route_calls == ["connect"]
    assert autosave_calls == ["canvas"]
    assert visibility_changed.connected == [
        shell.workspace_layout_controller.toggle_canvas_tabs
    ]
    assert splitter_moved.connected == [
        shell.workspace_layout_controller.handle_main_splitter_moved
    ]
    assert output_splitter_moved.connected == [
        shell.workspace_layout_controller.handle_editor_output_splitter_moved
    ]
    assert len(panel_changed.connected) == 1
    assert generation_mode_calls == ["generate"]
    assert mode_selected.connected == [shell._generation_action_cluster_mode_callback]
    assert comfy_visibility_calls == [False]
    assert layout_trace_calls == ["scheduling startup default splitter layout"]
    assert scheduled == [
        (0, shell.workspace_layout_controller.apply_startup_default_splitter_layout),
        (0, shell.progress_overlay_controller.position_progress_overlay),
        (0, shell.search_overlay_controller.position_search_box),
    ]
    assert installed_filters == [shell]


def test_main_window_routes_dependency_capture_through_composition_module() -> None:
    """Verify MainWindow delegates dependency capture instead of owning the method."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")

    assert "def _capture_dependencies" not in source
    assert "capture_dependencies(self, dependencies)" in source
    assert "compose_shell_controllers(self)" in source
    assert "connect_shell_signals(" in source


def test_main_window_composition_does_not_import_qt() -> None:
    """Keep dependency capture independent from direct Qt imports."""

    source = COMPOSITION_SOURCE.read_text(encoding="utf-8")

    assert "PySide6" not in source
    assert "qfluentwidgets" not in source
