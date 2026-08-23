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

"""Test ready-shell restore post-show scheduling and minimum-ready contracts."""

from __future__ import annotations


import pytest

from substitute.app.bootstrap.ready_shell_restore_controller import (
    mark_minimum_shell_ready,
    schedule_post_show_hydration_after_reveal,
)

from .restore_support import (
    _patch_trace,
)


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
