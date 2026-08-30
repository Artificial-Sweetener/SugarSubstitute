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

"""Test ready-shell restore hidden restore-runtime contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap import ready_shell_restore_controller
from substitute.app.bootstrap.ready_shell_restore_controller import (
    prepare_hidden_restore_runtime_before_show,
)

from .restore_support import (
    _MainWindow,
    _PhaseTimer,
    _PrehydratedRestoreController,
    _patch_trace,
)


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
