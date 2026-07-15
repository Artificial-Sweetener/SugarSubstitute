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

"""Run GUI startup work in short event-loop turns."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("app.bootstrap.gui_startup_queue")


@dataclass(frozen=True)
class GuiStartupTask:
    """Describe one queued GUI startup task."""

    name: str
    callback: Callable[[], None]


class GuiStartupTaskQueue:
    """Execute GUI startup tasks one at a time through a Qt timer scheduler."""

    def __init__(
        self,
        *,
        scheduler: Callable[[int, Callable[[], None]], None],
        startup_timer: StartupTimer | None = None,
        completed: Callable[[], None] | None = None,
        failed: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the queue with a single-shot scheduler."""

        self._scheduler = scheduler
        self._startup_timer = startup_timer
        self._completed = completed
        self._failed = failed
        self._tasks: list[GuiStartupTask] = []
        self._running = False
        self._scheduled = False
        self._cancelled = False

    def add(self, name: str, callback: Callable[[], None]) -> None:
        """Append one task and schedule execution when already running."""

        trace_mark(
            "gui_queue.task.added",
            task_name=name,
            cancelled=self._cancelled,
            running=self._running,
            scheduled=self._scheduled,
            pending_count_before=len(self._tasks),
        )
        if self._cancelled:
            trace_mark("gui_queue.task.add_skipped", task_name=name, reason="cancelled")
            return
        self._tasks.append(GuiStartupTask(name=name, callback=callback))
        trace_mark(
            "gui_queue.task.added.pending",
            task_name=name,
            pending_count_after=len(self._tasks),
        )
        if self._running and not self._scheduled:
            self._schedule_next()

    def start(self) -> None:
        """Start executing queued tasks on future event-loop turns."""

        trace_mark(
            "gui_queue.start",
            running=self._running,
            cancelled=self._cancelled,
            pending_count=len(self._tasks),
        )
        if self._running or self._cancelled:
            trace_mark(
                "gui_queue.start_skipped",
                reason="already_running" if self._running else "cancelled",
            )
            return
        self._running = True
        self._schedule_next()

    def cancel(self) -> None:
        """Cancel pending tasks and prevent future execution."""

        trace_mark(
            "gui_queue.cancel",
            pending_count=len(self._tasks),
            running=self._running,
            scheduled=self._scheduled,
        )
        self._cancelled = True
        self._tasks.clear()

    def _schedule_next(self) -> None:
        """Schedule the next queue drain turn."""

        next_task_name = self._tasks[0].name if self._tasks else "empty"
        trace_mark(
            "gui_queue.schedule_next",
            cancelled=self._cancelled,
            scheduled=self._scheduled,
            pending_count=len(self._tasks),
            next_task_name=next_task_name,
        )
        if self._cancelled or self._scheduled:
            trace_mark(
                "gui_queue.schedule_next_skipped",
                reason="cancelled" if self._cancelled else "already_scheduled",
                pending_count=len(self._tasks),
                next_task_name=next_task_name,
            )
            return
        self._scheduled = True
        trace_mark(
            "gui_queue.task.scheduled",
            task_name=next_task_name,
            delay_ms=0,
        )
        self._scheduler(0, self._run_next)

    def _run_next(self) -> None:
        """Run one queued task and yield before the following task."""

        trace_mark(
            "gui_queue.run_next.enter",
            cancelled=self._cancelled,
            pending_count=len(self._tasks),
        )
        self._scheduled = False
        if self._cancelled:
            trace_mark("gui_queue.run_next.cancelled")
            return
        if not self._tasks:
            self._running = False
            trace_mark("gui_queue.empty")
            if self._completed is not None:
                self._completed()
            return
        task = self._tasks.pop(0)
        try:
            trace_mark(
                "gui_queue.task.start",
                task_name=task.name,
                pending_count_after_pop=len(self._tasks),
            )
            if self._startup_timer is None:
                task.callback()
            else:
                with self._startup_timer.phase(f"gui_startup.{task.name}"):
                    task.callback()
            trace_mark(
                "gui_queue.task.end",
                task_name=task.name,
                pending_count_after=len(self._tasks),
            )
        except Exception:
            self._running = False
            self._cancelled = True
            self._tasks.clear()
            trace_mark("gui_queue.task.failed", task_name=task.name)
            log_exception(
                _LOGGER,
                "GUI startup task failed",
                task_name=task.name,
            )
            if self._failed is not None:
                try:
                    self._failed(task.name)
                except Exception:
                    log_exception(
                        _LOGGER,
                        "GUI startup failure callback failed",
                        task_name=task.name,
                    )
            return
        self._schedule_next()


__all__ = ["GuiStartupTask", "GuiStartupTaskQueue"]
