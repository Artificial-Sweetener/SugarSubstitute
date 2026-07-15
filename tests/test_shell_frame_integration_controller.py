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

"""Tests for shell frame integration controller attachments."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)
from substitute.presentation.shell.shell_frame_integration_controller import (
    ShellFrameIntegrationController,
)
from substitute.presentation.shell.taskbar_progress import (
    TaskbarProgressPresenter,
)
from substitute.presentation.shell.titlebar_buttons import (
    StartupDiagnosticsTitleBarButton,
)
import substitute.presentation.shell.shell_frame_integration_controller as controller_module


class _TaskbarPresenter:
    """Record taskbar presenter calls."""

    def __init__(self) -> None:
        """Create an empty taskbar call recorder."""

        self.calls: list[tuple[str, int | None]] = []

    def set_progress(self, value: int) -> None:
        """Record one progress value."""

        self.calls.append(("set", value))

    def clear_progress(self) -> None:
        """Record one clear request."""

        self.calls.append(("clear", None))


class _FakeStartupDiagnosticsTitlebarController:
    """Capture startup diagnostics titlebar construction and state."""

    instances: list["_FakeStartupDiagnosticsTitlebarController"] = []

    def __init__(
        self,
        *,
        button: object,
        parent: object,
        ignore_repository: object,
    ) -> None:
        """Record construction arguments."""

        self.button = button
        self.parent = parent
        self.ignore_repository = ignore_repository
        self.states: list[StartupDiagnosticsTitlebarState | None] = []
        self.instances.append(self)

    def set_state(self, state: StartupDiagnosticsTitlebarState | None) -> None:
        """Record one diagnostics state projection."""

        self.states.append(state)


class _Signal:
    """Record signal disconnect calls for generation mode wiring."""

    def __init__(self) -> None:
        """Create an empty signal recorder."""

        self.disconnected: list[object] = []

    def disconnect(self, callback: object) -> None:
        """Record one callback disconnection."""

        self.disconnected.append(callback)


class _Registry:
    """Record generation titlebar registry attachments."""

    def __init__(self) -> None:
        """Create an empty registry recorder."""

        self.registered: list[object] = []

    def register(self, target: object) -> None:
        """Record one registered titlebar control."""

        self.registered.append(target)


def test_constructor_installs_default_taskbar_presenter() -> None:
    """Frame integration should install a no-op taskbar presenter by default."""

    shell = SimpleNamespace()

    ShellFrameIntegrationController(shell)

    shell._taskbar_progress_presenter.clear_progress()


def test_set_taskbar_progress_presenter_updates_shell_presenter() -> None:
    """Taskbar presenter injection should update the shell progress surface."""

    shell = SimpleNamespace()
    controller = ShellFrameIntegrationController(shell)
    presenter = _TaskbarPresenter()

    controller.set_taskbar_progress_presenter(cast(TaskbarProgressPresenter, presenter))
    shell._taskbar_progress_presenter.set_progress(42)

    assert presenter.calls == [("set", 42)]


def test_startup_diagnostics_state_replays_after_titlebar_attach(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending diagnostics state should apply when the frame button arrives later."""

    _FakeStartupDiagnosticsTitlebarController.instances = []
    monkeypatch.setattr(
        controller_module,
        "StartupDiagnosticsTitlebarController",
        _FakeStartupDiagnosticsTitlebarController,
    )
    shell = SimpleNamespace()
    controller = ShellFrameIntegrationController(shell)
    state = StartupDiagnosticsTitlebarState(
        incidents=(),
        ignored_count=0,
        transcript=("ready",),
    )
    button = cast(StartupDiagnosticsTitleBarButton, object())
    repository = cast(StartupDiagnosticsIgnoreRepository, object())

    controller.set_startup_diagnostics_state(state)
    controller.attach_startup_diagnostics_titlebar(button, repository)

    created = _FakeStartupDiagnosticsTitlebarController.instances
    assert len(created) == 1
    assert created[0].button is button
    assert created[0].parent is shell
    assert created[0].ignore_repository is repository
    assert created[0].states == [state]


def test_generation_titlebar_registry_replaces_cluster_mode_callback() -> None:
    """Generation titlebar registry should own cluster registration and callback cleanup."""

    callback = object()
    signal = _Signal()
    cluster = SimpleNamespace(generateModeSelected=signal)
    titlebar_registries: list[object] = []
    shell = SimpleNamespace(
        generationActionCluster=cluster,
        _generation_action_cluster_mode_callback=callback,
        output_floating_chrome_factory=SimpleNamespace(
            set_titlebar_control_registry=titlebar_registries.append
        ),
    )
    controller = ShellFrameIntegrationController(shell)
    registry = _Registry()

    controller.set_generation_titlebar_control_registry(
        cast(GenerationTitleBarControlRegistry, registry)
    )

    assert shell.generation_titlebar_control_registry is registry
    assert shell._generation_action_cluster_mode_callback is None
    assert signal.disconnected == [callback]
    assert registry.registered == [cluster]
    assert titlebar_registries == [registry]


def test_attach_app_orb_menu_delegates_to_signal_binder() -> None:
    """App orb attachment should stay behind the signal-binder owner."""

    menu = object()
    calls: list[object] = []
    shell = SimpleNamespace(
        main_window_signal_binder=SimpleNamespace(
            attach_app_orb_menu=lambda app_orb_menu: calls.append(app_orb_menu)
        )
    )
    controller = ShellFrameIntegrationController(shell)

    controller.attach_app_orb_menu(menu)

    assert calls == [menu]


def test_reopen_closed_workflow_enablement_projects_to_workflow_tabbar() -> None:
    """Closed-workflow availability should be projected to the tab-bar surface."""

    states: list[bool] = []
    shell = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            set_reopen_closed_workflow_enabled=lambda enabled: states.append(enabled)
        )
    )
    controller = ShellFrameIntegrationController(shell)

    controller.set_reopen_closed_workflow_enabled(True)
    controller.set_reopen_closed_workflow_enabled(False)

    assert states == [True, False]


def test_reopen_closed_workflow_enablement_tolerates_missing_tabbar_api() -> None:
    """Closed-workflow projection should tolerate lightweight tabbar doubles."""

    shell = SimpleNamespace(workflow_tabbar=SimpleNamespace())
    controller = ShellFrameIntegrationController(shell)

    controller.set_reopen_closed_workflow_enabled(True)
