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

"""Tests for GUI startup task queue scheduling."""

from __future__ import annotations

from collections.abc import Callable

from substitute.app.bootstrap.gui_startup_queue import GuiStartupTaskQueue


def test_gui_startup_queue_runs_one_task_per_scheduled_turn() -> None:
    """Queue execution should yield to the event loop between startup tasks."""

    scheduled: list[Callable[[], None]] = []
    calls: list[str] = []
    queue = GuiStartupTaskQueue(
        scheduler=lambda _delay, callback: scheduled.append(callback)
    )
    queue.add("first", lambda: calls.append("first"))
    queue.add("second", lambda: calls.append("second"))

    queue.start()

    assert calls == []
    assert len(scheduled) == 1
    scheduled.pop(0)()
    assert calls == ["first"]
    assert len(scheduled) == 1
    scheduled.pop(0)()
    assert calls == ["first", "second"]


def test_gui_startup_queue_ignores_pending_tasks_after_cancel() -> None:
    """Cancellation should clear pending startup work."""

    scheduled: list[Callable[[], None]] = []
    calls: list[str] = []
    queue = GuiStartupTaskQueue(
        scheduler=lambda _delay, callback: scheduled.append(callback)
    )
    queue.add("first", lambda: calls.append("first"))
    queue.start()
    queue.cancel()

    scheduled.pop(0)()

    assert calls == []


def test_gui_startup_queue_runs_completion_after_all_tasks() -> None:
    """Queue completion should run once after the final drain turn."""

    scheduled: list[Callable[[], None]] = []
    calls: list[str] = []
    queue = GuiStartupTaskQueue(
        scheduler=lambda _delay, callback: scheduled.append(callback),
        completed=lambda: calls.append("done"),
    )
    queue.add("first", lambda: calls.append("first"))
    queue.start()

    scheduled.pop(0)()
    scheduled.pop(0)()

    assert calls == ["first", "done"]


def test_gui_startup_queue_stops_after_task_failure() -> None:
    """Task failures should stop pending startup work after logging the exception."""

    scheduled: list[Callable[[], None]] = []
    calls: list[str] = []
    queue = GuiStartupTaskQueue(
        scheduler=lambda _delay, callback: scheduled.append(callback)
    )

    def fail() -> None:
        calls.append("fail")
        raise RuntimeError("boom")

    queue.add("fail", fail)
    queue.add("second", lambda: calls.append("second"))
    queue.start()

    scheduled.pop(0)()

    assert calls == ["fail"]
    assert scheduled == []


def test_gui_startup_queue_reports_failed_task_name() -> None:
    """Startup orchestration should be able to fail closed after task failure."""

    scheduled: list[Callable[[], None]] = []
    failures: list[str] = []
    queue = GuiStartupTaskQueue(
        scheduler=lambda _delay, callback: scheduled.append(callback),
        failed=failures.append,
    )

    def fail() -> None:
        raise RuntimeError("boom")

    queue.add("build_main_window", fail)
    queue.start()

    scheduled.pop(0)()

    assert failures == ["build_main_window"]
