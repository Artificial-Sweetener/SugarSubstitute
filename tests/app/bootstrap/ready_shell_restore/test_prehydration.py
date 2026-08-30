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

"""Test ready-shell restore pre-show workspace-prehydration contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap import ready_shell_restore_controller
from substitute.app.bootstrap.ready_shell_restore_controller import (
    prehydrate_initial_workspace_before_show,
)

from .restore_support import (
    _MainWindow,
    _PhaseTimer,
    _WorkspaceRestoreController,
    _clock,
    _patch_trace,
)


def test_prehydrate_initial_workspace_before_show_runs_restore_prehydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-show restore prehydration should call the workspace restore controller."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    workspace = object()
    main_window = _MainWindow(
        workspace_restore_controller=_WorkspaceRestoreController(calls),
        prehydrated_restore_controller=None,
    )

    result = prehydrate_initial_workspace_before_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        workspace=workspace,
        startup_timer=_PhaseTimer(calls),
        workspace_workflow_count=lambda value: 2 if value is workspace else 0,
        trace_fields=lambda: {"route": "ready"},
        clock=_clock(1.0, 1.1),
    )

    assert result.attempted is True
    assert result.succeeded is True
    assert calls == [
        "phase:start:startup.prehydrate_initial_workspace",
        f"prehydrate:{id(workspace)}",
        "phase:end:startup.prehydrate_initial_workspace",
    ]
    assert events[0] == (
        "prehydrate_initial_workspace_task.start",
        {"route": "ready"},
    )
    assert events[-1] == (
        "prehydrate_initial_workspace_task.end",
        {"route": "ready"},
    )


def test_prehydrate_initial_workspace_before_show_skips_without_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prehydration should skip when there is no restored workspace."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    def main_window_for_shell(_frame: object) -> object:
        """Record unexpected shell access."""

        calls.append("main_window")
        return object()

    result = prehydrate_initial_workspace_before_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=main_window_for_shell,
        workspace=None,
        startup_timer=_PhaseTimer(calls),
        workspace_workflow_count=lambda _workspace: 0,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is False
    assert result.succeeded is False
    assert calls == []
    assert events[-1] == (
        "prehydrate_initial_workspace_task.skip",
        {"reason": "no_initial_workspace"},
    )


def test_prehydrate_initial_workspace_before_show_skips_without_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prehydration should skip when the shell exposes no prehydration port."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    main_window = _MainWindow(
        workspace_restore_controller=None,
        prehydrated_restore_controller=None,
    )

    result = prehydrate_initial_workspace_before_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        workspace=object(),
        startup_timer=_PhaseTimer(calls),
        workspace_workflow_count=lambda _workspace: 0,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is False
    assert result.succeeded is False
    assert calls == []
    assert events[-1] == (
        "prehydrate_initial_workspace_task.skip",
        {"reason": "no_prehydration_callable"},
    )


def test_prehydrate_initial_workspace_before_show_logs_over_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slow hidden prehydration should produce a bounded warning."""

    events: list[tuple[str, dict[str, object]]] = []
    warnings: list[dict[str, object]] = []
    _patch_trace(monkeypatch, events)
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "log_warning",
        lambda _logger, message, **fields: warnings.append(
            {"message": message, **fields}
        ),
    )
    calls: list[str] = []
    workspace = object()
    main_window = _MainWindow(
        workspace_restore_controller=_WorkspaceRestoreController(
            calls,
            prehydrate_result=False,
        ),
        prehydrated_restore_controller=None,
    )

    result = prehydrate_initial_workspace_before_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        workspace=workspace,
        startup_timer=_PhaseTimer(calls),
        workspace_workflow_count=lambda _workspace: 1,
        trace_fields=lambda: {"route": "ready"},
        clock=_clock(0.0, 1.0),
        budget_seconds=0.5,
    )

    assert result.attempted is True
    assert result.succeeded is False
    assert warnings == [
        {
            "message": "Hidden workspace prehydration exceeded budget",
            "elapsed_ms": "1000.000",
            "budget_ms": "500.000",
            "prehydration_succeeded": False,
        }
    ]
