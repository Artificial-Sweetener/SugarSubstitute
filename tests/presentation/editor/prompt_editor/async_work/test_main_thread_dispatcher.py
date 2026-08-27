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

from collections.abc import Callable

import pytest

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorMainThreadDispatcher,
    QtPromptEditorMainThreadDispatcher,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_qt_main_thread_dispatcher_defers_publication_until_event_loop() -> None:
    """Published callbacks should run through queued Qt delivery."""

    dispatcher = QtPromptEditorMainThreadDispatcher()
    calls: list[str] = []

    dispatcher.publish(lambda: calls.append("published"), reason="task_completed")

    assert calls == []
    wait_for_qt_condition(lambda: calls == ["published"])

    assert calls == ["published"]
    destroy_qt_object(dispatcher)


def test_qt_main_thread_dispatcher_preserves_publication_order() -> None:
    """Queued publications should preserve task completion ordering."""

    dispatcher = QtPromptEditorMainThreadDispatcher()
    calls: list[str] = []

    dispatcher.publish(lambda: calls.append("first"), reason="first_completed")
    dispatcher.publish(lambda: calls.append("second"), reason="second_completed")

    wait_for_qt_condition(lambda: calls == ["first", "second"])

    assert calls == ["first", "second"]
    destroy_qt_object(dispatcher)


def test_qt_main_thread_dispatcher_rejects_blank_publication_reason() -> None:
    """Publication reasons should be explicit and prompt-safe."""

    dispatcher = QtPromptEditorMainThreadDispatcher()

    with pytest.raises(ValueError, match="reason"):
        dispatcher.publish(lambda: None, reason=" ")

    destroy_qt_object(dispatcher)


def test_qt_main_thread_dispatcher_ignores_publication_after_qt_destruction() -> None:
    """Deleted Qt receivers should drop late publications without widget mutation."""

    dispatcher = QtPromptEditorMainThreadDispatcher()
    calls: list[str] = []

    destroy_qt_object(dispatcher)
    dispatcher.publish(lambda: calls.append("late"), reason="late_task_completed")

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
