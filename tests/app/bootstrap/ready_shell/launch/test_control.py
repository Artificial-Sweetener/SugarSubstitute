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

"""Tests for ready-shell startup task orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path
from typing import cast


from substitute.app.bootstrap import (
    ready_shell_controller,
)
from substitute.domain.onboarding import InstallationContext

from ..support.shell_surfaces import _Splash

PROJECT_ROOT = Path(__file__).resolve().parents[5]
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_ready_shell_launch_controller_launches_no_comfy_shell() -> None:
    """Ready-shell launch controller should own the no-Comfy route branch."""

    calls: list[str] = []
    context = cast(InstallationContext, _LaunchContext())
    splash = _Splash(calls)
    shell_frame = object()
    current_shells: list[object] = []
    splashes: list[object | None] = []

    def show_main_window(received_context: object, **kwargs: object) -> object:
        """Record the no-Comfy shell show call."""

        assert received_context is context
        assert kwargs["initial_shell_placement"] == "placement"
        assert kwargs["initial_workspace"] == "workspace"
        calls.append("show")
        return shell_frame

    controller = ready_shell_controller.ReadyShellLaunchController(
        no_comfy=True,
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: False,
        splash=lambda: splash,
        set_splash=splashes.append,
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement="placement",
        initial_workspace="workspace",
        show_main_window=show_main_window,
        attach_gui_reload_command=lambda frame: calls.append(
            "attach_reload" if frame is shell_frame else "attach_wrong"
        ),
        set_current_shell=current_shells.append,
        launch_managed_ready_shell=lambda _context: calls.append("managed"),
    )

    controller.launch(context)

    assert calls == ["splash_close", "show", "attach_reload"]
    assert current_shells == [shell_frame]
    assert splashes == [None]


def test_ready_shell_launch_controller_launches_managed_shell_once() -> None:
    """Ready-shell launch controller should route managed startup behind a callback."""

    calls: list[str] = []
    context = cast(InstallationContext, _LaunchContext())

    controller = ready_shell_controller.ReadyShellLaunchController(
        no_comfy=False,
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: False,
        splash=lambda: _Splash(calls),
        set_splash=lambda _splash: calls.append("set_splash"),
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda *_args, **_kwargs: calls.append("show"),
        attach_gui_reload_command=lambda _frame: calls.append("attach"),
        set_current_shell=lambda _frame: calls.append("current"),
        launch_managed_ready_shell=lambda received: calls.append(
            "managed" if received is context else "managed_wrong"
        ),
    )

    controller.launch(context)
    controller.launch(context)

    assert calls == ["managed"]


def test_ready_shell_launch_controller_skips_when_gate_blocks() -> None:
    """Ready-shell launch controller should respect duplicate/cancel gate state."""

    calls: list[str] = []

    controller = ready_shell_controller.ReadyShellLaunchController(
        no_comfy=False,
        startup_cancelled=lambda: True,
        shell_frame_present=lambda: False,
        splash=lambda: _Splash(calls),
        set_splash=lambda _splash: calls.append("set_splash"),
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda *_args, **_kwargs: calls.append("show"),
        attach_gui_reload_command=lambda _frame: calls.append("attach"),
        set_current_shell=lambda _frame: calls.append("current"),
        launch_managed_ready_shell=lambda _context: calls.append("managed"),
    )

    controller.launch(cast(InstallationContext, _LaunchContext()))

    assert calls == []


def test_create_ready_shell_launch_controller_returns_controller() -> None:
    """Ready-shell launch controller factory should construct the controller."""

    controller = ready_shell_controller.create_ready_shell_launch_controller(
        no_comfy=False,
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: False,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda *_args, **_kwargs: object(),
        attach_gui_reload_command=lambda _frame: None,
        set_current_shell=lambda _frame: None,
        launch_managed_ready_shell=lambda _context: None,
    )

    assert isinstance(controller, ready_shell_controller.ReadyShellLaunchController)


@dataclass(frozen=True)
class _LaunchEndpoint:
    """Minimal endpoint shape for ready-shell launch tests."""

    host: str = "127.0.0.1"
    port: int = 8188


@dataclass(frozen=True)
class _LaunchTarget:
    """Minimal target shape for ready-shell launch tests."""

    mode: str = "managed"
    endpoint: _LaunchEndpoint = _LaunchEndpoint()


@dataclass(frozen=True)
class _LaunchContext:
    """Minimal installation-context shape for ready-shell launch tests."""

    comfy_target: _LaunchTarget = _LaunchTarget()
