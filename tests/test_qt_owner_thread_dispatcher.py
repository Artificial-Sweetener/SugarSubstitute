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

"""Tests for Qt owner-thread execution publication."""

from __future__ import annotations

from collections.abc import Callable
import threading
import time
from typing import cast

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.qt.execution import QtOwnerThreadDispatcher


def test_qt_owner_thread_dispatcher_uses_queued_delivery() -> None:
    """Published callbacks should not run until Qt processes events."""

    app = _ensure_qapp()
    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)
    delivered: list[str] = []

    dispatcher.publish(lambda: delivered.append("done"), reason="test_publish")

    assert delivered == []
    assert _process_until(app, lambda: delivered == ["done"])


def test_qt_owner_thread_dispatcher_publishes_worker_callbacks_on_owner_thread() -> (
    None
):
    """Worker publications should execute on the preconstructed receiver thread."""

    app = _ensure_qapp()
    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)
    delivered_threads: list[QThread] = []

    worker = threading.Thread(
        target=lambda: dispatcher.publish(
            lambda: delivered_threads.append(QThread.currentThread()),
            reason="worker_publish",
        ),
        name="qt-owner-thread-dispatcher-test",
    )
    worker.start()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert dispatcher.thread() is app.thread()
    assert _process_until(app, lambda: len(delivered_threads) == 1)
    assert delivered_threads == [app.thread()]


def test_qt_owner_thread_dispatcher_drops_after_receiver_destroyed() -> None:
    """Receiver destruction should prevent later callback delivery."""

    app = _ensure_qapp()
    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)
    delivered: list[str] = []

    receiver.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    dispatcher.publish(lambda: delivered.append("done"), reason="test_publish")
    app.processEvents()

    assert delivered == []
    assert dispatcher.is_destroyed


def test_qt_owner_thread_dispatcher_rejects_blank_reason() -> None:
    """Publication reasons should be mandatory."""

    receiver = QObject()
    dispatcher = QtOwnerThreadDispatcher(receiver)

    with pytest.raises(ValueError, match="reason"):
        dispatcher.publish(lambda: None, reason=" ")


def _ensure_qapp() -> QApplication:
    """Return a Qt application for signal-delivery tests."""

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
