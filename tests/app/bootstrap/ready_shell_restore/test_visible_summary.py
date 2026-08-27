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

"""Test ready-shell restore visible-startup-summary contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap import ready_shell_restore_controller
from substitute.app.bootstrap.ready_shell_restore_controller import (
    log_visible_startup_summary,
)
from substitute.app.bootstrap.startup_timing import StartupTimer

from .restore_support import (
    _patch_trace,
)


def _marked_timer() -> StartupTimer:
    """Build a startup timer with deterministic visible-summary milestones."""

    ticks = iter((0.0, 0.100, 0.150, 0.250, 0.300))
    timer = StartupTimer(clock=lambda: next(ticks))
    timer.mark("splash_closed")
    timer.mark("main_shell_shown")
    timer.mark("hydration_completed")
    timer.mark("restore_lifecycle_running")
    return timer


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
