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

"""Cover workflow UI creation outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces
from substitute.presentation.shell.workflow_ui_factory import WorkflowUiFactory
from substitute.presentation.workflows.cube_stack_view import CubeCloseButtonDisplayMode


def test_create_editor_panel_passes_shell_dependencies_and_wires_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editor-panel creation should preserve dependencies and shell wiring."""

    created_panels: list[_FakeEditorPanel] = []

    def editor_panel_factory(**kwargs: object) -> _FakeEditorPanel:
        """Create one fake editor panel and record constructor kwargs."""

        panel = _FakeEditorPanel(**kwargs)
        created_panels.append(panel)
        return panel

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        editor_panel_factory,
    )
    shell = _workflow_shell()
    _install_signal_binder_stub(monkeypatch, shell)

    panel = WorkflowUiFactory(shell).create_editor_panel("wf-1")

    fake_panel = cast("_FakeEditorPanel", panel)
    assert fake_panel is created_panels[0]
    assert fake_panel.kwargs["workflow_id"] == "wf-1"
    assert fake_panel.kwargs["node_definition_gateway"] is shell.node_definition_gateway
    assert (
        fake_panel.kwargs["node_presentation_service"]
        is shell.node_presentation_service
    )
    assert fake_panel.kwargs["wheel_adjustment_mode"] == "precise"
    assert fake_panel.kwargs["error_presenter"] is shell._error_presenter
    assert (
        fake_panel.kwargs["editor_panel_execution_factories"]
        is shell.editor_panel_execution_factories
    )
    assert fake_panel.mainwindow is shell
    assert fake_panel.minimum_widths == [412]
    assert shell.connected_editor_panels == [fake_panel]


def test_create_cube_stack_configures_stack_and_shell_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube-stack creation should preserve tab policy and shell signal wiring."""

    created_stacks: list[_FakeCubeStack] = []

    def cube_stack_factory(parent: object) -> _FakeCubeStack:
        """Create one fake cube stack and record its parent."""

        stack = _FakeCubeStack(parent)
        created_stacks.append(stack)
        return stack

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.CubeStack",
        cube_stack_factory,
    )
    shell = _workflow_shell()
    _install_signal_binder_stub(monkeypatch, shell)

    factory = WorkflowUiFactory(shell)
    stack = factory.create_cube_stack("wf-1")

    fake_stack = cast("_FakeCubeStack", stack)
    assert fake_stack is created_stacks[0]
    assert fake_stack.parent is shell
    assert fake_stack.movable_calls == [True]
    assert fake_stack.maximum_width_calls == [220]
    assert fake_stack.close_button_modes == [CubeCloseButtonDisplayMode.ON_HOVER]
    assert fake_stack.cubeMoved.connections == [factory.handle_cube_moved]
    assert fake_stack.currentCubeChanged.connections == [factory.handle_cube_changed]
    assert shell.connected_cube_stacks == [fake_stack]
    assert shell.layout_applied_stacks == [fake_stack]


def test_cube_stack_signal_handlers_are_intentional_noops() -> None:
    """Cube-stack interim tab signals should remain side-effect free."""

    shell = _workflow_shell()
    factory = WorkflowUiFactory(shell)

    factory.handle_cube_changed(2)
    factory.handle_cube_moved(1, 3)

    assert shell.connected_cube_stacks == []
    assert shell.layout_applied_stacks == []


def test_create_workflow_ui_registers_widgets_and_current_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow UI creation should register and optionally select new widgets."""

    created_managers: list[_FakeOverrideManager] = []

    def editor_panel_factory(**kwargs: object) -> _FakeEditorPanel:
        """Create one fake editor panel."""

        return _FakeEditorPanel(**kwargs)

    def cube_stack_factory(parent: object) -> _FakeCubeStack:
        """Create one fake cube stack."""

        return _FakeCubeStack(parent)

    def override_manager_factory(
        shell: object, **kwargs: object
    ) -> _FakeOverrideManager:
        """Create one fake override manager and record constructor kwargs."""

        manager = _FakeOverrideManager(shell, **kwargs)
        created_managers.append(manager)
        return manager

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        editor_panel_factory,
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.CubeStack",
        cube_stack_factory,
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.GlobalOverridesManager",
        override_manager_factory,
    )
    shell = _workflow_shell()
    _install_signal_binder_stub(monkeypatch, shell)

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
    """Workflow UI creation should support background workflow materialization."""

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        lambda **kwargs: _FakeEditorPanel(**kwargs),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.CubeStack",
        lambda parent: _FakeCubeStack(parent),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.GlobalOverridesManager",
        lambda shell, **kwargs: _FakeOverrideManager(shell, **kwargs),
    )
    shell = _workflow_shell()
    _install_signal_binder_stub(monkeypatch, shell)

    surfaces = WorkflowUiFactory(shell).create_workflow_ui(
        "wf-1",
        set_as_current=False,
    )
    cube_stack = surfaces.cube_stack
    editor_panel = surfaces.editor_panel

    assert shell.editor_panels == {"wf-1": editor_panel}
    assert shell.cube_stacks == {"wf-1": cube_stack}
    assert shell.editor_panel_container.current is None
    assert shell.cube_stack_container.current is None
    assert not hasattr(shell, "editor_panel")
    assert not hasattr(shell, "cube_stack")


class _FakeEditorPanel:
    """Record editor-panel construction and configuration."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor kwargs and default controller attributes."""

        self.kwargs = kwargs
        self.model_choice_snapshot_controller = object()
        self.minimum_widths: list[int] = []
        self.mainwindow: object | None = None

    def setMinimumWidth(self, width: int) -> None:
        """Record the configured minimum width."""

        self.minimum_widths.append(width)


class _FakeCubeStack:
    """Record cube-stack construction and configuration."""

    def __init__(self, parent: object) -> None:
        """Store parent and create fake Qt signals."""

        self.parent = parent
        self.cubeMoved = _Signal()
        self.currentCubeChanged = _Signal()
        self.movable_calls: list[bool] = []
        self.maximum_width_calls: list[int] = []
        self.close_button_modes: list[object] = []
        self.deleted = False

    def setMovable(self, movable: bool) -> None:
        """Record movable configuration."""

        self.movable_calls.append(movable)

    def setTabMaximumWidth(self, width: int) -> None:
        """Record tab maximum width configuration."""

        self.maximum_width_calls.append(width)

    def setCloseButtonDisplayMode(self, mode: object) -> None:
        """Record close-button visibility mode."""

        self.close_button_modes.append(mode)

    def deleteLater(self) -> None:
        """Record deferred widget disposal."""

        self.deleted = True


class _FakeOverrideManager:
    """Record override-manager construction and injected UI handles."""

    def __init__(self, shell: object, **kwargs: object) -> None:
        """Store constructor inputs."""

        self.shell = shell
        self.kwargs = kwargs
        self.override_dropdown_btn: object | None = None
        self._global_override_menu: object | None = None


class _Signal:
    """Record connected slots."""

    def __init__(self) -> None:
        """Initialize empty connection storage."""

        self.connections: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected slot."""

        self.connections.append(slot)


class _Container:
    """Record stacked-widget additions and current selection."""

    def __init__(self) -> None:
        """Initialize empty widget state."""

        self.added: list[object] = []
        self.current: object | None = None

    def addWidget(self, widget: object) -> None:
        """Record one widget addition."""

        self.added.append(widget)

    def setCurrentWidget(self, widget: object) -> None:
        """Record current widget selection."""

        self.current = widget

    def removeWidget(self, widget: object) -> None:
        """Record removal from this stacked container."""

        self.added.remove(widget)
        if self.current is widget:
            self.current = None


def _workflow_shell() -> SimpleNamespace:
    """Build a shell fake with workflow UI dependencies."""

    connected_editor_panels: list[object] = []
    connected_cube_stacks: list[object] = []
    layout_applied_stacks: list[object] = []
    values: dict[str, Any] = {
        "node_definition_gateway": object(),
        "node_presentation_service": object(),
        "prompt_autocomplete_gateway": object(),
        "prompt_wildcard_catalog_gateway": object(),
        "danbooru_url_import_service": object(),
        "danbooru_wiki_service": object(),
        "danbooru_image_preview_service": object(),
        "danbooru_recent_posts_service": object(),
        "prompt_lora_catalog_service": object(),
        "scheduled_lora_provider": object(),
        "prompt_scheduled_lora_service": object(),
        "prompt_spellcheck_service": object(),
        "prompt_feature_profile_service": object(),
        "prompt_editor_preference_service": SimpleNamespace(
            load_preferences=lambda: SimpleNamespace(wheel_adjustment_mode="precise")
        ),
        "model_catalog_service": object(),
        "model_choice_resolver": object(),
        "thumbnail_asset_repository": object(),
        "model_metadata_context_action_handler": object(),
        "node_behavior_service": object(),
        "user_preset_service": object(),
        "_error_presenter": object(),
        "workflow_issue_state": object(),
        "editor_panel_execution_factories": object(),
        "pinned_override_service": object(),
        "override_dropdown_btn": object(),
        "_global_override_menu": object(),
        "editor_panels": {},
        "cube_stacks": {},
        "override_managers": {},
        "editor_panel_container": _Container(),
        "cube_stack_container": _Container(),
        "connected_editor_panels": connected_editor_panels,
        "connected_cube_stacks": connected_cube_stacks,
        "layout_applied_stacks": layout_applied_stacks,
        "workflow_session_service": SimpleNamespace(
            workflows={"wf-1": WorkflowState()}
        ),
        "cube_stack_presentation_controller": SimpleNamespace(
            prepare_stack=layout_applied_stacks.append
        ),
    }
    return SimpleNamespace(**values)


def test_direct_workflow_creates_editor_without_phantom_cube_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct documents should own an editor surface and no cube-stack widget."""

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.EditorPanel",
        lambda **kwargs: _FakeEditorPanel(**kwargs),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.GlobalOverridesManager",
        lambda shell, **kwargs: _FakeOverrideManager(shell, **kwargs),
    )
    shell = _workflow_shell()
    direct = WorkflowState()
    direct.direct_workflow = cast(Any, object())
    shell.workflow_session_service.workflows["wf-1"] = direct
    _install_signal_binder_stub(monkeypatch, shell)

    surfaces = WorkflowUiFactory(shell).create_workflow_ui("wf-1")

    assert isinstance(surfaces, WorkflowUiSurfaces)
    assert surfaces.editor_panel is shell.editor_panels["wf-1"]
    assert surfaces.cube_stack is None
    assert shell.cube_stacks == {}
    assert shell.cube_stack is None


def test_blank_cube_surface_is_disposed_when_document_becomes_direct() -> None:
    """Loading direct JSON into the initial blank tab should remove its old stack."""

    shell = _workflow_shell()
    stack = _FakeCubeStack(shell)
    shell.cube_stacks["wf-1"] = stack
    shell.cube_stack_container.addWidget(stack)
    shell.cube_stack_container.setCurrentWidget(stack)
    shell.cube_stack = stack
    direct = WorkflowState()
    direct.direct_workflow = cast(Any, object())
    shell.workflow_session_service.workflows["wf-1"] = direct

    result = WorkflowUiFactory(shell).reconcile_cube_stack_surface(
        "wf-1",
        set_as_current=True,
    )

    assert result is None
    assert shell.cube_stacks == {}
    assert shell.cube_stack is None
    assert shell.cube_stack_container.added == []
    assert stack.deleted


def _install_signal_binder_stub(
    monkeypatch: pytest.MonkeyPatch,
    shell: SimpleNamespace,
) -> None:
    """Route workflow factory signal binding through the composed binder port."""

    binder = SimpleNamespace(
        connect_editor_panel_signals=shell.connected_editor_panels.append,
        connect_cube_stack_signals=shell.connected_cube_stacks.append,
    )

    def binder_for(candidate: object) -> SimpleNamespace:
        """Return the test binder for the expected shell."""

        assert candidate is shell
        return binder

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.main_window_signal_binder_for",
        binder_for,
    )
