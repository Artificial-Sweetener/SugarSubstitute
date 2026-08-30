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

"""Test Qt owner-thread execution publication."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QThread
import pytest

from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_qt_owner_thread_dispatcher_uses_queued_delivery() -> None:
    """Defer published callbacks until Qt processes queued delivery."""

    ensure_qt_application()
    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)
    delivered: list[str] = []
    try:
        dispatcher.publish(lambda: delivered.append("done"), reason="test_publish")

        assert delivered == []
        wait_for_qt_condition(lambda: delivered == ["done"])
    finally:
        destroy_qt_object(receiver)


def test_qt_owner_thread_dispatcher_publishes_worker_callbacks_on_owner_thread() -> (
    None
):
    """Execute worker publications on the preconstructed receiver thread."""

    application = ensure_qt_application()
    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)
    delivered_threads: list[QThread] = []
    try:
        with ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="qt-owner-thread-dispatcher-test",
        ) as executor:
            publication = executor.submit(
                dispatcher.publish,
                lambda: delivered_threads.append(QThread.currentThread()),
                reason="worker_publish",
            )
            publication.result(timeout=1.0)

        assert dispatcher.thread() is application.thread()
        wait_for_qt_condition(lambda: len(delivered_threads) == 1)
        assert delivered_threads == [application.thread()]
    finally:
        destroy_qt_object(receiver)


def test_qt_owner_thread_dispatcher_drops_after_receiver_destroyed() -> None:
    """Drop later publications after the receiver is destroyed."""

    ensure_qt_application()
    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)
    delivered: list[str] = []

    destroy_qt_object(receiver)
    dispatcher.publish(lambda: delivered.append("done"), reason="test_publish")

    assert delivered == []
    assert dispatcher.is_destroyed


def test_qt_owner_thread_dispatcher_rejects_blank_reason() -> None:
    """Require a nonblank publication reason."""

    ensure_qt_application()
    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)
    try:
        with pytest.raises(ValueError, match="reason"):
            dispatcher.publish(lambda: None, reason=" ")
    finally:
        destroy_qt_object(receiver)
