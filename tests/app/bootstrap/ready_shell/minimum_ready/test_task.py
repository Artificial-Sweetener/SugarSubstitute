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


def test_mark_ready_shell_minimum_ready_task_delegates_gate_and_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell minimum-ready task should update state and reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()

    marked = ready_shell_controller.mark_ready_shell_minimum_ready_task(
        startup_cancelled=False,
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert marked is True
    assert state.minimum_shell_ready is True
    assert calls == ["try_show"]
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_mark_ready_shell_minimum_ready_task_runs_after_mark_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell minimum-ready task should run follow-up work after reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()

    marked = ready_shell_controller.mark_ready_shell_minimum_ready_task(
        startup_cancelled=False,
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
        after_mark_ready=lambda: calls.append("after_mark"),
    )

    assert marked is True
    assert state.minimum_shell_ready is True
    assert calls == ["try_show", "after_mark"]
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_mark_ready_shell_minimum_ready_task_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not mark the minimum shell gate."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()

    marked = ready_shell_controller.mark_ready_shell_minimum_ready_task(
        startup_cancelled=True,
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert marked is False
    assert state.minimum_shell_ready is False
    assert calls == []
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        (
            "mark_minimum_shell_ready_task.skip",
            {"reason": "startup_cancelled"},
        ),
    ]


def test_minimum_ready_task_uses_live_cancellation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Minimum-ready task should read cancellation state when it runs."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()
    cancelled = [True]
    task = ready_shell_controller.ReadyShellMinimumReadyTask(
        startup_cancelled=lambda: cancelled[0],
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    skipped = task.mark_ready()

    assert skipped is False
    assert state.minimum_shell_ready is False
    assert calls == []

    cancelled[0] = False

    marked = task.mark_ready()

    assert marked is True
    assert state.minimum_shell_ready is True
    assert calls == ["try_show"]
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        (
            "mark_minimum_shell_ready_task.skip",
            {"reason": "startup_cancelled"},
        ),
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_minimum_ready_task_defers_reveal_until_prerequisite_settles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-interactive work must settle before the shell becomes usable."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    scheduled: list[tuple[int, Callable[[], None]]] = []
    prerequisite_ready = [False]
    state = _MinimumReadyState()
    task = ready_shell_controller.ReadyShellMinimumReadyTask(
        startup_cancelled=lambda: False,
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
        prerequisite_ready=lambda: prerequisite_ready[0],
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
    )

    task.run()

    assert state.minimum_shell_ready is False
    assert calls == []
    assert len(scheduled) == 1
    assert scheduled[0][0] == 10
    assert events == [
        (
            "mark_minimum_shell_ready_task.deferred",
            {"reason": "prerequisite_pending", "route": "ready"},
        )
    ]

    prerequisite_ready[0] = True
    scheduled.pop()[1]()

    assert state.minimum_shell_ready is True
    assert calls == ["try_show"]
    assert events[-2:] == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_minimum_ready_task_cancellation_does_not_poll_prerequisite() -> None:
    """Cancelled startup must terminate without scheduling another gate turn."""

    scheduled: list[tuple[int, Callable[[], None]]] = []
    state = _MinimumReadyState()
    task = ready_shell_controller.ReadyShellMinimumReadyTask(
        startup_cancelled=lambda: True,
        state=state,
        try_show_main_window=lambda: None,
        trace_fields=lambda: {},
        prerequisite_ready=lambda: False,
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
    )

    task.run()

    assert state.minimum_shell_ready is False
    assert scheduled == []


def test_create_ready_shell_minimum_ready_task_returns_task() -> None:
    """Minimum-ready task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_minimum_ready_task(
        startup_cancelled=lambda: False,
        state=_MinimumReadyState(),
        try_show_main_window=lambda: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellMinimumReadyTask)


@dataclass
class _MinimumReadyState:
    """Expose the ready-shell minimum-ready state field."""

    minimum_shell_ready: bool = False
