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

"""Tests for owner-thread Qt UI scheduling."""

from __future__ import annotations

from collections.abc import Callable
from threading import Thread
import time
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.qt.execution import QtUiScheduler


def test_qt_ui_scheduler_accepts_requests_from_worker_threads() -> None:
    """Worker-originated schedule requests should run on Qt event processing."""

    app = _ensure_qapp()
    receiver = QObject()
    scheduler = QtUiScheduler(receiver)
    delivered: list[str] = []

    worker = Thread(
        target=lambda: scheduler.schedule(
            0,
            lambda: delivered.append("done"),
            reason="worker_handoff",
        ),
        name="qt-ui-scheduler-test",
    )
    worker.start()
    worker.join(1.0)

    assert delivered == []
    assert _process_until(app, lambda: delivered == ["done"])


def test_qt_ui_scheduler_processes_items_in_chunks() -> None:
    """Chunked scheduling should process all items without one large handoff."""

    app = _ensure_qapp()
    receiver = QObject()
    scheduler = QtUiScheduler(receiver)
    processed: list[int] = []

    scheduler.schedule_chunked(
        [1, 2, 3, 4, 5],
        processed.append,
        chunk_size=2,
        reason="chunk_test",
    )

    assert _process_until(app, lambda: processed == [1, 2, 3, 4, 5])


def test_qt_ui_scheduler_validates_requests() -> None:
    """Scheduler inputs should reject invalid delay, budget, and reason values."""

    receiver = QObject()
    scheduler = QtUiScheduler(receiver)

    with pytest.raises(ValueError, match="delay_ms"):
        scheduler.schedule(-1, lambda: None, reason="bad_delay")
    with pytest.raises(ValueError, match="reason"):
        scheduler.schedule(0, lambda: None, reason=" ")
    with pytest.raises(ValueError, match="chunk_size"):
        scheduler.schedule_chunked([], lambda _item: None, chunk_size=0, reason="bad")


def _ensure_qapp() -> QApplication:
    """Return a Qt application for scheduler tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_until(
    app: QApplication,
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 1.0,
) -> bool:
    """Process Qt events until a predicate is true or timeout expires."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        app.processEvents()
        time.sleep(0.005)
    return predicate()
