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

from pathlib import Path

import pytest

from substitute.app.bootstrap import (
    ready_shell_controller,
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


def test_prehydrate_ready_shell_initial_workspace_delegates_prehydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell prehydration task should delegate restore policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _PrehydrationMainWindow(calls)

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda value: 3 if value is workspace else 0,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is True
    assert result.succeeded is True
    assert calls == [
        "phase:start:startup.prehydrate_initial_workspace",
        "span:start:prehydrate_initial_workspace_task.prehydrate",
        f"prehydrate:{id(workspace)}",
        "span:end:prehydrate_initial_workspace_task.prehydrate",
        "phase:end:startup.prehydrate_initial_workspace",
    ]
    assert events == [
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        ("prehydrate_initial_workspace_task.end", {"route": "ready"}),
    ]


def test_prehydrate_ready_shell_initial_workspace_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not prehydrate workspace collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=object(),
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda _workspace: 0,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is False
    assert result.succeeded is False
    assert calls == []
    assert events == [
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        (
            "prehydrate_initial_workspace_task.skip",
            {"reason": "startup_cancelled"},
        ),
    ]


def test_prehydrate_ready_shell_initial_workspace_task_records_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell prehydration task should record attempted and succeeded gates."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _PrehydrationMainWindow(calls)
    state = _PrehydrationState()

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace_task(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda value: 1 if value is workspace else 0,
        state=state,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is True
    assert result.succeeded is True
    assert state.prehydration_attempted is True
    assert state.prehydration_succeeded is True
    assert calls == [
        "phase:start:startup.prehydrate_initial_workspace",
        "span:start:prehydrate_initial_workspace_task.prehydrate",
        f"prehydrate:{id(workspace)}",
        "span:end:prehydrate_initial_workspace_task.prehydrate",
        "phase:end:startup.prehydrate_initial_workspace",
    ]


def test_prehydrate_ready_shell_initial_workspace_task_leaves_state_when_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipped prehydration should not mutate ready-shell gate state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _PrehydrationState()

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace_task(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=object(),
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda _workspace: 0,
        state=state,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is False
    assert result.succeeded is False
    assert state.prehydration_attempted is False
    assert state.prehydration_succeeded is False
    assert calls == []


def test_initial_workspace_prehydration_task_uses_live_shell_and_workspace_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initial workspace prehydration task should read live shell/workspace state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    state = _PrehydrationState()
    shell_frame = object()
    shell_state: list[object | None] = [None]
    workspace = object()
    workspace_state: list[object | None] = [workspace]
    main_window = _PrehydrationMainWindow(calls)

    task = ready_shell_controller.ReadyShellInitialWorkspacePrehydrationTask(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_state[0],
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=lambda: workspace_state[0],
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda value: 2 if value is workspace else 0,
        state=state,
        trace_fields=lambda: {"route": "ready"},
    )

    skipped_result = task.prehydrate()

    assert skipped_result.attempted is False
    assert skipped_result.succeeded is False
    assert state.prehydration_attempted is False
    assert state.prehydration_succeeded is False
    assert calls == []

    shell_state[0] = shell_frame
    workspace_state[0] = object()

    completed_result = task.prehydrate()

    assert completed_result.attempted is True
    assert completed_result.succeeded is True
    assert state.prehydration_attempted is True
    assert state.prehydration_succeeded is True
    assert calls == [
        "phase:start:startup.prehydrate_initial_workspace",
        "span:start:prehydrate_initial_workspace_task.prehydrate",
        f"prehydrate:{id(workspace_state[0])}",
        "span:end:prehydrate_initial_workspace_task.prehydrate",
        "phase:end:startup.prehydrate_initial_workspace",
    ]
    assert events == [
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        (
            "prehydrate_initial_workspace_task.skip",
            {"reason": "no_shell_frame"},
        ),
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        ("prehydrate_initial_workspace_task.end", {"route": "ready"}),
    ]


def test_create_ready_shell_initial_workspace_prehydration_task_returns_task() -> None:
    """Initial workspace prehydration task construction should live in its owner."""

    task = (
        ready_shell_controller.create_ready_shell_initial_workspace_prehydration_task(
            startup_cancelled=lambda: False,
            shell_frame=lambda: None,
            main_window_for_shell=lambda _frame: object(),
            workspace=lambda: None,
            startup_timer=_Timer([]),
            workspace_workflow_count=lambda _workspace: 0,
            state=_PrehydrationState(),
            trace_fields=lambda: {"route": "ready"},
        )
    )

    assert isinstance(
        task,
        ready_shell_controller.ReadyShellInitialWorkspacePrehydrationTask,
    )


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


class _PrehydrationMainWindow:
    """Expose workspace restore collaborators for prehydration."""

    def __init__(self, calls: list[str]) -> None:
        """Create the workspace restore controller double."""

        self.workspace_restore_controller = _WorkspaceRestoreController(calls)


class _PrehydrationState:
    """Record ready-shell prehydration gate state."""

    def __init__(self) -> None:
        """Initialize prehydration gates as not attempted."""

        self.prehydration_attempted = False
        self.prehydration_succeeded = False
