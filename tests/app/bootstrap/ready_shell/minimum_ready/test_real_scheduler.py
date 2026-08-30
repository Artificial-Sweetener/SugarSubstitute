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

"""Verify minimum-shell readiness against the real Qt scheduler."""

from __future__ import annotations

import gc

from PySide6.QtCore import QTimer

from substitute.app.bootstrap.ready_shell_minimum_ready import (
    ReadyShellMinimumReadyTask,
)
from substitute.app.bootstrap.startup_qt_timers import startup_single_shot
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _MinimumReadyState:
    """Hold the minimum-ready gate observed by the shell reveal path."""

    minimum_shell_ready = False


def test_real_qt_retry_survives_release_by_startup_queue() -> None:
    """Qt must retain a deferred gate after the startup queue drops its task."""

    ensure_qt_application()
    prerequisite_ready = [False]
    reveal_attempts: list[bool] = []
    state = _MinimumReadyState()

    def reveal() -> None:
        """Record successful readiness."""

        reveal_attempts.append(True)

    def schedule_then_release_task() -> None:
        """Match the production queue's ownership ending after ``run``."""

        task = ReadyShellMinimumReadyTask(
            startup_cancelled=lambda: False,
            state=state,
            try_show_main_window=reveal,
            trace_fields=lambda: {},
            prerequisite_ready=lambda: prerequisite_ready[0],
            scheduler=startup_single_shot,
        )
        task.run()

    schedule_then_release_task()
    gc.collect()
    prerequisite_timer = QTimer()
    prerequisite_timer.setSingleShot(True)
    prerequisite_timer.timeout.connect(lambda: prerequisite_ready.__setitem__(0, True))
    try:
        prerequisite_timer.start(25)
        wait_for_qt_condition(lambda: state.minimum_shell_ready, timeout_ms=1_000)
    finally:
        prerequisite_timer.stop()
        destroy_qt_object(prerequisite_timer)

    assert state.minimum_shell_ready is True
    assert reveal_attempts == [True]
