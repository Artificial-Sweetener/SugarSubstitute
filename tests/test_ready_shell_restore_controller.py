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

"""Tests for ready-shell restore hydration orchestration."""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from substitute.app.bootstrap import ready_shell_restore_controller
from substitute.app.bootstrap.ready_shell_restore_controller import (
    attach_restore_asset_preload_to_shell,
    hydrate_initial_workspace_after_show,
    log_visible_startup_summary,
    mark_minimum_shell_ready,
    prepare_hidden_restore_runtime_before_show,
    prehydrate_initial_workspace_before_show,
    schedule_post_show_hydration_after_reveal,
    update_shell_backend_state,
    warm_prompt_editor_gui_before_reveal,
)
from substitute.app.bootstrap.startup_timing import StartupTimer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
READY_SHELL_RESTORE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "ready_shell_restore_controller.py"
)
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_READY_SHELL_RESTORE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
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


def test_hydrate_initial_workspace_after_show_runs_full_hydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Visible-shell hydration should call the workspace restore controller."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    workspace = object()
    main_window = _MainWindow(
        workspace_restore_controller=_WorkspaceRestoreController(calls),
        prehydrated_restore_controller=_PrehydratedRestoreController(calls),
    )

    hydrate_initial_workspace_after_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
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
        f"hydrate:{id(workspace)}",
        "mark:hydration_completed",
        "warmups:fallback_after_hydration",
        "summary",
    ]
    assert events[0] == ("post_show.hydration.start", {"route": "ready"})
    assert events[-1] == ("post_show.visible_startup_summary", {"delay_ms": 0})


def test_hydrate_initial_workspace_after_show_finishes_prepared_restore_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prepared restore runtime should finish layout before fallback finalization."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    workspace = object()
    main_window = _MainWindow(
        workspace_restore_controller=_WorkspaceRestoreController(calls),
        prehydrated_restore_controller=_PrehydratedRestoreController(
            calls,
            finish_layout_result=False,
        ),
    )

    hydrate_initial_workspace_after_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        workspace=workspace,
        hidden_restore_runtime_prepared=True,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=lambda: calls.append("summary"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert calls == [
        "mark:hydration_started",
        "finish_layout",
        f"finalize:{id(workspace)}",
        "mark:hydration_completed",
        "warmups:fallback_after_hydration",
        "summary",
    ]
    assert (
        "post_show.hydration.finish_restore_layout.fallback",
        {},
    ) in events


def test_hydrate_initial_workspace_after_show_waits_when_finalization_is_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending restore layout finalization should defer nonessential warmups."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    main_window = _MainWindow(
        workspace_restore_controller=_WorkspaceRestoreController(calls),
        prehydrated_restore_controller=_PrehydratedRestoreController(
            calls,
            finalization_pending=True,
        ),
    )

    hydrate_initial_workspace_after_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        workspace=None,
        hidden_restore_runtime_prepared=False,
        prehydration_succeeded=False,
        startup_timer=_Timer(calls),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=lambda: calls.append("summary"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert calls == [
        "mark:hydration_started",
        "hydrate:blank",
        "mark:hydration_completed",
        "summary",
    ]
    assert (
        "post_comfy.nonessential_warmups.waiting_after_hydration",
        {"route": "ready"},
    ) in events


def test_hydrate_initial_workspace_after_show_schedules_warmups_without_hydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing hydration collaborators should release warmups through fallback."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    main_window = _MainWindow(
        workspace_restore_controller=None,
        prehydrated_restore_controller=None,
    )

    hydrate_initial_workspace_after_show(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        workspace=None,
        hidden_restore_runtime_prepared=False,
        prehydration_succeeded=False,
        startup_timer=_Timer(calls),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=lambda: calls.append("summary"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert calls == [
        "mark:hydration_started",
        "warmups:no_hydration_callable",
    ]
    assert events[-1] == (
        "post_show.hydration.skip",
        {"reason": "no_hydration_callable"},
    )


def test_hydrate_initial_workspace_after_show_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not inspect shell hydration collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    def main_window_for_shell(_frame: object) -> object:
        """Record unexpected shell access."""

        calls.append("main_window")
        return object()

    hydrate_initial_workspace_after_show(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=main_window_for_shell,
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


def test_log_visible_startup_summary_emits_log_and_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Visible startup summaries should include prompt-safe route context."""

    events: list[tuple[str, dict[str, object]]] = []
    logs: list[dict[str, object]] = []
    _patch_trace(monkeypatch, events)
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "log_info",
        lambda _logger, message, **fields: logs.append({"message": message, **fields}),
    )
    timer = _marked_timer()

    log_visible_startup_summary(
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


def test_prepare_hidden_restore_runtime_before_show_runs_when_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hidden restore runtime preparation should use the prehydrated controller."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    main_window = _MainWindow(
        workspace_restore_controller=None,
        prehydrated_restore_controller=_PrehydratedRestoreController(calls),
    )

    prepared = prepare_hidden_restore_runtime_before_show(
        main_window=main_window,
        comfy_http_ready=True,
        prehydration_succeeded=True,
        startup_timer=_PhaseTimer(calls),
    )

    assert prepared is True
    assert calls == [
        "phase:start:startup.hidden_restore_runtime_prepare",
        "prepare_runtime",
        "phase:end:startup.hidden_restore_runtime_prepare",
    ]
    assert events == []


def test_prepare_hidden_restore_runtime_before_show_skips_without_prehydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hidden restore runtime preparation should require successful prehydration."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    main_window = _MainWindow(
        workspace_restore_controller=None,
        prehydrated_restore_controller=_PrehydratedRestoreController(calls),
    )

    prepared = prepare_hidden_restore_runtime_before_show(
        main_window=main_window,
        comfy_http_ready=True,
        prehydration_succeeded=False,
        startup_timer=_PhaseTimer(calls),
    )

    assert prepared is False
    assert calls == []
    assert events == [
        (
            "post_comfy.hidden_restore_runtime_prepare.skip",
            {"reason": "prehydration_not_succeeded"},
        )
    ]


def test_prepare_hidden_restore_runtime_before_show_logs_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hidden restore runtime failures should preserve startup progress."""

    events: list[tuple[str, dict[str, object]]] = []
    errors: list[str] = []
    _patch_trace(monkeypatch, events)
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "log_exception",
        lambda _logger, message, **_fields: errors.append(message),
    )
    calls: list[str] = []
    main_window = _MainWindow(
        workspace_restore_controller=None,
        prehydrated_restore_controller=_PrehydratedRestoreController(
            calls,
            prepare_runtime_error=RuntimeError("prepare failed"),
        ),
    )

    prepared = prepare_hidden_restore_runtime_before_show(
        main_window=main_window,
        comfy_http_ready=True,
        prehydration_succeeded=True,
        startup_timer=_PhaseTimer(calls),
    )

    assert prepared is False
    assert calls == [
        "phase:start:startup.hidden_restore_runtime_prepare",
        "prepare_runtime",
        "phase:end:startup.hidden_restore_runtime_prepare",
    ]
    assert errors == ["Failed to prepare restored workspace runtime before reveal"]


def test_schedule_post_show_hydration_after_reveal_queues_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-show hydration scheduling should set the gate and start the queue."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    scheduled = schedule_post_show_hydration_after_reveal(
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


def test_schedule_post_show_hydration_after_reveal_skips_when_already_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-show hydration scheduling should not enqueue twice."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    scheduled = schedule_post_show_hydration_after_reveal(
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


def test_mark_minimum_shell_ready_sets_gate_and_requests_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Minimum shell readiness should set the gate and request reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    marked = mark_minimum_shell_ready(
        startup_cancelled=False,
        mark_ready=lambda: calls.append("mark_ready"),
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert marked is True
    assert calls == ["mark_ready", "try_show"]
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_mark_minimum_shell_ready_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not mutate readiness or request reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    marked = mark_minimum_shell_ready(
        startup_cancelled=True,
        mark_ready=lambda: calls.append("mark_ready"),
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert marked is False
    assert calls == []
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        (
            "mark_minimum_shell_ready_task.skip",
            {"reason": "startup_cancelled"},
        ),
    ]


def test_warm_prompt_editor_gui_before_reveal_runs_for_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt editor GUI warmup should use the shell main-window port."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    shell_frame = object()
    main_window = object()

    warmed = warm_prompt_editor_gui_before_reveal(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else None
        ),
        warm_prompt_editor_gui=lambda window: calls.append(f"warm:{id(window)}"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is True
    assert calls == [f"warm:{id(main_window)}"]
    assert events == [
        ("warm_prompt_editor_gui_task.start", {"route": "ready"}),
        ("warm_prompt_editor_gui_task.end", {"route": "ready"}),
    ]


def test_warm_prompt_editor_gui_before_reveal_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not inspect shell warmup collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    warmed = warm_prompt_editor_gui_before_reveal(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        warm_prompt_editor_gui=lambda _window: calls.append("warm"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is False
    assert calls == []
    assert events == [
        ("warm_prompt_editor_gui_task.start", {"route": "ready"}),
        (
            "warm_prompt_editor_gui_task.skip",
            {"reason": "startup_cancelled"},
        ),
    ]


def test_warm_prompt_editor_gui_before_reveal_skips_without_main_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing main-window lookup should end without warming GUI surfaces."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    warmed = warm_prompt_editor_gui_before_reveal(
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: None,
        warm_prompt_editor_gui=lambda _window: calls.append("warm"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is False
    assert calls == []
    assert events == [
        ("warm_prompt_editor_gui_task.start", {"route": "ready"}),
        ("warm_prompt_editor_gui_task.end", {"route": "ready"}),
    ]


def test_attach_restore_asset_preload_to_shell_sets_restore_preload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore asset preloads should be passed to the shell restore adapter."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    preload = object()
    restore_adapter = _RestoreImageAdapter()
    main_window = _RestoreAssetMainWindow(restore_adapter)

    attached = attach_restore_asset_preload_to_shell(
        main_window=main_window,
        restore_asset_preload=preload,
        trace_fields=lambda: {"route": "ready"},
    )

    assert attached is True
    assert restore_adapter.preloads == [preload]
    assert events == [
        (
            "build_shell_task.restore_asset_preload.attached",
            {"route": "ready"},
        )
    ]


def test_attach_restore_asset_preload_to_shell_skips_without_preload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing restore preloads should not inspect shell adapters."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = object()

    attached = attach_restore_asset_preload_to_shell(
        main_window=main_window,
        restore_asset_preload=None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert attached is False
    assert events == [
        (
            "build_shell_task.restore_asset_preload.skip",
            {"reason": "no_restore_asset_preload", "route": "ready"},
        )
    ]


def test_attach_restore_asset_preload_to_shell_skips_without_adapter_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incomplete shell adapters should not fail restore preload handoff."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = _RestoreAssetMainWindow(restore_adapter=object())

    attached = attach_restore_asset_preload_to_shell(
        main_window=main_window,
        restore_asset_preload=object(),
        trace_fields=lambda: {"route": "ready"},
    )

    assert attached is False
    assert events == [
        (
            "build_shell_task.restore_asset_preload.skip",
            {"reason": "no_restore_asset_preload_port", "route": "ready"},
        )
    ]


def test_update_shell_backend_state_projects_generation_action_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend state projection should call the composed generation controller."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    states: list[str] = []
    main_window = _BackendMainWindow(
        generation_action_controller=_GenerationActionController(states)
    )

    updated = update_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is True
    assert states == ["ready"]
    assert events == [
        ("shell_backend_state.update", {"state": "ready", "route": "ready"}),
    ]


def test_update_shell_backend_state_skips_without_shell_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend state projection should ignore missing shell frames."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    def main_window_for_shell(_frame: object) -> object:
        """Record unexpected shell access."""

        calls.append("main_window")
        return object()

    updated = update_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=None,
        main_window_for_shell=main_window_for_shell,
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is False
    assert calls == []
    assert events == []


def test_update_shell_backend_state_skips_without_generation_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend state projection should tolerate incomplete shell adapters."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = _BackendMainWindow(generation_action_controller=None)

    updated = update_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is False
    assert events == []


def test_ready_shell_restore_controller_imports_no_forbidden_boundaries() -> None:
    """Ready-shell restore controller should stay Qt-free and adapter-light."""

    imported_modules = _imported_module_names(READY_SHELL_RESTORE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_READY_SHELL_RESTORE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_post_show_hydration_logic() -> None:
    """Startup should delegate post-show hydration branch ownership."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    ready_shell_controller_source = READY_SHELL_CONTROLLER_SOURCE.read_text(
        encoding="utf-8"
    )

    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task("
        not in source
    )
    assert "create_ready_shell_initial_workspace_prehydration_task(" not in source
    assert "ReadyShellInitialWorkspacePrehydrationTask(" not in source
    assert "def prehydrate_initial_workspace_task" not in source
    assert "prehydrate_ready_shell_initial_workspace_task(" not in source
    assert " prehydrate_ready_shell_initial_workspace(" not in source
    assert "ready_state.prehydration_attempted = True" not in source
    assert "prehydration_result.attempted" not in source
    assert "prehydrate_initial_workspace_before_show(" not in source
    assert "prehydrate_initial_workspace_before_show(" in ready_shell_controller_source
    assert "Hidden workspace prehydration exceeded budget" not in source
    assert "managed_ready_launch.create_post_show_controller(" in launch_source
    assert "managed_ready_runtime.create_post_show_controller(" not in source
    assert "create_bound_ready_shell_post_show_controller(" not in source
    assert "create_ready_shell_post_show_controller(" not in source
    assert "ReadyShellPostShowController(" not in source
    assert "def hydrate_initial_workspace_task" not in source
    assert " hydrate_ready_shell_initial_workspace(" not in source
    assert "hydrate_ready_shell_initial_workspace(" in ready_shell_controller_source
    assert "hydrate_initial_workspace_after_show(" not in source
    assert "hydrate_initial_workspace_after_show(" in ready_shell_controller_source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task(" not in source
    assert "create_ready_shell_show_gate_task(" not in source
    assert "ReadyShellShowGateTask(" not in source
    assert "try_reveal_ready_shell(" not in source
    assert "prepare_ready_shell_hidden_restore_runtime(" not in source
    assert (
        "prepare_ready_shell_hidden_restore_runtime(" in ready_shell_controller_source
    )
    assert "prepare_hidden_restore_runtime_before_show(" not in source
    assert (
        "prepare_hidden_restore_runtime_before_show(" in ready_shell_controller_source
    )
    assert "post_comfy.hidden_restore_runtime_prepare.skip" not in source
    assert "Failed to prepare restored workspace runtime before reveal" not in source
    assert "project_ready_shell_backend_state(" not in source
    assert "project_ready_shell_backend_state(" in ready_shell_controller_source
    assert "update_built_shell_backend_state(" not in source
    assert "update_shell_backend_state(" in ready_shell_controller_source
    assert "generation_action_controller" not in source
    assert "shell_backend_state.update" not in source
    assert "schedule_ready_shell_post_show_hydration(" not in source
    assert "schedule_ready_shell_post_show_hydration(" in ready_shell_controller_source
    assert "schedule_post_show_hydration_after_reveal(" not in source
    assert "schedule_post_show_hydration_after_reveal(" in ready_shell_controller_source
    assert "post_show.hydration.queued" not in source
    assert 'reason="already_started"' not in source
    assert "post_show.hydration.finish_restore_layout.fallback" not in source
    assert "post_show.hydration.full_hydrate" not in source
    assert "post_comfy.nonessential_warmups.waiting_after_hydration" not in source
    assert "managed_ready_launch.create_minimum_ready_task(" in launch_source
    assert "managed_ready_runtime.create_minimum_ready_task(" not in source
    assert "create_ready_shell_minimum_ready_task(" not in source
    assert "ReadyShellMinimumReadyTask(" not in source
    assert "def mark_minimum_shell_ready_task" not in source
    assert "mark_ready_shell_minimum_ready_task(" not in source
    assert "mark_ready_shell_minimum_ready(" not in source
    assert "mark_minimum_shell_ready_task.start" not in source
    assert "mark_minimum_shell_ready_task.end" not in source
    assert "managed_ready_launch.create_prompt_editor_warmup_task(" in launch_source
    assert "managed_ready_runtime.create_prompt_editor_warmup_task(" not in source
    assert "create_ready_shell_prompt_editor_warmup_task(" not in source
    assert "ReadyShellPromptEditorWarmupTask(" not in source
    assert "warm_ready_shell_prompt_editor_gui(" not in source
    assert "warm_prompt_editor_gui_before_reveal(" not in source
    assert "warm_prompt_editor_gui_before_reveal(" in ready_shell_controller_source
    assert "warm_prompt_editor_gui_task.start" not in source
    assert "warm_prompt_editor_gui_task.run" not in source
    assert "emit_ready_shell_visible_startup_summary(" not in source
    assert "emit_ready_shell_visible_startup_summary(" in ready_shell_controller_source
    assert "emit_visible_startup_summary(" not in source
    assert "log_visible_startup_summary(" in ready_shell_controller_source
    assert "build_visible_loading_summary(" not in source
    assert "startup.visible_loading.summary" not in source
    assert "attach_restore_asset_preload_to_shell(" not in source
    assert "attach_restore_asset_preload_to_shell(" in ready_shell_controller_source
    assert "workspace_restore_image_adapter" not in source
    assert "set_restore_asset_preload" not in source


class _Timer:
    """Record startup timer marks."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records."""

        self._calls = calls

    def mark(self, name: str) -> None:
        """Record one timer mark."""

        self._calls.append(f"mark:{name}")


class _PhaseTimer:
    """Record startup timer phases."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records."""

        self._calls = calls

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Record phase entry and exit."""

        self._calls.append(f"phase:start:{name}")
        try:
            yield
        finally:
            self._calls.append(f"phase:end:{name}")


class _BackendMainWindow:
    """Expose generation action state projection collaborators."""

    def __init__(self, *, generation_action_controller: object | None) -> None:
        """Store generation controller double."""

        self.generation_action_controller = generation_action_controller


class _RestoreAssetMainWindow:
    """Expose a restore image adapter for preload handoff tests."""

    def __init__(self, restore_adapter: object) -> None:
        """Store the restore adapter double."""

        self.workspace_restore_image_adapter = restore_adapter


class _RestoreImageAdapter:
    """Record restore asset preload handoff."""

    def __init__(self) -> None:
        """Create empty preload records."""

        self.preloads: list[object] = []

    def set_restore_asset_preload(self, preload: object) -> None:
        """Record one restore asset preload."""

        self.preloads.append(preload)


class _GenerationActionController:
    """Record backend state updates."""

    def __init__(self, states: list[str]) -> None:
        """Store state records."""

        self._states = states

    def set_backend_state(self, state: str) -> None:
        """Record one backend state."""

        self._states.append(state)


class _MainWindow:
    """Expose shell restore collaborators for hydration tests."""

    def __init__(
        self,
        *,
        workspace_restore_controller: object | None,
        prehydrated_restore_controller: object | None,
    ) -> None:
        """Store controller doubles."""

        self.workspace_restore_controller = workspace_restore_controller
        self.shell_prehydrated_restore_controller = prehydrated_restore_controller


class _WorkspaceRestoreController:
    """Record workspace hydration requests."""

    def __init__(self, calls: list[str], *, prehydrate_result: bool = True) -> None:
        """Store call records."""

        self._calls = calls
        self._prehydrate_result = prehydrate_result

    def prehydrate_initial_workspace(self, workspace: object) -> bool:
        """Record a prehydration request."""

        self._calls.append(f"prehydrate:{id(workspace)}")
        return self._prehydrate_result

    def hydrate_initial_workspace(self, workspace: object | None = None) -> None:
        """Record a full hydration request."""

        if workspace is None:
            self._calls.append("hydrate:blank")
            return
        self._calls.append(f"hydrate:{id(workspace)}")


class _PrehydratedRestoreController:
    """Record prehydrated restore finalization requests."""

    def __init__(
        self,
        calls: list[str],
        *,
        prepare_runtime_error: Exception | None = None,
        finish_layout_result: bool = True,
        finalization_pending: bool = False,
    ) -> None:
        """Store behavior flags and call records."""

        self._calls = calls
        self._prepare_runtime_error = prepare_runtime_error
        self._finish_layout_result = finish_layout_result
        self._finalization_pending = finalization_pending

    def prepare_initial_workspace_restore_runtime(self) -> bool:
        """Record restore-runtime preparation."""

        self._calls.append("prepare_runtime")
        if self._prepare_runtime_error is not None:
            raise self._prepare_runtime_error
        return True

    def finalize_initial_workspace_restore(self, workspace: object | None) -> None:
        """Record finalization for one workspace."""

        self._calls.append(f"finalize:{id(workspace)}")

    def finish_initial_workspace_restore_layout(self) -> bool:
        """Record restore-layout finishing."""

        self._calls.append("finish_layout")
        return self._finish_layout_result

    def restore_layout_finalization_pending(self) -> bool:
        """Return whether restore layout finalization is pending."""

        return self._finalization_pending


def _patch_trace(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple[str, dict[str, object]]],
) -> None:
    """Patch trace recording for deterministic assertions."""

    def trace(event_name: str, **fields: object) -> None:
        """Record one trace event."""

        events.append((event_name, fields))

    monkeypatch.setattr(ready_shell_restore_controller, "trace_mark", trace)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _clock(*values: float) -> Callable[[], float]:
    """Return one callable clock from fixed values."""

    iterator = iter(values)
    return iterator.__next__


def _marked_timer() -> StartupTimer:
    """Build a startup timer with deterministic visible-summary milestones."""

    ticks = iter((0.0, 0.100, 0.150, 0.250, 0.300))
    timer = StartupTimer(clock=lambda: next(ticks))
    timer.mark("splash_closed")
    timer.mark("main_shell_shown")
    timer.mark("hydration_completed")
    timer.mark("restore_lifecycle_running")
    return timer
