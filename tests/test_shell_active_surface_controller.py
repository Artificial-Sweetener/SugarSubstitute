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

"""Tests for shell active workflow and surface lookup."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from substitute.presentation.shell.shell_active_surface_controller import (
    ShellActiveSurfaceController,
)
import substitute.presentation.shell.shell_active_surface_controller as controller_module


class _Container:
    """Return one current widget from a Qt-like stacked container."""

    def __init__(self, widget: object) -> None:
        """Store the current widget returned by the container."""

        self._widget = widget

    def currentWidget(self) -> object:  # noqa: N802
        """Return the configured current widget."""

        return self._widget


class _EditorPanel:
    """Editor panel test marker."""


class _CubeStack:
    """Cube stack test marker."""


def test_get_active_workflow_returns_session_active_workflow() -> None:
    """Active workflow lookup should delegate to workflow session service."""

    workflow = object()
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(get_active_workflow=lambda: workflow)
    )
    controller = ShellActiveSurfaceController(shell)

    assert controller.get_active_workflow() is workflow


def test_active_editor_panel_requires_editor_panel_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editor lookup should ignore non-editor current widgets."""

    monkeypatch.setattr(controller_module, "EditorPanel", _EditorPanel)
    editor = _EditorPanel()
    controller = ShellActiveSurfaceController(
        SimpleNamespace(editor_panel_container=_Container(editor))
    )
    wrong_controller = ShellActiveSurfaceController(
        SimpleNamespace(editor_panel_container=_Container(object()))
    )
    missing_controller = ShellActiveSurfaceController(SimpleNamespace())

    active_editor = cast(object | None, controller.active_editor_panel())
    assert active_editor is editor
    assert wrong_controller.active_editor_panel() is None
    assert missing_controller.active_editor_panel() is None


def test_active_cube_stack_requires_cube_stack_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube-stack lookup should ignore non-stack current widgets."""

    monkeypatch.setattr(controller_module, "CubeStack", _CubeStack)
    stack = _CubeStack()
    controller = ShellActiveSurfaceController(
        SimpleNamespace(cube_stack_container=_Container(stack))
    )
    wrong_controller = ShellActiveSurfaceController(
        SimpleNamespace(cube_stack_container=_Container(object()))
    )
    missing_controller = ShellActiveSurfaceController(SimpleNamespace())

    active_stack = cast(object | None, controller.active_cube_stack())
    assert active_stack is stack
    assert wrong_controller.active_cube_stack() is None
    assert missing_controller.active_cube_stack() is None


def test_active_override_manager_uses_active_workflow_id() -> None:
    """Override-manager lookup should use the active workflow route."""

    manager = object()
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        override_managers={"wf-a": manager, "wf-b": object()},
    )
    controller = ShellActiveSurfaceController(shell)
    missing_controller = ShellActiveSurfaceController(
        SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="wf-a")
        )
    )

    assert controller.active_override_manager() is manager
    assert missing_controller.active_override_manager() is None
