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

"""Contract tests for prompt-editor main-thread async publication."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorMainThreadDispatcher,
    QtPromptEditorMainThreadDispatcher,
)


_WINDOWS_XDIST_QT_SKIP = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="Qt queued delivery can abort Windows xdist workers in full-suite runs",
)


@_WINDOWS_XDIST_QT_SKIP
def test_qt_main_thread_dispatcher_defers_publication_until_event_loop() -> None:
    """Published callbacks should run through queued Qt delivery."""

    app = _ensure_qapp()
    dispatcher = QtPromptEditorMainThreadDispatcher()
    calls: list[str] = []

    dispatcher.publish(lambda: calls.append("published"), reason="task_completed")

    assert calls == []
    _process_events(app)

    assert calls == ["published"]
    dispatcher.deleteLater()
    _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_qt_main_thread_dispatcher_preserves_publication_order() -> None:
    """Queued publications should preserve task completion ordering."""

    app = _ensure_qapp()
    dispatcher = QtPromptEditorMainThreadDispatcher()
    calls: list[str] = []

    dispatcher.publish(lambda: calls.append("first"), reason="first_completed")
    dispatcher.publish(lambda: calls.append("second"), reason="second_completed")

    _process_events(app)

    assert calls == ["first", "second"]
    dispatcher.deleteLater()
    _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_qt_main_thread_dispatcher_rejects_blank_publication_reason() -> None:
    """Publication reasons should be explicit and prompt-safe."""

    dispatcher = QtPromptEditorMainThreadDispatcher()

    with pytest.raises(ValueError, match="reason"):
        dispatcher.publish(lambda: None, reason=" ")

    dispatcher.deleteLater()
    _process_events(_ensure_qapp())


@_WINDOWS_XDIST_QT_SKIP
def test_qt_main_thread_dispatcher_ignores_publication_after_qt_destruction() -> None:
    """Deleted Qt receivers should drop late publications without widget mutation."""

    app = _ensure_qapp()
    dispatcher = QtPromptEditorMainThreadDispatcher()
    calls: list[str] = []

    dispatcher.deleteLater()
    _process_events(app)
    dispatcher.publish(lambda: calls.append("late"), reason="late_task_completed")
    _process_events(app)

    assert calls == []


def test_task_completion_can_depend_on_dispatcher_protocol() -> None:
    """Task completion code should publish through the dispatcher protocol."""

    class RecordingDispatcher:
        """Record publications while satisfying the main-thread dispatcher protocol."""

        def __init__(self) -> None:
            """Create an empty recording dispatcher."""

            self.reasons: list[str] = []

        def publish(self, callback: Callable[[], None], *, reason: str) -> None:
            """Record and invoke one publication callback."""

            self.reasons.append(reason)
            callback()

    dispatcher = RecordingDispatcher()
    calls: list[str] = []

    _publish_test_task_completion(
        dispatcher,
        callback=lambda: calls.append("published"),
    )

    assert dispatcher.reasons == ["test_task_completed"]
    assert calls == ["published"]


def _publish_test_task_completion(
    dispatcher: PromptEditorMainThreadDispatcher,
    *,
    callback: Callable[[], None],
) -> None:
    """Publish a test task completion without depending on a widget object."""

    dispatcher.publish(callback, reason="test_task_completed")


def _ensure_qapp() -> QApplication:
    """Return a QApplication for Qt queued-delivery tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, *, cycles: int = 5) -> None:
    """Flush queued signal and deferred-delete events."""

    for _ in range(cycles):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
