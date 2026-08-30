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


def test_warm_ready_shell_prompt_editor_gui_delegates_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell prompt editor warmup task should delegate warmup policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    main_window = object()

    warmed = ready_shell_controller.warm_ready_shell_prompt_editor_gui(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else None
        ),
        warm_prompt_editor_gui=lambda window: calls.append(
            "warm" if window is main_window else "wrong_window"
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is True
    assert calls == [
        "span:start:warm_prompt_editor_gui_task.run",
        "warm",
        "span:end:warm_prompt_editor_gui_task.run",
    ]
    assert events == [
        ("warm_prompt_editor_gui_task.start", {"route": "ready"}),
        ("warm_prompt_editor_gui_task.end", {"route": "ready"}),
    ]


def test_warm_ready_shell_prompt_editor_gui_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not warm prompt editor GUI collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)

    warmed = ready_shell_controller.warm_ready_shell_prompt_editor_gui(
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


def test_prompt_editor_warmup_task_uses_live_shell_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt editor warmup task should read current startup state per run."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    main_window = object()
    shell_state: list[object | None] = [None]
    task = ready_shell_controller.ReadyShellPromptEditorWarmupTask(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_state[0],
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else None
        ),
        warm_prompt_editor_gui=lambda window: calls.append(
            "warm" if window is main_window else "wrong_window"
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert task.warm() is False

    shell_state[0] = shell_frame

    assert task.warm() is True
    assert calls == [
        "span:start:warm_prompt_editor_gui_task.run",
        "warm",
        "span:end:warm_prompt_editor_gui_task.run",
    ]
    assert events[0] == ("warm_prompt_editor_gui_task.start", {"route": "ready"})
    assert events[1] == (
        "warm_prompt_editor_gui_task.skip",
        {"reason": "no_shell_frame"},
    )
    assert events[-1] == ("warm_prompt_editor_gui_task.end", {"route": "ready"})


def test_create_ready_shell_prompt_editor_warmup_task_returns_task() -> None:
    """Prompt editor warmup task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_prompt_editor_warmup_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: object(),
        warm_prompt_editor_gui=lambda _window: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellPromptEditorWarmupTask)
