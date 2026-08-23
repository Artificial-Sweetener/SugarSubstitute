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

"""Verify MainWindow composes runtime controllers and their cleanup paths."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields

import pytest

from substitute.presentation.shell import main_window_composition
from substitute.presentation.shell.main_window_dependencies import (
    MainWindowDependencies,
)


class _Submitter:
    """Provide a named runtime submitter cleanup endpoint."""

    def close(self) -> None:
        """Represent submitter cleanup."""


class _ExecutionRuntime:
    """Record runtime submitter requests."""

    def __init__(self, cube_submitter: _Submitter, node_submitter: _Submitter) -> None:
        """Initialize deterministic submitter routing."""

        self.cube_submitter = cube_submitter
        self.node_submitter = node_submitter
        self.requests: list[tuple[str, str, object]] = []

    def submitter(self, name: str, *, owner_id: str, dispatcher: object) -> _Submitter:
        """Record one request and return the owner-specific submitter."""

        self.requests.append((name, owner_id, dispatcher))
        return self.node_submitter if name == "node_definition" else self.cube_submitter


class _ResourceLifecycle:
    """Record named runtime cleanup registrations."""

    def __init__(self) -> None:
        """Initialize no resource registrations."""

        self.registrations: list[tuple[str, Callable[[], None]]] = []

    def register(self, name: str, cleanup: Callable[[], None]) -> None:
        """Record one cleanup callback."""

        self.registrations.append((name, cleanup))


class _QueueService:
    """Capture the runtime queue observer."""

    def __init__(self) -> None:
        """Initialize no observer."""

        self.observers: list[object] = []

    def add_observer(self, observer: object) -> None:
        """Record one queue observer."""

        self.observers.append(observer)


class _GenerationActions:
    """Provide the queue-state observation endpoint."""

    def __init__(self) -> None:
        """Create a stable queue observer token."""

        self.handle_generation_queue_state_changed = object()


class _ComfyRuntimeActions:
    """Record output-console visibility changes."""

    def __init__(self) -> None:
        """Initialize no visibility changes."""

        self.visibility: list[bool] = []

    def set_comfy_output_panel_visible(self, visible: bool) -> None:
        """Record one output-console visibility change."""

        self.visibility.append(visible)


class _GenerationInterruptFailurePresenter:
    """Capture the Comfy output stream."""

    def __init__(self, output_stream: object) -> None:
        """Store the output stream."""

        self.output_stream = output_stream


class _ErrorPresenter:
    """Capture error-presenter composition callbacks."""

    def __init__(self, **kwargs: object) -> None:
        """Store presenter construction arguments."""

        self.kwargs = kwargs


class _UpdateController:
    """Capture one runtime update controller's dependencies and cleanup methods."""

    def __init__(self, shell: object, dependencies: object, **kwargs: object) -> None:
        """Store construction inputs."""

        self.shell = shell
        self.dependencies = dependencies
        self.kwargs = kwargs

    def stop_listener(self) -> None:
        """Provide cube-library listener cleanup."""

    def stop(self) -> None:
        """Provide model-catalog cleanup."""


class _SettingsRouteController:
    """Capture settings route construction and workspace initialization."""

    def __init__(self, shell: object, *, error_presenter: object | None) -> None:
        """Store the shell and injected error presenter."""

        self.shell = shell
        self.error_presenter = error_presenter
        self.created_settings_workspace = False
        self.error_presenter_during_creation: object | None = None
        self.shell_error_presenter_during_creation: object | None = None

    def create_settings_workspace(self) -> None:
        """Record creation with the error presenter visible to the shell."""

        self.error_presenter_during_creation = self.error_presenter
        self.shell_error_presenter_during_creation = getattr(
            self.shell,
            "_error_presenter",
            None,
        )
        self.created_settings_workspace = True


class _Dependencies:
    """Build the exact dependency owner with a controlled output stream."""

    def __init__(self) -> None:
        """Create a stable output stream token."""

        self.comfy_output_stream = object()

    def build(self) -> MainWindowDependencies:
        """Build the production dependency value object with opaque collaborators."""

        dependencies = object.__new__(MainWindowDependencies)
        for dependency_field in fields(MainWindowDependencies):
            object.__setattr__(dependencies, dependency_field.name, object())
        object.__setattr__(
            dependencies,
            "comfy_output_stream",
            self.comfy_output_stream,
        )
        return dependencies


class _Shell:
    """Hold runtime inputs and observable composed state."""

    def __init__(self) -> None:
        """Create the minimal runtime shell contract."""

        self.generation_action_controller = _GenerationActions()
        self.generation_job_queue_service = _QueueService()
        self.comfy_runtime_actions = _ComfyRuntimeActions()
        self.cube_submitter = _Submitter()
        self.node_submitter = _Submitter()
        self.execution_runtime = _ExecutionRuntime(
            self.cube_submitter,
            self.node_submitter,
        )
        self.shell_resource_lifecycle = _ResourceLifecycle()
        self._error_presenter: object | None = None
        self.generation_interrupt_failure_presenter: object | None = None
        self.cube_library_update_controller: object | None = None
        self.model_catalog_update_controller: object | None = None
        self.settings_route_controller: object | None = None
        self._current_generate_mode = ""
        self._backend_state = ""
        self._last_progress_view_state: object | None = object()
        self._sampler_progress_model_fields_cleared = True
        self._comfy_output_stream: object | None = None
        self._initial_workspace_hydrated = True


def test_compose_runtime_controllers_assigns_runtime_controllers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose runtime state, update owners, error routing, and cleanup paths."""

    monkeypatch.setattr(
        main_window_composition,
        "GenerationInterruptFailurePresenter",
        _GenerationInterruptFailurePresenter,
    )
    monkeypatch.setattr(main_window_composition, "ErrorPresenter", _ErrorPresenter)
    monkeypatch.setattr(
        main_window_composition,
        "CubeLibraryUpdateController",
        _UpdateController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ModelCatalogUpdateController",
        _UpdateController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "SettingsRouteController",
        _SettingsRouteController,
    )
    dispatcher = object()
    monkeypatch.setattr(
        main_window_composition,
        "QtOwnerThreadDispatcher",
        lambda _parent: dispatcher,
    )
    shell = _Shell()
    dependencies = _Dependencies()
    dependency_bundle = dependencies.build()

    composition = main_window_composition.compose_runtime_controllers(
        shell,
        dependency_bundle,
    )

    assert (
        composition.generation_job_queue_observer
        is shell.generation_action_controller.handle_generation_queue_state_changed
    )
    assert shell.generation_job_queue_service.observers == [
        shell.generation_action_controller.handle_generation_queue_state_changed
    ]
    assert shell._current_generate_mode == "generate"
    assert shell._backend_state == "starting"
    assert shell._last_progress_view_state is None
    assert shell._sampler_progress_model_fields_cleared is False
    assert shell._comfy_output_stream is dependency_bundle.comfy_output_stream
    interrupt_presenter = shell.generation_interrupt_failure_presenter
    assert isinstance(interrupt_presenter, _GenerationInterruptFailurePresenter)
    assert interrupt_presenter.output_stream is dependency_bundle.comfy_output_stream
    error_presenter = shell._error_presenter
    assert isinstance(error_presenter, _ErrorPresenter)
    open_console = error_presenter.kwargs["open_console"]
    assert callable(open_console)
    open_console()
    assert shell.comfy_runtime_actions.visibility == [True]
    cube_controller = shell.cube_library_update_controller
    assert isinstance(cube_controller, _UpdateController)
    assert cube_controller.shell is shell
    assert cube_controller.dependencies is dependency_bundle
    assert cube_controller.kwargs["refresh_submitter"] is shell.cube_submitter
    assert getattr(
        cube_controller.kwargs["close_refresh_submitter"], "__self__", None
    ) is (shell.cube_submitter)
    model_controller = shell.model_catalog_update_controller
    assert isinstance(model_controller, _UpdateController)
    assert model_controller.shell is shell
    assert model_controller.dependencies is dependency_bundle
    assert model_controller.kwargs["node_definition_submitter"] is shell.node_submitter
    assert (
        getattr(
            model_controller.kwargs["close_node_definition_submitter"],
            "__self__",
            None,
        )
        is shell.node_submitter
    )
    assert shell.execution_runtime.requests[0] == (
        "cube_library_update",
        "cube_library_update_controller",
        dispatcher,
    )
    assert shell.execution_runtime.requests[1][0] == "node_definition"
    assert (
        shell.execution_runtime.requests[1][1] == f"model_catalog_change_{id(shell):x}"
    )
    assert shell._initial_workspace_hydrated is False
    settings_controller = shell.settings_route_controller
    assert isinstance(settings_controller, _SettingsRouteController)
    assert settings_controller.shell is shell
    assert settings_controller.created_settings_workspace is True
    assert [
        name for name, _cleanup in shell.shell_resource_lifecycle.registrations
    ] == [
        "cube_library_updates",
        "model_catalog_updates",
    ]
    assert settings_controller.error_presenter_during_creation is error_presenter
    assert settings_controller.shell_error_presenter_during_creation is error_presenter
