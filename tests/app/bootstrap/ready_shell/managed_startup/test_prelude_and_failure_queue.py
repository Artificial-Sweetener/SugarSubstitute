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

from collections.abc import Callable
from pathlib import Path

from substitute.app.bootstrap import (
    ready_shell_controller,
    startup_warmup_controller,
)
from substitute.app.bootstrap.startup_timing import StartupTimer

from ..support.shell_surfaces import _CloseSplash

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


def test_ready_shell_managed_startup_prelude_wires_cancel_and_splash() -> None:
    """Managed startup prelude should own cancel and splash wiring."""

    calls: list[str] = []
    connected_callbacks: list[Callable[[], None]] = []
    initial_cancel_callbacks: list[Callable[[], None]] = []
    splash = object()
    new_splash = object()

    def start_splash(**kwargs: object) -> object:
        """Record launch-splash inputs and return the new splash reference."""

        assert kwargs["splash"] is splash
        assert kwargs["on_cancel_requested"] is emit_splash_cancel
        calls.append("start_splash")
        return new_splash

    def connect_cancel(callback: Callable[[], None]) -> None:
        """Record the startup cancellation handler."""

        connected_callbacks.append(callback)
        calls.append("connect_cancel")

    def initial_connector(callback: Callable[[], None]) -> None:
        """Record the splash cancel callback exposed to an initial splash."""

        initial_cancel_callbacks.append(callback)
        calls.append("initial_connector")

    def request_startup_cancel() -> None:
        """Record forwarded startup cancellation."""

        calls.append("request_cancel")

    def emit_splash_cancel() -> None:
        """Record splash cancel bridge emission."""

        calls.append("emit_cancel")

    splashes: list[object | None] = []
    prelude = ready_shell_controller.ReadyShellManagedStartupPrelude(
        connect_cancel_request=connect_cancel,
        request_startup_cancel=request_startup_cancel,
        initial_splash_cancel_connector=initial_connector,
        emit_splash_cancel=emit_splash_cancel,
        splash=lambda: splash,
        set_splash=splashes.append,
        startup_timer=object(),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=start_splash,
    )

    prelude.run()
    connected_callbacks[0]()
    initial_cancel_callbacks[0]()

    assert calls == [
        "connect_cancel",
        "initial_connector",
        "start_splash",
        "request_cancel",
        "emit_cancel",
    ]
    assert splashes == [new_splash]


def test_create_ready_shell_managed_startup_prelude_returns_prelude() -> None:
    """Managed startup prelude construction should live in its owner."""

    prelude = ready_shell_controller.create_ready_shell_managed_startup_prelude(
        connect_cancel_request=lambda _callback: None,
        request_startup_cancel=lambda: None,
        initial_splash_cancel_connector=None,
        emit_splash_cancel=lambda: None,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        startup_timer=object(),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=lambda **_kwargs: object(),
    )

    assert isinstance(prelude, ready_shell_controller.ReadyShellManagedStartupPrelude)


def test_ready_shell_failure_queue_cancels_owned_queue_on_startup_cancel() -> None:
    """Ready-shell failure queue should bind fail-closed cleanup to queue cancel."""

    calls: list[str] = []
    scheduled: list[Callable[[], None]] = []
    cancelled = False

    def mark_cancelled() -> None:
        """Record startup cancellation."""

        nonlocal cancelled
        cancelled = True

    failure_queue = ready_shell_controller.ReadyShellFailureQueue(
        is_startup_cancelled=lambda: cancelled,
        mark_startup_cancelled=mark_cancelled,
        readiness_timers=lambda: (),
        runtime_compatibility_probes=lambda: (),
        managed_comfy_state=lambda: None,
        splash=lambda: _CloseSplash(calls),
        cleanup=lambda: calls.append("cleanup"),
        quit_app=lambda: calls.append("quit"),
        trace_fields=lambda: {"route": "ready"},
        managed_failure_report_factory=lambda _incident: object(),
        present_startup_failure_report=lambda _report: calls.append("present"),
        scheduler=lambda _delay_ms, callback: scheduled.append(callback),
        startup_timer=StartupTimer(),
    )

    failure_queue.add_task("later", lambda: calls.append("task"))
    failure_queue.request_startup_cancel()
    failure_queue.start_queue()

    assert cancelled is True
    assert scheduled == []
    assert calls == ["splash:close", "cleanup", "quit"]


def test_create_ready_shell_failure_queue_returns_failure_queue() -> None:
    """Ready-shell failure queue construction should live in its owner."""

    failure_queue = ready_shell_controller.create_ready_shell_failure_queue(
        is_startup_cancelled=lambda: False,
        mark_startup_cancelled=lambda: None,
        readiness_timers=lambda: (),
        runtime_compatibility_probes=lambda: (),
        managed_comfy_state=lambda: None,
        splash=lambda: None,
        cleanup=lambda: None,
        quit_app=lambda: None,
        trace_fields=lambda: {"route": "ready"},
        managed_failure_report_factory=lambda _incident: object(),
        present_startup_failure_report=lambda _report: None,
        scheduler=lambda _delay_ms, _callback: None,
        startup_timer=StartupTimer(),
    )

    assert isinstance(failure_queue, ready_shell_controller.ReadyShellFailureQueue)


def test_ready_shell_local_editor_warmup_adapter_uses_live_startup_state() -> None:
    """Local editor warmup adapter should own shell-build warmup port assembly."""

    calls: list[str] = []
    state = startup_warmup_controller.StartupWarmupState()
    shell_frame = object()
    main_window = object()
    registry = object()

    def start_local_editor_warmup(**kwargs: object) -> object:
        """Record local editor warmup inputs."""

        assert kwargs["state"] is state
        assert kwargs["startup_cancelled"] is False
        assert kwargs["shell_frame"] is shell_frame
        assert kwargs["main_window_for_shell"] is main_window_for_shell
        assert kwargs["registry"] is registry
        calls.append("local_editor_warmup")
        return "started"

    def main_window_for_shell(received: object) -> object:
        """Return a main window for the built shell frame."""

        assert received is shell_frame
        return main_window

    adapter = ready_shell_controller.ReadyShellLocalEditorWarmupAdapter(
        state=state,
        startup_cancelled=lambda: False,
        main_window_for_shell=main_window_for_shell,
        registry=registry,
        trace_fields=lambda: {"route": "ready"},
        start_local_editor_warmup=start_local_editor_warmup,
    )

    result = adapter.start(shell_frame)

    assert result == "started"
    assert calls == ["local_editor_warmup"]


def test_create_ready_shell_local_editor_warmup_adapter_returns_adapter() -> None:
    """Local editor warmup adapter construction should live in its owner."""

    adapter = ready_shell_controller.create_ready_shell_local_editor_warmup_adapter(
        state=startup_warmup_controller.StartupWarmupState(),
        startup_cancelled=lambda: False,
        main_window_for_shell=lambda _frame: object(),
        registry=object(),
        trace_fields=lambda: {"route": "ready"},
        start_local_editor_warmup=lambda **_kwargs: None,
    )

    assert isinstance(
        adapter,
        ready_shell_controller.ReadyShellLocalEditorWarmupAdapter,
    )
