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

"""Contract tests for the prompt-editor local task executor adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, get_ident
from typing import TypeVar

import pytest

from substitute.application.execution import TaskHandle, TaskRequest
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorTaskExecutor,
    PromptEditorCancellationToken,
)
from tests.execution_test_helpers import prompt_task_executor

TResult = TypeVar("TResult")


def test_task_executor_executes_work_and_dispatches_successful_outcome() -> None:
    """Submitted work should complete through a dispatcher-published outcome."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    caller_thread_id = get_ident()
    callback_called = Event()
    execution_thread_id: list[int] = []
    outcomes: list[PromptAsyncTaskOutcome[int]] = []

    def work(_token: PromptEditorCancellationToken) -> int:
        execution_thread_id.append(get_ident())
        return 7

    handle = executor.submit(_request(work=work), cancellation=_Token())
    handle.add_done_callback(
        lambda outcome: _record_outcome(outcomes, outcome, callback_called),
        reason="test_success",
    )

    assert callback_called.wait(3.0)
    assert handle.is_finished is True
    assert handle.identity.request_id == 1
    assert handle.outcome is outcomes[0]
    assert outcomes[0].result == 7
    assert outcomes[0].error is None
    assert outcomes[0].cancelled is False
    assert execution_thread_id and execution_thread_id[0] != caller_thread_id
    assert dispatcher.reasons == ["test_success"]
    executor.shutdown()


def test_task_executor_captures_task_exception_as_outcome_error() -> None:
    """Task failures should publish as outcomes instead of escaping callbacks."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    callback_called = Event()
    outcomes: list[PromptAsyncTaskOutcome[int]] = []

    def work(_token: PromptEditorCancellationToken) -> int:
        raise RuntimeError("task failed")

    handle = executor.submit(_request(work=work), cancellation=_Token())
    handle.add_done_callback(
        lambda outcome: _record_outcome(outcomes, outcome, callback_called),
        reason="test_failure",
    )

    assert callback_called.wait(3.0)
    assert outcomes[0].result is None
    assert isinstance(outcomes[0].error, RuntimeError)
    assert outcomes[0].cancelled is False
    assert handle.outcome is outcomes[0]
    assert dispatcher.reasons == ["test_failure"]
    executor.shutdown()


def test_task_executor_dispatches_callbacks_added_after_completion() -> None:
    """Late callbacks should still publish through the dispatcher."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    first_callback_called = Event()
    late_callback_called = Event()
    first_outcomes: list[PromptAsyncTaskOutcome[int]] = []
    late_outcomes: list[PromptAsyncTaskOutcome[int]] = []

    handle = executor.submit(_request(work=lambda _token: 11), cancellation=_Token())
    handle.add_done_callback(
        lambda outcome: _record_outcome(
            first_outcomes,
            outcome,
            first_callback_called,
        ),
        reason="first_completion",
    )
    assert first_callback_called.wait(3.0)

    handle.add_done_callback(
        lambda outcome: _record_outcome(
            late_outcomes,
            outcome,
            late_callback_called,
        ),
        reason="late_completion",
    )

    assert late_callback_called.wait(3.0)
    assert late_outcomes == first_outcomes
    assert dispatcher.reasons == ["first_completion", "late_completion"]
    executor.shutdown()


def test_task_executor_can_cancel_queued_work_before_it_runs() -> None:
    """Task handles should expose concrete future cancellation."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    blocker_started = Event()
    release_blocker = Event()
    cancelled_callback_called = Event()
    cancelled_outcomes: list[PromptAsyncTaskOutcome[int]] = []
    queued_work_ran = False

    def blocking_work(_token: PromptEditorCancellationToken) -> int:
        blocker_started.set()
        assert release_blocker.wait(3.0)
        return 1

    def queued_work(_token: PromptEditorCancellationToken) -> int:
        nonlocal queued_work_ran
        queued_work_ran = True
        return 2

    blocking_handle = executor.submit(
        _request(work=blocking_work), cancellation=_Token()
    )
    assert blocker_started.wait(3.0)
    queued_handle = executor.submit(_request(work=queued_work), cancellation=_Token())
    queued_handle.add_done_callback(
        lambda outcome: _record_outcome(
            cancelled_outcomes,
            outcome,
            cancelled_callback_called,
        ),
        reason="queued_cancelled",
    )

    queued_handle.cancel(reason="test_cancel")

    assert cancelled_callback_called.wait(3.0)
    assert cancelled_outcomes[0].cancelled is True
    assert cancelled_outcomes[0].result is None
    assert cancelled_outcomes[0].error is None
    assert queued_work_ran is False

    release_blocker.set()
    while not blocking_handle.is_finished:
        assert release_blocker.is_set()
    executor.shutdown()


def test_task_executor_does_not_submit_pre_cancelled_requests() -> None:
    """Pre-cancelled tokens should produce cancelled outcomes without running work."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    callback_called = Event()
    outcomes: list[PromptAsyncTaskOutcome[int]] = []
    work_ran = False

    def work(_token: PromptEditorCancellationToken) -> int:
        nonlocal work_ran
        work_ran = True
        return 5

    handle = executor.submit(
        _request(work=work),
        cancellation=_Token(is_cancelled=True, reason="pre_cancelled"),
    )
    handle.add_done_callback(
        lambda outcome: _record_outcome(outcomes, outcome, callback_called),
        reason="pre_cancelled",
    )

    assert callback_called.wait(3.0)
    assert outcomes[0].cancelled is True
    assert work_ran is False
    executor.shutdown()


def test_task_executor_rejects_submit_after_shutdown() -> None:
    """Shutdown should make the prompt task adapter stop accepting work."""

    executor = prompt_task_executor(dispatcher=_RecordingDispatcher())
    executor.shutdown()

    with pytest.raises(RuntimeError, match="shut down"):
        executor.submit(_request(work=lambda _token: 1), cancellation=_Token())


def test_task_executor_converts_submitter_backpressure_to_failed_outcome() -> None:
    """Runtime submission backpressure should not escape Qt callback delivery."""

    error = RuntimeError("Execution lane prompt_editor queue is full.")
    executor = PromptEditorTaskExecutor(
        submitter=_RejectingSubmitter(error),
    )
    outcomes: list[PromptAsyncTaskOutcome[int]] = []

    handle = executor.submit(_request(work=lambda _token: 1), cancellation=_Token())
    handle.add_done_callback(outcomes.append, reason="submission_rejected")

    assert handle.is_finished is True
    assert handle.outcome is outcomes[0]
    assert outcomes[0].result is None
    assert outcomes[0].error is error
    assert outcomes[0].cancelled is False


def _request(
    *,
    work: Callable[[PromptEditorCancellationToken], int],
) -> PromptAsyncRequest[int]:
    """Create one deterministic prompt-editor async request."""

    return PromptAsyncRequest(
        identity=PromptAsyncResultIdentity(request_id=1),
        context=PromptAsyncRequestContext(
            operation="task_executor_test", reason="unit"
        ),
        work=work,
    )


def _record_outcome(
    outcomes: list[PromptAsyncTaskOutcome[int]],
    outcome: PromptAsyncTaskOutcome[int],
    event: Event,
) -> None:
    """Record one outcome and notify the waiting test thread."""

    outcomes.append(outcome)
    event.set()


class _RecordingDispatcher:
    """Synchronously record dispatcher publications for deterministic tests."""

    def __init__(self) -> None:
        """Create an empty recording dispatcher."""

        self.reasons: list[str] = []

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Record one publication reason and invoke the callback."""

        self.reasons.append(reason)
        callback()


class _RejectingSubmitter:
    """Raise a configured error for task-executor backpressure tests."""

    def __init__(self, error: RuntimeError) -> None:
        """Store the error raised for every submission."""

        self._error = error

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> TaskHandle[TResult]:
        """Raise the configured submission error."""

        _ = request, cancellation
        raise self._error


@dataclass(frozen=True, slots=True)
class _Token:
    """Provide the cancellation-token protocol for task-executor tests."""

    generation: int = 0
    is_cancelled: bool = False
    reason: str | None = None
