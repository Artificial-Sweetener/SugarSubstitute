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

"""Verify UI ownership transitions for direct workflows."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces
from substitute.presentation.shell.workflow_ui_factory import WorkflowUiFactory
from tests.presentation.shell.workflow_ui.support import (
    FakeCubeStack,
    FakeEditorPanel,
    FakeOverrideManager,
    build_workflow_shell,
    install_signal_binder,
)


def _direct_workflow() -> WorkflowState:
    """Build a real direct Comfy document with one ordinary node."""

    return WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("direct.json"),
            source_workflow={
                "version": 0.4,
                "nodes": [{"id": "ordinary", "type": "VendorNode"}],
                "links": [],
                "definitions": {"subgraphs": []},
            },
            buffer={"nodes": {}},
        )
    )


def test_direct_workflow_creates_editor_without_phantom_cube_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create an editor surface without a cube-stack widget."""
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        lambda **kwargs: FakeEditorPanel(**kwargs),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.GlobalOverridesManager",
        lambda shell, **kwargs: FakeOverrideManager(shell, **kwargs),
    )
    shell = build_workflow_shell()
    shell.workflow_session_service.workflows["wf-1"] = _direct_workflow()
    install_signal_binder(monkeypatch, shell)

    surfaces = WorkflowUiFactory(shell).create_workflow_ui("wf-1")

    assert isinstance(surfaces, WorkflowUiSurfaces)
    assert surfaces.editor_panel is shell.editor_panels["wf-1"]
    assert surfaces.cube_stack is None
    assert shell.cube_stacks == {}
    assert shell.cube_stack is None


def test_blank_cube_surface_is_disposed_when_document_becomes_direct() -> None:
    """Remove the initial blank cube stack after loading a direct document."""
    shell = build_workflow_shell()
    stack = FakeCubeStack(shell)
    shell.cube_stacks["wf-1"] = stack
    shell.cube_stack_container.addWidget(stack)
    shell.cube_stack_container.setCurrentWidget(stack)
    shell.cube_stack = stack
    shell.workflow_session_service.workflows["wf-1"] = _direct_workflow()

    result = WorkflowUiFactory(shell).reconcile_cube_stack_surface(
        "wf-1",
        set_as_current=True,
    )

    assert result is None
    assert shell.cube_stacks == {}
    assert shell.cube_stack is None
    assert shell.cube_stack_container.added == []
    assert stack.deleted
