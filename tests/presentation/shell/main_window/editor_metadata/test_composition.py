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

"""Verify MainWindow composes editor metadata refresh collaborators."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from substitute.presentation.shell import main_window_composition


class _PanelLoraMetadataRefreshController:
    """Capture panel LoRA metadata refresh construction."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor collaborators."""

        self.kwargs = kwargs

    def shutdown(self) -> None:
        """Provide the shell resource cleanup endpoint."""


class _RefreshCoordinator:
    """Provide model-surface refresh cleanup ownership."""

    def shutdown(self) -> None:
        """Provide the shell resource cleanup endpoint."""


class _ModelMetadataSurfaceRefreshController:
    """Capture model metadata surface refresh construction."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Store constructor arguments."""

        self.args = args
        self.kwargs = kwargs
        self.lora_refresh_coordinator = _RefreshCoordinator()


class _Submitter:
    """Provide a named submitter cleanup endpoint."""

    def close(self) -> None:
        """Provide the submitted-resource cleanup endpoint."""


class _ExecutionRuntime:
    """Record model-catalog submitter construction."""

    def __init__(self, submitter: _Submitter) -> None:
        """Initialize deterministic submitter capture."""

        self.submitter_value = submitter
        self.requests: list[tuple[str, str, object]] = []

    def submitter(self, name: str, *, owner_id: str, dispatcher: object) -> _Submitter:
        """Record and return the model-catalog submitter."""

        self.requests.append((name, owner_id, dispatcher))
        return self.submitter_value


class _ExecutionFactories:
    """Record prompt-task executor construction."""

    def __init__(self, executor: object) -> None:
        """Initialize deterministic executor capture."""

        self.executor = executor
        self.requests: list[tuple[object, str]] = []

    def prompt_task_executor_factory(self, owner: object, owner_id: str) -> object:
        """Record and return the local executor."""

        self.requests.append((owner, owner_id))
        return self.executor


class _ResourceLifecycle:
    """Record named shell cleanup registrations."""

    def __init__(self) -> None:
        """Initialize no resource registrations."""

        self.registrations: list[tuple[str, Callable[[], None]]] = []

    def register(self, name: str, cleanup: Callable[[], None]) -> None:
        """Record one cleanup callback."""

        self.registrations.append((name, cleanup))


class _Shell:
    """Hold editor-metadata composition inputs and observable outputs."""

    def __init__(self) -> None:
        """Create the minimum editor-metadata shell contract."""

        self.prompt_lora_catalog_service = object()
        self.editor_a = object()
        self.editor_b = object()
        self.editor_panels = {"a": self.editor_a, "b": self.editor_b}
        self.executor = object()
        self.editor_panel_execution_factories = _ExecutionFactories(self.executor)
        self.model_catalog_submitter = _Submitter()
        self.execution_runtime = _ExecutionRuntime(self.model_catalog_submitter)
        self.shell_resource_lifecycle = _ResourceLifecycle()
        self._lora_metadata_refresh_coordinator: object | None = None
        self.model_metadata_surface_refresh_controller: object | None = None


def test_compose_editor_metadata_controllers_assigns_metadata_refreshers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose both editor metadata refresh owners with distinct cleanup paths."""

    monkeypatch.setattr(
        main_window_composition,
        "PanelLoraMetadataRefreshController",
        _PanelLoraMetadataRefreshController,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ModelMetadataSurfaceRefreshController",
        _ModelMetadataSurfaceRefreshController,
    )
    dispatcher = object()
    monkeypatch.setattr(
        main_window_composition,
        "QtOwnerThreadDispatcher",
        lambda _parent: dispatcher,
    )
    shell = _Shell()

    composition = main_window_composition.compose_editor_metadata_controllers(shell)

    assert (
        composition.lora_metadata_refresh_coordinator
        is shell._lora_metadata_refresh_coordinator
    )
    assert (
        composition.model_metadata_surface_refresh_controller
        is shell.model_metadata_surface_refresh_controller
    )
    lora_controller = shell._lora_metadata_refresh_coordinator
    assert isinstance(lora_controller, _PanelLoraMetadataRefreshController)
    assert (
        lora_controller.kwargs["catalog_service"] is shell.prompt_lora_catalog_service
    )
    assert lora_controller.kwargs["parent"] is shell
    editor_panels = lora_controller.kwargs["editor_panels"]
    assert callable(editor_panels)
    assert editor_panels() == (shell.editor_a, shell.editor_b)
    assert lora_controller.kwargs["executor"] is shell.executor
    assert shell.editor_panel_execution_factories.requests == [
        (shell, f"panel-lora-metadata-refresh:{id(shell):x}")
    ]
    surface_controller = shell.model_metadata_surface_refresh_controller
    assert isinstance(surface_controller, _ModelMetadataSurfaceRefreshController)
    assert surface_controller.args == (shell,)
    assert surface_controller.kwargs["parent"] is shell
    assert surface_controller.kwargs["snapshot_refresh_submitter"] is (
        shell.model_catalog_submitter
    )
    cleanup_submitter = surface_controller.kwargs["close_snapshot_refresh_submitter"]
    assert getattr(cleanup_submitter, "__self__", None) is shell.model_catalog_submitter
    assert shell.execution_runtime.requests == [
        ("model_catalog", f"model_catalog_snapshot_refresh_{id(shell):x}", dispatcher)
    ]
    assert [
        name for name, _cleanup in shell.shell_resource_lifecycle.registrations
    ] == [
        "panel_lora_metadata_refresh",
        "model_catalog_snapshot_refresh",
    ]
