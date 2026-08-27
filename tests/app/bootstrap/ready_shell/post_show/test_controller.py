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

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from substitute.app.bootstrap import (
    ready_shell_controller,
    ready_shell_reveal,
    ready_shell_restore_controller,
    startup_warmup_controller,
)
from substitute.app.bootstrap.startup_timing import StartupTimer

from ..support.backend_state import _BackendStateMainWindow
from ..support.restore_signals import _Signal
from ..support.timing import _Timer, _marked_timer
from ..support.trace import _patch_trace

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


def test_connect_ready_shell_restore_finalized_warmups_delegates_wiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell restore-finalized helper should delegate warmup wiring."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    state = startup_warmup_controller.StartupWarmupState()
    signal = _Signal()
    scheduled_reasons: list[str] = []

    ready_shell_reveal.connect_ready_shell_restore_finalized_warmups(
        state=state,
        main_window=_RestoreFinalizedMainWindow(signal),
        schedule_warmups=scheduled_reasons.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert state.restore_finalized_warmups_connected is True
    assert signal.callbacks == [state.restore_finalized_warmups_callback]
    callback = cast(Callable[[], None], signal.callbacks[0])
    callback()
    assert scheduled_reasons == ["restore_finalized"]
    assert events == [
        (
            "post_comfy.nonessential_warmups.wait_restore_finalized",
            {"route": "ready"},
        ),
        (
            "post_comfy.nonessential_warmups.restore_finalized",
            {"route": "ready"},
        ),
    ]


def test_schedule_ready_shell_post_show_hydration_delegates_queueing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell post-show scheduling should delegate queue policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    scheduled = ready_shell_controller.schedule_ready_shell_post_show_hydration(
        startup_cancelled=False,
        hydration_started=False,
        mark_hydration_started=lambda: calls.append("mark_started"),
        queue_hydration_task=lambda: calls.append("queue_hydration"),
        start_queue=lambda: calls.append("start_queue"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert scheduled is True
    assert calls == ["mark_started", "queue_hydration", "start_queue"]
    assert events == [
        ("post_show.hydration.queued", {"route": "ready"}),
    ]


def test_schedule_ready_shell_post_show_hydration_skips_when_already_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell post-show scheduling should avoid duplicate hydration."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    scheduled = ready_shell_controller.schedule_ready_shell_post_show_hydration(
        startup_cancelled=False,
        hydration_started=True,
        mark_hydration_started=lambda: calls.append("mark_started"),
        queue_hydration_task=lambda: calls.append("queue_hydration"),
        start_queue=lambda: calls.append("start_queue"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert scheduled is False
    assert calls == []
    assert events == [
        ("post_show.hydration.skip", {"reason": "already_started"}),
    ]


def test_hydrate_ready_shell_initial_workspace_delegates_hydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell hydration task should delegate post-show hydration policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _HydrationMainWindow(calls)

    ready_shell_controller.hydrate_ready_shell_initial_workspace(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        hidden_restore_runtime_prepared=False,
        prehydration_succeeded=False,
        startup_timer=_Timer(calls),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=lambda: calls.append("summary"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert calls == [
        "mark:hydration_started",
        "span:start:post_show.hydration.full_hydrate",
        f"hydrate:{id(workspace)}",
        "span:end:post_show.hydration.full_hydrate",
        "mark:hydration_completed",
        "warmups:fallback_after_hydration",
        "summary",
    ]
    assert events[0] == ("post_show.hydration.start", {"route": "ready"})
    assert events[-1] == ("post_show.visible_startup_summary", {"delay_ms": 0})


def test_hydrate_ready_shell_initial_workspace_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not inspect hydration collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)

    ready_shell_controller.hydrate_ready_shell_initial_workspace(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=None,
        hidden_restore_runtime_prepared=False,
        prehydration_succeeded=False,
        startup_timer=_Timer(calls),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=lambda: calls.append("summary"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert calls == []
    assert events == [
        ("post_show.hydration.skip", {"reason": "startup_cancelled"}),
    ]


def test_emit_ready_shell_visible_startup_summary_delegates_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell visible summary task should delegate summary policy."""

    events: list[tuple[str, dict[str, object]]] = []
    logs: list[dict[str, object]] = []
    _patch_trace(monkeypatch, events)
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "log_info",
        lambda _logger, message, **fields: logs.append({"message": message, **fields}),
    )
    timer = _marked_timer()

    ready_shell_controller.emit_ready_shell_visible_startup_summary(
        startup_timer=timer,
        workspace=None,
        trace_fields=lambda: {"route": "ready"},
    )

    summary_fields = {
        "session_restore_used": False,
        "workflow_count": 0,
        "active_cube_count": 0,
        "splash_close_to_shell_show_ms": "50.000",
        "splash_close_to_hydration_complete_ms": "150.000",
        "splash_close_to_restore_running_ms": "200.000",
    }
    assert logs == [
        {
            "message": "Startup visible loading summary",
            **summary_fields,
        }
    ]
    assert events == [
        (
            "startup.visible_loading.summary",
            {**summary_fields, "route": "ready"},
        )
    ]


def test_ready_shell_post_show_controller_projects_queues_and_hydrates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-show controller should own backend projection and hydration queue glue."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _PostShowMainWindow(calls)
    state = _HydrationState()
    queued_tasks: list[tuple[str, Callable[[], None]]] = []
    summary_callbacks: list[Callable[[], None]] = []

    controller = ready_shell_controller.ReadyShellPostShowController(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        state=state,
        queue_named_task=lambda name, callback: queued_tasks.append((name, callback)),
        start_queue=lambda: calls.append("start_queue"),
        workspace=lambda: workspace,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=cast(StartupTimer, _Timer(calls)),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=summary_callbacks.append,
        trace_fields=lambda: {"route": "ready"},
    )

    updated = controller.update_backend_state("ready")
    scheduled = controller.schedule_hydration()
    queued_tasks[0][1]()

    assert updated is True
    assert scheduled is True
    assert main_window.generation_action_controller.states == ["ready"]
    assert state.hydration_started is True
    assert queued_tasks == [
        ("hydrate_initial_workspace", controller.hydrate_initial_workspace)
    ]
    assert summary_callbacks == [controller.log_visible_startup_summary]
    assert calls == [
        "start_queue",
        "mark:hydration_started",
        "span:start:post_show.hydration.full_hydrate",
        f"hydrate:{id(workspace)}",
        "span:end:post_show.hydration.full_hydrate",
        "mark:hydration_completed",
        "warmups:fallback_after_hydration",
    ]
    assert events[0] == (
        "shell_backend_state.update",
        {"state": "ready", "route": "ready"},
    )
    assert events[1] == ("post_show.hydration.queued", {"route": "ready"})


def test_ready_shell_post_show_controller_logs_visible_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-show controller should delegate visible startup summary logging."""

    events: list[tuple[str, dict[str, object]]] = []
    logs: list[dict[str, object]] = []
    _patch_trace(monkeypatch, events)
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "log_info",
        lambda _logger, message, **fields: logs.append({"message": message, **fields}),
    )

    controller = ready_shell_controller.ReadyShellPostShowController(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: object(),
        state=_HydrationState(),
        queue_named_task=lambda _name, _callback: None,
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=_marked_timer(),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {"route": "ready"},
    )

    controller.log_visible_startup_summary()

    assert logs[0]["message"] == "Startup visible loading summary"
    assert events == [
        (
            "startup.visible_loading.summary",
            {
                "session_restore_used": False,
                "workflow_count": 0,
                "active_cube_count": 0,
                "splash_close_to_shell_show_ms": "50.000",
                "splash_close_to_hydration_complete_ms": "150.000",
                "splash_close_to_restore_running_ms": "200.000",
                "route": "ready",
            },
        )
    ]


def test_create_ready_shell_post_show_controller_returns_controller() -> None:
    """Ready-shell post-show controller construction should live in its owner."""

    controller = ready_shell_controller.create_ready_shell_post_show_controller(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: object(),
        state=_HydrationState(),
        queue_named_task=lambda _name, _callback: None,
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=_marked_timer(),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {},
    )

    assert isinstance(controller, ready_shell_controller.ReadyShellPostShowController)


def test_create_bound_ready_shell_post_show_controller_binds_backend_updater() -> None:
    """Bound post-show factory should connect backend-state projection."""

    main_window = _BackendStateMainWindow()
    updater = ready_shell_controller.ReadyShellBackendStateUpdater()
    controller = ready_shell_controller.create_bound_ready_shell_post_show_controller(
        backend_state_updater=updater,
        startup_cancelled=lambda: False,
        shell_frame=lambda: object(),
        main_window_for_shell=lambda _frame: main_window,
        state=_HydrationState(),
        queue_named_task=lambda _name, _callback: None,
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=_marked_timer(),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {},
    )

    updater.update("ready")

    assert isinstance(controller, ready_shell_controller.ReadyShellPostShowController)
    assert main_window.generation_action_controller.states == ["ready"]


def test_ready_shell_backend_state_updater_requires_binding() -> None:
    """Backend-state updater should fail before the post-show port is bound."""

    updater = ready_shell_controller.ReadyShellBackendStateUpdater()

    with pytest.raises(RuntimeError, match="updater is not bound"):
        updater.update("ready")


def test_ready_shell_backend_state_updater_forwards_to_bound_port() -> None:
    """Backend-state updater should forward states after binding."""

    states: list[str] = []
    updater = ready_shell_controller.ReadyShellBackendStateUpdater()

    def update_backend_state(state: str) -> None:
        """Record one backend state."""

        states.append(state)

    updater.bind(update_backend_state)

    updater.update("starting")
    updater.update("ready")
    assert states == ["starting", "ready"]


class _WorkspaceRestoreController:
    """Record workspace prehydration requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def prehydrate_initial_workspace(self, workspace: object) -> bool:
        """Record one prehydration request."""

        self._calls.append(f"prehydrate:{id(workspace)}")
        return True

    def hydrate_initial_workspace(self, workspace: object | None = None) -> None:
        """Record one hydration request."""

        if workspace is None:
            self._calls.append("hydrate:blank")
        else:
            self._calls.append(f"hydrate:{id(workspace)}")


class _GenerationActionController:
    """Record projected backend states."""

    def __init__(self) -> None:
        """Initialize recorded backend states."""

        self.states: list[str] = []

    def set_backend_state(self, state: str) -> None:
        """Record one backend state projection."""

        self.states.append(state)


class _HydrationMainWindow:
    """Expose workspace restore collaborators for hydration."""

    def __init__(self, calls: list[str]) -> None:
        """Create the workspace restore controller double."""

        self.workspace_restore_controller = _WorkspaceRestoreController(calls)
        self.shell_prehydrated_restore_controller = None


class _PostShowMainWindow:
    """Expose backend-state and hydration collaborators for post-show tests."""

    def __init__(self, calls: list[str]) -> None:
        """Create post-show shell collaborator doubles."""

        self.generation_action_controller = _GenerationActionController()
        self.workspace_restore_controller = _WorkspaceRestoreController(calls)
        self.shell_prehydrated_restore_controller = None


@dataclass
class _HydrationState:
    """Expose the ready-shell post-show hydration state field."""

    hydration_started: bool = False


class _RestoreFinalizedMainWindow:
    """Expose a restore-finalized signal for warmup wiring."""

    def __init__(self, signal: _Signal) -> None:
        """Store the restore-finalized signal double."""

        self.restore_finalized = signal
