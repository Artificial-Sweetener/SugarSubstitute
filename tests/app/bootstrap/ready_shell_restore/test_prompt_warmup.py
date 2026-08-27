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

"""Test ready-shell restore prompt-editor warmup contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap.ready_shell_restore_controller import (
    warm_prompt_editor_gui_before_reveal,
)

from .restore_support import (
    _patch_trace,
)


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
