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

import pytest

from substitute.app.bootstrap import (
    ready_shell_controller,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)

from ..support.timing import _Timer
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


def test_try_reveal_ready_shell_blocks_until_all_gates_are_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should not inspect shell collaborators while blocked."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _ShowGateState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=state,
        pre_show_projection_pending=False,
        minimum_shell_ready=False,
        comfy_http_ready=True,
        shell_frame=object(),
        comfy_state=None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=object(),
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _window: calls.append("reveal"),
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(revealed=False)
    assert state.main_window_shown is False
    assert calls == []
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("main_shell.try_show.blocked", {"route": "ready"}),
    ]


def test_try_reveal_ready_shell_reports_fatal_managed_incident(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should fail closed on fatal managed startup incidents."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    incident = _FatalIncident(kind="startup_failed", severity="error")
    state = _ShowGateState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=state,
        pre_show_projection_pending=False,
        minimum_shell_ready=True,
        comfy_http_ready=True,
        shell_frame=object(),
        comfy_state=object(),
        fatal_incident_for_state=lambda _state: incident,
        handle_fatal_incident=lambda received: calls.append(
            "fatal" if received is incident else "fatal_wrong"
        ),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=None,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _window: calls.append("reveal"),
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(revealed=False)
    assert state.main_window_shown is False
    assert calls == ["fatal"]
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        (
            "main_shell.try_show.fatal_incident",
            {
                "incident_kind": "startup_failed",
                "incident_severity": "error",
                "route": "ready",
            },
        ),
    ]


def test_try_reveal_ready_shell_runs_restore_priority_and_reveals_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should warm restored state before immediate reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _ShowGateMainWindow(calls)
    revealed: list[object] = []
    state = _ShowGateState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=state,
        pre_show_projection_pending=False,
        minimum_shell_ready=True,
        comfy_http_ready=True,
        shell_frame=shell_frame,
        comfy_state=None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=revealed.append,
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=True,
        hidden_restore_runtime_prepared=True,
        pre_show_projection_deferred=False,
    )
    assert state.main_window_shown is True
    assert revealed == [main_window]
    assert calls == [
        "phase:start:startup.restore_cube_definition_warmup",
        "span:start:startup.restore_cube_definition_warmup",
        f"warm:{id(workspace)}",
        "span:end:startup.restore_cube_definition_warmup",
        "phase:end:startup.restore_cube_definition_warmup",
        "phase:start:startup.hidden_restore_runtime_prepare",
        "span:start:post_comfy.hidden_restore_runtime_prepare",
        "prepare_runtime",
        "span:end:post_comfy.hidden_restore_runtime_prepare",
        "phase:end:startup.hidden_restore_runtime_prepare",
    ]
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("post_comfy.restore_priority.begin", {"route": "ready"}),
        ("post_comfy.restore_priority.end", {"route": "ready"}),
        (
            "main_shell.pre_show_restore_projection.skip",
            {
                "reason": "start_callable_missing",
                "cache_artifact_present": False,
                "restored_active_workflow_id": "wf-a",
                "route": "ready",
            },
        ),
    ]


def test_try_reveal_ready_shell_defers_reveal_for_pre_show_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should wait for pre-show projection completion."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    projection_controller = _PreShowProjectionController(calls)
    main_window = _ShowGateMainWindow(
        calls,
        projection_controller=projection_controller,
    )
    projection_artifact = object()
    scheduled: list[tuple[int, Callable[[], None]]] = []
    revealed: list[object] = []
    show_state = _ShowGateState()
    projection_state = PreShowRestoreProjectionState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=show_state,
        pre_show_projection_pending=False,
        minimum_shell_ready=True,
        comfy_http_ready=True,
        shell_frame=shell_frame,
        comfy_state=None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=None,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=projection_state,
        provisional_restore_projection=projection_artifact,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=revealed.append,
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=True,
        hidden_restore_runtime_prepared=True,
        pre_show_projection_deferred=True,
    )
    assert projection_state.pending is True
    assert show_state.main_window_shown is True
    assert revealed == []
    assert len(scheduled) == 1
    assert projection_controller.completions

    projection_controller.completions[0]()

    assert projection_state.pending is False
    assert revealed == [main_window]
    assert events[-1] == (
        "main_shell.pre_show_restore_projection.complete",
        {"reason": "surface_complete", "route": "ready"},
    )


def test_ready_shell_show_gate_task_uses_live_state_and_records_hidden_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show-gate task should adapt live state through explicit ports."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _ShowGateMainWindow(calls)
    state = _ShowGateState()
    minimum_shell_ready = False
    hidden_runtime_updates: list[bool] = []
    revealed: list[object] = []

    task = ready_shell_controller.ReadyShellShowGateTask(
        startup_cancelled=lambda: False,
        state=state,
        pre_show_projection_pending=lambda: False,
        minimum_shell_ready=lambda: minimum_shell_ready,
        comfy_http_ready=lambda: True,
        shell_frame=lambda: shell_frame,
        comfy_state=lambda: None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=lambda: workspace,
        prehydration_succeeded=lambda: True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=lambda: None,
        fallback_workflow_id=lambda: "wf-live",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=revealed.append,
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        set_hidden_restore_runtime_prepared=hidden_runtime_updates.append,
        trace_fields=lambda: {"route": "ready"},
    )

    blocked_result = task.try_show()

    assert blocked_result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=False
    )
    assert state.main_window_shown is False
    assert hidden_runtime_updates == []
    assert revealed == []
    assert calls == []

    minimum_shell_ready = True
    revealed_result = task.try_show()

    assert revealed_result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=True,
        hidden_restore_runtime_prepared=True,
        pre_show_projection_deferred=False,
    )
    assert state.main_window_shown is True
    assert hidden_runtime_updates == [True]
    assert revealed == [main_window]
    assert calls == [
        "phase:start:startup.restore_cube_definition_warmup",
        "span:start:startup.restore_cube_definition_warmup",
        f"warm:{id(workspace)}",
        "span:end:startup.restore_cube_definition_warmup",
        "phase:end:startup.restore_cube_definition_warmup",
        "phase:start:startup.hidden_restore_runtime_prepare",
        "span:start:post_comfy.hidden_restore_runtime_prepare",
        "prepare_runtime",
        "span:end:post_comfy.hidden_restore_runtime_prepare",
        "phase:end:startup.hidden_restore_runtime_prepare",
    ]
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("main_shell.try_show.blocked", {"route": "ready"}),
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("post_comfy.restore_priority.begin", {"route": "ready"}),
        ("post_comfy.restore_priority.end", {"route": "ready"}),
        (
            "main_shell.pre_show_restore_projection.skip",
            {
                "reason": "start_callable_missing",
                "cache_artifact_present": False,
                "restored_active_workflow_id": "wf-live",
                "route": "ready",
            },
        ),
    ]


def test_create_ready_shell_show_gate_task_returns_task() -> None:
    """Show-gate task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_show_gate_task(
        startup_cancelled=lambda: False,
        state=_ShowGateState(),
        pre_show_projection_pending=lambda: False,
        minimum_shell_ready=lambda: False,
        comfy_http_ready=lambda: False,
        shell_frame=lambda: None,
        comfy_state=lambda: None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: None,
        main_window_for_shell=lambda _frame: object(),
        workspace=lambda: None,
        prehydration_succeeded=lambda: False,
        startup_timer=_Timer([]),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=lambda: None,
        fallback_workflow_id=lambda: "wf-live",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _window: None,
        scheduler=lambda _delay, _callback: None,
        set_hidden_restore_runtime_prepared=lambda _prepared: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellShowGateTask)


class _PrehydratedRestoreController:
    """Record hidden restore runtime preparation requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def prepare_initial_workspace_restore_runtime(self) -> bool:
        """Record hidden runtime preparation."""

        self._calls.append("prepare_runtime")
        return True


class _ShowGateMainWindow:
    """Expose restore-priority collaborators for show-gate tests."""

    def __init__(
        self,
        calls: list[str],
        *,
        projection_controller: _PreShowProjectionController | None = None,
    ) -> None:
        """Create all collaborators used before ready-shell reveal."""

        self.shell_restore_warmup_controller = _RestoreWarmupController(calls)
        self.shell_prehydrated_restore_controller = _PrehydratedRestoreController(calls)
        self.restore_projection_controller = projection_controller


class _PreShowProjectionController:
    """Capture pre-show projection completion callbacks."""

    def __init__(self, calls: list[str]) -> None:
        """Store call and completion recorders."""

        self._calls = calls
        self.completions: list[Callable[[], None]] = []

    def start_pre_show_restore_projection(
        self,
        artifact: object | None,
        *,
        fallback_workflow_id: str,
        on_complete: Callable[[], None],
    ) -> bool:
        """Record one pre-show projection request."""

        self._calls.append(
            "projection:"
            f"{'artifact' if artifact is not None else 'none'}:"
            f"{fallback_workflow_id}"
        )
        self.completions.append(on_complete)
        return True


@dataclass(frozen=True)
class _FatalIncident:
    """Expose fatal incident fields used by the show-gate trace."""

    kind: str
    severity: str


@dataclass
class _ShowGateState:
    """Expose the ready-shell show-gate state field."""

    main_window_shown: bool = False


class _RestoreWarmupController:
    """Record restored cube-definition warmup requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def warm_restored_workspace_cube_definitions(
        self, workspace: object | None
    ) -> None:
        """Record one restored workspace warmup."""

        if workspace is None:
            self._calls.append("warm:blank")
        else:
            self._calls.append(f"warm:{id(workspace)}")
