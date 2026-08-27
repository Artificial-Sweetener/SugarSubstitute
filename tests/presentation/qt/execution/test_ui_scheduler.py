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

"""Test owner-thread Qt UI scheduling."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject
import pytest

from substitute.presentation.qt.execution import QtUiScheduler
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_qt_ui_scheduler_accepts_requests_from_worker_threads() -> None:
    """Deliver worker-originated schedule requests through the Qt owner thread."""

    ensure_qt_application()
    receiver = QObject()
    scheduler = QtUiScheduler(receiver)
    delivered: list[str] = []
    try:
        with ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="qt-ui-scheduler-test",
        ) as executor:
            request = executor.submit(
                scheduler.schedule,
                0,
                lambda: delivered.append("done"),
                reason="worker_handoff",
            )
            request.result(timeout=1.0)

        assert delivered == []
        wait_for_qt_condition(lambda: delivered == ["done"])
    finally:
        destroy_qt_object(receiver)


def test_qt_ui_scheduler_processes_items_in_chunks() -> None:
    """Process every item through repeated owner-thread chunks."""

    ensure_qt_application()
    receiver = QObject()
    scheduler = QtUiScheduler(receiver)
    processed: list[int] = []
    try:
        scheduler.schedule_chunked(
            [1, 2, 3, 4, 5],
            processed.append,
            chunk_size=2,
            reason="chunk_test",
        )

        wait_for_qt_condition(lambda: processed == [1, 2, 3, 4, 5])
    finally:
        destroy_qt_object(receiver)


def test_qt_ui_scheduler_validates_requests() -> None:
    """Reject invalid delay, chunk budget, and reason values."""

    ensure_qt_application()
    receiver = QObject()
    scheduler = QtUiScheduler(receiver)
    try:
        with pytest.raises(ValueError, match="delay_ms"):
            scheduler.schedule(-1, lambda: None, reason="bad_delay")
        with pytest.raises(ValueError, match="reason"):
            scheduler.schedule(0, lambda: None, reason=" ")
        with pytest.raises(ValueError, match="chunk_size"):
            scheduler.schedule_chunked(
                [],
                lambda _item: None,
                chunk_size=0,
                reason="bad",
            )
    finally:
        destroy_qt_object(receiver)
