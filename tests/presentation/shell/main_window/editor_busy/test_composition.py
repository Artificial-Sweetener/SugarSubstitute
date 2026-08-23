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

"""Verify MainWindow composes editor-busy coordination at the shell boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pytest

from substitute.presentation.shell import main_window_composition


class _Signal:
    """Record one signal's connected slots."""

    def __init__(self) -> None:
        """Initialize the empty connection list."""

        self.connected: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one signal connection."""

        self.connected.append(slot)


class _EditorBusyCoordinator:
    """Capture editor-busy collaborators and its cancellation endpoint."""

    def __init__(self, **kwargs: object) -> None:
        """Store composition arguments."""

        self.kwargs = kwargs
        self.request_active_cancel = object()

    def shutdown(self) -> None:
        """Provide the registered cleanup endpoint."""


class _ResourceLifecycle:
    """Record named resource cleanup registrations."""

    def __init__(self) -> None:
        """Initialize no registrations."""

        self.registrations: list[tuple[str, Callable[[], None]]] = []

    def register(self, name: str, cleanup: Callable[[], None]) -> None:
        """Record one cleanup callback."""

        self.registrations.append((name, cleanup))


@dataclass
class _WorkflowSession:
    """Expose the active workflow identity."""

    active_workflow_id: str


@dataclass
class _BusyOverlay:
    """Expose the busy-overlay cancellation signal."""

    cancel_requested: _Signal = field(default_factory=_Signal)


@dataclass
class _Shell:
    """Hold shell state consumed and assigned by busy composition."""

    workflow_session_service: _WorkflowSession
    editorBusyOverlay: _BusyOverlay
    shell_resource_lifecycle: _ResourceLifecycle
    _active_workspace_route: str
    editor_busy: object | None = None


def test_compose_editor_busy_controller_assigns_busy_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connect editor-busy cancellation and resource lifecycle to the shell."""

    monkeypatch.setattr(
        main_window_composition,
        "EditorBusyCoordinator",
        _EditorBusyCoordinator,
    )
    shell = _Shell(
        workflow_session_service=_WorkflowSession(active_workflow_id="wf-b"),
        editorBusyOverlay=_BusyOverlay(),
        shell_resource_lifecycle=_ResourceLifecycle(),
        _active_workspace_route="wf-b",
    )

    composition = main_window_composition.compose_editor_busy_controller(shell)

    assert composition.editor_busy is shell.editor_busy
    coordinator = shell.editor_busy
    assert isinstance(coordinator, _EditorBusyCoordinator)
    assert coordinator.kwargs["overlay"] is shell.editorBusyOverlay
    active_workflow_id = coordinator.kwargs["active_workflow_id"]
    assert callable(active_workflow_id)
    assert active_workflow_id() == "wf-b"
    is_editor_surface_active = coordinator.kwargs["is_editor_surface_active"]
    assert callable(is_editor_surface_active)
    assert is_editor_surface_active() is True
    shell._active_workspace_route = "settings"
    assert is_editor_surface_active() is False
    assert shell.shell_resource_lifecycle.registrations == [
        ("editor_busy", coordinator.shutdown)
    ]
    assert shell.editorBusyOverlay.cancel_requested.connected == [
        coordinator.request_active_cancel
    ]
