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

"""Verify MainWindow dependency capture and initial composition."""

from __future__ import annotations

from dataclasses import fields

import pytest

from substitute.presentation.shell import main_window_composition
from substitute.presentation.shell.main_window_dependencies import (
    MainWindowDependencies,
)


class _PromptInteractionActivityTracker:
    """Provide deterministic prompt-activity callbacks for dependency capture."""

    def is_prompt_interaction_active(self) -> bool:
        """Return the inactive interaction state."""

        return False

    def ms_since_last_prompt_interaction(self) -> int:
        """Return a stable elapsed interaction interval."""

        return 0


class _Shell:
    """Capture shell mutation performed by dependency composition."""

    cube_load_service: object
    recipe_io_service: object
    asset_reveal_service: object
    prompt_lora_catalog_service: object
    _open_reconfigure_window: object
    _reconfigure_window: object | None
    _comfy_settings_webview_dialog: object | None
    _pending_restore_projection_cache_capture_workflow_id: str
    workflow_surface_invalidation_service: object
    visual_authorization_service: object
    workflow_progress_service: object
    output_scene_run_service: object
    output_preview_registry: object
    _error_presenter: object
    workspace_controller: object
    workspace_file_actions: object
    workflow_workspace: object
    workflow_duplicate_service: object
    workspace_generation_actions: object
    workspace_scene_generation_actions: object
    workspace_loaded_cube_surface_actions: object
    workspace_search_actions: object
    workspace_cube_picker_actions: object
    workspace_cube_stack_actions: object
    workspace_canvas_actions: object
    workspace_canvas_drag_source_classifier: object

    def __init__(self) -> None:
        """Create the minimal shell state observed by this contract."""

        self.prompt_interaction_activity_tracker = _PromptInteractionActivityTracker()
        self.accept_drops_enabled: bool | None = None

    def setAcceptDrops(self, enabled: bool) -> None:
        """Record whether shell drops were enabled."""

        self.accept_drops_enabled = enabled


class _WorkspaceFileActions:
    """Provide the recipe-load callback delegated to the drop controller."""

    def load_recipe_document(self, document: object) -> object:
        """Return the loaded document unchanged."""

        return document


class _WorkflowWorkspace:
    """Provide the direct-workflow callbacks captured during composition."""

    def add_workflow(self) -> str:
        """Return a stable workflow identifier."""

        return "workflow-new"

    def reconcile_active_workflow_after_structural_mutation(
        self,
        *,
        force_refresh: bool,
    ) -> None:
        """Accept the requested post-mutation projection."""

        _ = force_refresh


class _FakeWorkspaceController:
    """Expose the workspace-owned collaborators captured by composition."""

    def __init__(self, shell: _Shell) -> None:
        """Create one stable workspace collaboration surface."""

        self.shell = shell
        self.error_presenter_during_creation = getattr(shell, "_error_presenter", None)
        self.file_actions = _WorkspaceFileActions()
        self.workflow_workspace = _WorkflowWorkspace()
        self.workflow_duplicate_service = object()
        self.generation_actions = object()
        self.scene_generation_actions = object()
        self.loaded_cube_surface_actions = object()
        self.search_actions = object()
        self.cube_picker_actions = object()
        self.cube_stack_actions = object()
        self.canvas_actions = object()


class _FakeGenerationFeedbackCoalescer:
    """Capture feedback coalescer collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store composed collaborators for verification."""

        self.kwargs = kwargs


class _FakeGenerationFeedbackDispatcher:
    """Capture feedback dispatcher collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store composed collaborators for verification."""

        self.kwargs = kwargs


class _FakeShellGenerationFeedbackSink:
    """Record the shell that owns feedback presentation."""

    def __init__(self, shell: _Shell) -> None:
        """Store the shell supplied by composition."""

        self.shell = shell


class _FakeWorkflowRecipeDropClassifier:
    """Capture recipe loading dependencies for workspace drops."""

    def __init__(
        self,
        recipe_io_service: object,
        direct_workflow_classifier: object | None = None,
    ) -> None:
        """Store recipe and direct-workflow classifiers."""

        self.recipe_io_service = recipe_io_service
        self.direct_workflow_classifier = direct_workflow_classifier


class _FakeWorkspaceCanvasDragSourceClassifier:
    """Identify the shell as the only ignored drag source."""

    def __init__(self, shell: _Shell) -> None:
        """Store the shell identity."""

        self.shell = shell

    def is_workspace_canvas_drag_source(self, source: object | None) -> bool:
        """Return whether the drag came from the owning shell."""

        return source is self.shell


class _FakeWorkspaceDropController:
    """Capture the workspace drop callbacks selected by composition."""

    def __init__(self, **kwargs: object) -> None:
        """Store composed callbacks for verification."""

        self.kwargs = kwargs


class _FakeService:
    """Represent one zero-argument shell service."""


class _FakeErrorPresenter:
    """Capture dependency-capture error presenter collaborators."""

    def __init__(self, **kwargs: object) -> None:
        """Store presenter constructor arguments."""

        self.kwargs = kwargs


def _dependencies() -> MainWindowDependencies:
    """Create the real dependency bundle with opaque identity-only values."""

    dependencies = object.__new__(MainWindowDependencies)
    for dependency_field in fields(MainWindowDependencies):
        object.__setattr__(dependencies, dependency_field.name, object())
    return dependencies


def _install_composition_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace external composition collaborators with local contract doubles."""

    replacements = {
        "WorkflowSurfaceInvalidationService": _FakeService,
        "VisualAuthorizationService": _FakeService,
        "WorkflowProgressService": _FakeService,
        "OutputSceneRunService": _FakeService,
        "OutputPreviewRegistry": _FakeService,
        "ErrorPresenter": _FakeErrorPresenter,
        "WorkspaceController": _FakeWorkspaceController,
        "GenerationFeedbackCoalescer": _FakeGenerationFeedbackCoalescer,
        "GenerationFeedbackDispatcher": _FakeGenerationFeedbackDispatcher,
        "ShellGenerationFeedbackSink": _FakeShellGenerationFeedbackSink,
        "WorkflowRecipeDropClassifier": _FakeWorkflowRecipeDropClassifier,
        "WorkspaceCanvasDragSourceClassifier": _FakeWorkspaceCanvasDragSourceClassifier,
        "WorkspaceDropController": _FakeWorkspaceDropController,
    }
    for collaborator_name, replacement in replacements.items():
        monkeypatch.setattr(main_window_composition, collaborator_name, replacement)


@pytest.fixture
def composition_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install the dependency-capture family collaborators."""

    _install_composition_fakes(monkeypatch)


def test_capture_dependencies_assigns_dependencies_and_composes_controllers(
    composition_fakes: None,
) -> None:
    """Ensure dependency capture remains behaviorally equivalent after extraction."""

    shell = _Shell()
    dependencies = _dependencies()

    composition = main_window_composition.capture_dependencies(shell, dependencies)

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
    assert isinstance(composition.workspace_controller, _FakeWorkspaceController)
    assert isinstance(
        composition.generation_feedback_sink,
        _FakeShellGenerationFeedbackSink,
    )
    assert isinstance(
        composition.generation_feedback_dispatcher,
        _FakeGenerationFeedbackDispatcher,
    )
    assert isinstance(
        composition.workspace_canvas_drag_source_classifier,
        _FakeWorkspaceCanvasDragSourceClassifier,
    )
    assert isinstance(
        composition.workspace_drop_controller, _FakeWorkspaceDropController
    )
    assert (
        composition.workspace_controller.error_presenter_during_creation
        is shell._error_presenter
    )
    assert composition.workspace_controller is shell.workspace_controller
    assert composition.workspace_file_actions is shell.workspace_file_actions
    assert shell.workspace_file_actions is composition.workspace_controller.file_actions
    assert composition.workflow_workspace is shell.workflow_workspace
    assert (
        shell.workflow_workspace is composition.workspace_controller.workflow_workspace
    )
    assert (
        composition.workflow_duplicate_service
        is composition.workspace_controller.workflow_duplicate_service
    )
    assert shell.workflow_duplicate_service is composition.workflow_duplicate_service
    assert (
        composition.workspace_generation_actions
        is composition.workspace_controller.generation_actions
    )
    assert (
        shell.workspace_generation_actions is composition.workspace_generation_actions
    )
    assert (
        composition.workspace_scene_generation_actions
        is composition.workspace_controller.scene_generation_actions
    )
    assert (
        shell.workspace_scene_generation_actions
        is composition.workspace_scene_generation_actions
    )
    assert (
        composition.workspace_loaded_cube_surface_actions
        is composition.workspace_controller.loaded_cube_surface_actions
    )
    assert (
        shell.workspace_loaded_cube_surface_actions
        is composition.workspace_loaded_cube_surface_actions
    )
    assert composition.workspace_search_actions is shell.workspace_search_actions
    assert (
        shell.workspace_search_actions
        is composition.workspace_controller.search_actions
    )
    assert (
        composition.workspace_cube_picker_actions is shell.workspace_cube_picker_actions
    )
    assert (
        shell.workspace_cube_picker_actions
        is composition.workspace_controller.cube_picker_actions
    )
    assert (
        composition.workspace_cube_stack_actions is shell.workspace_cube_stack_actions
    )
    assert (
        shell.workspace_cube_stack_actions
        is composition.workspace_controller.cube_stack_actions
    )
    assert composition.workspace_canvas_actions is shell.workspace_canvas_actions
    assert (
        shell.workspace_canvas_actions
        is composition.workspace_controller.canvas_actions
    )
    assert (
        composition.workspace_canvas_drag_source_classifier
        is shell.workspace_canvas_drag_source_classifier
    )
    assert composition.workspace_controller.shell is shell
    assert composition.generation_feedback_sink.shell is shell
    assert (
        composition.generation_feedback_dispatcher.kwargs["sink"]
        is composition.generation_feedback_sink
    )
    assert isinstance(
        composition.generation_feedback_dispatcher.kwargs["coalescer"],
        _FakeGenerationFeedbackCoalescer,
    )
    assert (
        composition.workspace_drop_controller.kwargs["load_recipe_document"]
        == composition.workspace_controller.file_actions.load_recipe_document
    )
    assert (
        composition.workspace_drop_controller.kwargs["ignored_drag_source"]
        == composition.workspace_canvas_drag_source_classifier.is_workspace_canvas_drag_source
    )
    assert (
        composition.workspace_canvas_drag_source_classifier.is_workspace_canvas_drag_source(
            shell
        )
        is True
    )
