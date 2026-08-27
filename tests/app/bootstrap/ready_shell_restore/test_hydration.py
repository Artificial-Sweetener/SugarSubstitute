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

"""Test ready-shell restore post-show workspace-hydration contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap.ready_shell_restore_controller import (
    hydrate_initial_workspace_after_show,
)

from .restore_support import (
    _MainWindow,
    _PrehydratedRestoreController,
    _Timer,
    _WorkspaceRestoreController,
    _patch_trace,
)


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
