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

"""Verify workflow UI registration and selection."""

from __future__ import annotations

import pytest

from substitute.presentation.shell.workflow_ui_factory import WorkflowUiFactory
from tests.presentation.shell.workflow_ui.support import (
    FakeCubeStack,
    FakeEditorPanel,
    FakeOverrideManager,
    build_workflow_shell,
    install_signal_binder,
)


def test_create_workflow_ui_registers_widgets_and_current_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Register and select a new workflow's widgets."""
    created_managers: list[FakeOverrideManager] = []

    def override_manager_factory(
        shell: object,
        **kwargs: object,
    ) -> FakeOverrideManager:
        """Create and record one override manager."""
        manager = FakeOverrideManager(shell, **kwargs)
        created_managers.append(manager)
        return manager

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        lambda **kwargs: FakeEditorPanel(**kwargs),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.CubeStack",
        lambda parent: FakeCubeStack(parent),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.GlobalOverridesManager",
        override_manager_factory,
    )
    shell = build_workflow_shell()
    install_signal_binder(monkeypatch, shell)

    surfaces = WorkflowUiFactory(shell).create_workflow_ui("wf-1")
    cube_stack = surfaces.cube_stack
    editor_panel = surfaces.editor_panel

    assert shell.editor_panels == {"wf-1": editor_panel}
    assert shell.cube_stacks == {"wf-1": cube_stack}
    assert shell.override_managers == {"wf-1": created_managers[0]}
    assert shell.editor_panel_container.added == [editor_panel]
    assert shell.cube_stack_container.added == [cube_stack]
    assert shell.editor_panel_container.current is editor_panel
    assert shell.cube_stack_container.current is cube_stack
    assert shell.editor_panel is editor_panel
    assert shell.cube_stack is cube_stack
    assert created_managers[0].kwargs["model_choice_snapshot_controller"] is (
        editor_panel.model_choice_snapshot_controller
    )
    assert created_managers[0].override_dropdown_btn is shell.override_dropdown_btn
    assert created_managers[0]._global_override_menu is shell._global_override_menu


def test_create_workflow_ui_can_register_without_selecting_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Support background workflow materialization without selection."""
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        lambda **kwargs: FakeEditorPanel(**kwargs),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.CubeStack",
        lambda parent: FakeCubeStack(parent),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.GlobalOverridesManager",
        lambda shell, **kwargs: FakeOverrideManager(shell, **kwargs),
    )
    shell = build_workflow_shell()
    install_signal_binder(monkeypatch, shell)

    surfaces = WorkflowUiFactory(shell).create_workflow_ui(
        "wf-1",
        set_as_current=False,
    )

    assert shell.editor_panels == {"wf-1": surfaces.editor_panel}
    assert shell.cube_stacks == {"wf-1": surfaces.cube_stack}
    assert shell.editor_panel_container.current is None
    assert shell.cube_stack_container.current is None
    assert not hasattr(shell, "editor_panel")
    assert not hasattr(shell, "cube_stack")
