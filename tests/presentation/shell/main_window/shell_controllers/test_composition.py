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

"""Verify MainWindow composes its post-widget controller transaction."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from substitute.presentation.shell import main_window_composition


class _RecordedController:
    """Record constructor inputs and the lifecycle actions this transaction owns."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Store construction inputs with deterministic lifecycle state."""

        self.args = args
        self.kwargs = kwargs
        self.installed = False
        self.restore_initialized = False
        self.coordinator_ensured = False
        self.layout_trace_messages: list[str] = []

    def install_surfaces(self) -> None:
        """Record generation-queue surface installation."""

        self.installed = True

    def initialize_restore_state(self) -> None:
        """Record prehydrated-restore initialization."""

        self.restore_initialized = True

    def ensure_coordinator(self) -> None:
        """Record autosave coordinator initialization."""

        self.coordinator_ensured = True

    def log_editor_width_trace(self, message: str) -> None:
        """Record the durable layout initialization trace."""

        self.layout_trace_messages.append(message)

    def position_search_box(self) -> None:
        """Accept search-box positioning supplied to cube-stack composition."""


class _WorkflowSession:
    """Provide the active workflow identity used to initialize the shell route."""

    def __init__(self, active_workflow_id: str) -> None:
        """Store one stable active workflow identity."""

        self.active_workflow_id = active_workflow_id


class _Shell:
    """Hold inputs and observable outputs of shell-controller composition."""

    def __init__(self) -> None:
        """Create the minimal post-widget shell contract."""

        self.workflow_session_service = _WorkflowSession("wf-a")
        self.splitter = object()
        self.editor_output_container = object()
        self.canvas_host_container = object()
        self.cube_stack_container = object()
        self.cube_stacks: dict[str, object] = {}
        self.cubeStackModeButton = object()
        self.workspace_body_material_surface = object()
        self.request_session_autosave: Callable[[], None] = lambda: None
        self.shell_chrome_controller: object | None = None
        self.shell_layout_restore_controller: object | None = None
        self.workspace_layout_controller: object | None = None
        self.canvas_route_controller: object | None = None
        self.generation_queue_controller: object | None = None
        self.shell_prehydrated_restore_controller: object | None = None
        self.session_autosave_controller: object | None = None


_CONTROLLER_NAMES = (
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
)


def test_compose_shell_controllers_assigns_controllers_and_initial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose the complete post-widget controller transaction for one shell."""

    for controller_name in _CONTROLLER_NAMES:
        monkeypatch.setattr(
            main_window_composition,
            controller_name,
            _RecordedController,
        )
    monkeypatch.setattr(
        main_window_composition,
        "canvas_route_controller_for",
        lambda shell: _RecordedController(shell),
    )
    shell = _Shell()

    composition = main_window_composition.compose_shell_controllers(shell)

    assert composition.shell_chrome_controller is shell.shell_chrome_controller
    assert (
        composition.shell_layout_restore_controller
        is shell.shell_layout_restore_controller
    )
    assert composition.workspace_layout_controller is shell.workspace_layout_controller
    assert composition.canvas_route_controller is shell.canvas_route_controller
    queue_controller = shell.generation_queue_controller
    assert isinstance(queue_controller, _RecordedController)
    assert queue_controller.installed is True
    prehydrated_restore = shell.shell_prehydrated_restore_controller
    assert isinstance(prehydrated_restore, _RecordedController)
    assert prehydrated_restore.restore_initialized is True
    autosave_controller = shell.session_autosave_controller
    assert isinstance(autosave_controller, _RecordedController)
    assert autosave_controller.coordinator_ensured is True
    layout_controller = shell.workspace_layout_controller
    assert isinstance(layout_controller, _RecordedController)
    assert layout_controller.layout_trace_messages == [
        "initialized durable layout state"
    ]
    assert shell._generation_queue_panel_visible is False
    assert shell._active_workspace_route == "wf-a"
    assert shell._remembered_workflow_splitter_sizes == ()
    assert shell._restored_shell_layout_applied is False
    assert shell._pending_restored_shell_layout is None
    assert shell._restore_asset_preload is None
    assert shell._startup_autosave_unmuted_marked is False
