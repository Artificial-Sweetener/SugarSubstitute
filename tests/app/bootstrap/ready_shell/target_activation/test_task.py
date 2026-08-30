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


def test_activate_ready_shell_target_starts_managed_comfy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell target activation should sequence managed startup ports."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    context = object()
    splash = object()
    output_stream = object()
    diagnostics = object()
    comfy_state = object()

    def activate_target(**kwargs: object) -> object:
        """Record activation inputs and return a managed Comfy state."""

        assert kwargs["installation_context"] is context
        assert kwargs["splash"] is splash
        assert kwargs["comfy_output_stream"] is output_stream
        assert kwargs["startup_diagnostics"] is diagnostics
        calls.append("activate_target")
        return comfy_state

    result = ready_shell_controller.activate_ready_shell_target(
        startup_cancelled=False,
        splash=splash,
        installation_context=context,
        comfy_output_stream=output_stream,
        startup_diagnostics=diagnostics,
        startup_timer=_Timer(calls),
        activate_target=activate_target,
        mark_activation_started=lambda: calls.append("mark_started"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is True
    assert result.comfy_state is comfy_state
    assert calls == [
        "mark_started",
        "phase:start:startup.activate_target",
        "span:start:activate_target_task.activate",
        "activate_target",
        "span:end:activate_target_task.activate",
        "phase:end:startup.activate_target",
    ]
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        (
            "activate_target_task.end",
            {"comfy_state_present": True, "route": "ready"},
        ),
    ]


def test_activate_ready_shell_target_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not activate managed Comfy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    result = ready_shell_controller.activate_ready_shell_target(
        startup_cancelled=True,
        splash=object(),
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: calls.append("activate"),
        mark_activation_started=lambda: calls.append("mark_started"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is False
    assert result.comfy_state is None
    assert calls == []
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_activate_ready_shell_target_task_records_started_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell activation task should store produced managed Comfy state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    comfy_state = object()
    state = _ActivationState()
    recorded_states: list[object | None] = []

    result = ready_shell_controller.activate_ready_shell_target_task(
        startup_cancelled=False,
        splash=object(),
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: comfy_state,
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is True
    assert result.comfy_state is comfy_state
    assert state.comfy_activation_started is True
    assert recorded_states == [comfy_state]
    assert calls == [
        "phase:start:startup.activate_target",
        "span:start:activate_target_task.activate",
        "span:end:activate_target_task.activate",
        "phase:end:startup.activate_target",
    ]
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        (
            "activate_target_task.end",
            {"comfy_state_present": True, "route": "ready"},
        ),
    ]


def test_activate_ready_shell_target_task_leaves_state_when_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipped ready-shell activation must not mutate managed Comfy state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _ActivationState()
    recorded_states: list[object | None] = []

    result = ready_shell_controller.activate_ready_shell_target_task(
        startup_cancelled=True,
        splash=object(),
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: calls.append("activate"),
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is False
    assert result.comfy_state is None
    assert state.comfy_activation_started is False
    assert recorded_states == []
    assert calls == []
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_activate_ready_shell_target_task_skips_when_already_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prestarted managed activation should not launch Comfy a second time."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _ActivationState(comfy_activation_started=True)
    recorded_states: list[object | None] = []

    result = ready_shell_controller.activate_ready_shell_target_task(
        startup_cancelled=False,
        splash=None,
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: calls.append("activate"),
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is False
    assert result.comfy_state is None
    assert state.comfy_activation_started is True
    assert recorded_states == []
    assert calls == []
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "already_started"}),
    ]


def test_target_activation_task_uses_live_startup_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target activation task should read cancellation and splash state on run."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    context = object()
    output_stream = object()
    diagnostics = object()
    splash = object()
    splash_state: list[object | None] = [None]
    cancelled = [True]
    comfy_state = object()
    state = _ActivationState()
    recorded_states: list[object | None] = []

    def activate_target(**kwargs: object) -> object:
        """Record activation inputs and return a managed Comfy state."""

        assert kwargs["installation_context"] is context
        assert kwargs["splash"] is splash
        assert kwargs["comfy_output_stream"] is output_stream
        assert kwargs["startup_diagnostics"] is diagnostics
        calls.append("activate")
        return comfy_state

    task = ready_shell_controller.ReadyShellTargetActivationTask(
        startup_cancelled=lambda: cancelled[0],
        splash=lambda: splash_state[0],
        installation_context=context,
        comfy_output_stream=output_stream,
        startup_diagnostics=diagnostics,
        startup_timer=_Timer(calls),
        activate_target=activate_target,
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    skipped = task.activate()

    assert skipped.started is False
    assert state.comfy_activation_started is False
    assert recorded_states == []
    assert calls == []

    cancelled[0] = False
    splash_state[0] = splash

    activated = task.activate()

    assert activated.started is True
    assert activated.comfy_state is comfy_state
    assert state.comfy_activation_started is True
    assert recorded_states == [comfy_state]
    assert calls == [
        "phase:start:startup.activate_target",
        "span:start:activate_target_task.activate",
        "activate",
        "span:end:activate_target_task.activate",
        "phase:end:startup.activate_target",
    ]
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "startup_cancelled"}),
        ("activate_target_task.start", {"route": "ready"}),
        (
            "activate_target_task.end",
            {"comfy_state_present": True, "route": "ready"},
        ),
    ]


def test_create_ready_shell_target_activation_task_returns_task() -> None:
    """Target activation task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_target_activation_task(
        startup_cancelled=lambda: False,
        splash=lambda: None,
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer([]),
        activate_target=lambda **_kwargs: None,
        state=_ActivationState(),
        set_comfy_state=lambda _state: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellTargetActivationTask)


@dataclass
class _ActivationState:
    """Expose the ready-shell activation-started state field."""

    comfy_activation_started: bool = False
