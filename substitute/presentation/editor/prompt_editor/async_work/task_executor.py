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

"""Adapt prompt-editor async requests onto the shared execution submitter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar

from substitute.shared.logging.logger import get_logger, log_warning

from substitute.application.execution import (
    TaskHandle,
    TaskOutcome,
    TaskSubmitter,
)

from .execution import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
    prompt_async_outcome_from_task,
    prompt_task_request_from_async,
)

TResult = TypeVar("TResult")
_LOGGER = get_logger("presentation.editor.prompt_editor.async_work.task_executor")


@dataclass(frozen=True, slots=True)
class PromptEditorTaskExecutorRoute:
    """Carry one closeable execution submitter for prompt-editor task work."""

    submitter: TaskSubmitter
    close: Callable[[], None]


class PromptEditorTaskExecutor(PromptEditorExecutor):
    """Submit prompt-editor work through the shared execution lane adapter."""

    def __init__(
        self,
        *,
        submitter: TaskSubmitter,
        shutdown_callback: Callable[[], None] | None = None,
    ) -> None:
        """Create a prompt-editor adapter over an injected execution submitter."""

        self._submitter = submitter
        self._shutdown_callback = shutdown_callback
        self._is_shutdown = False
        self._lock = Lock()

    def submit(
        self,
        request: PromptAsyncRequest[TResult],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[TResult]:
        """Submit one prompt request and return a prompt-shaped task handle."""

        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Prompt editor task executor is shut down.")
        generic_request = prompt_task_request_from_async(request)
        try:
            handle = self._submitter.submit(
                generic_request,
                cancellation=cancellation,
            )
        except RuntimeError as error:
            log_warning(
                _LOGGER,
                "Prompt editor task submission failed before execution.",
                operation=request.context.operation,
                reason=request.context.reason,
                request_id=request.identity.request_id,
                error=repr(error),
            )
            return _RejectedPromptEditorTaskHandle(
                request=request,
                error=error,
            )
        return _PromptEditorTaskHandleAdapter(
            request=request,
            handle=handle,
        )

    def shutdown(
        self,
        *,
        wait: bool = False,
        cancel_futures: bool = True,
    ) -> None:
        """Stop accepting prompt tasks and release the runtime submitter."""

        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
        _ = wait, cancel_futures
        if self._shutdown_callback is not None:
            self._shutdown_callback()


def build_prompt_editor_executor(
    *,
    route: PromptEditorTaskExecutorRoute,
) -> PromptEditorTaskExecutor:
    """Build a prompt executor from one composed execution route."""

    return PromptEditorTaskExecutor(
        submitter=route.submitter,
        shutdown_callback=route.close,
    )


class _PromptEditorTaskHandleAdapter(Generic[TResult]):
    """Convert shared execution outcomes back to prompt-editor outcomes."""

    def __init__(
        self,
        *,
        request: PromptAsyncRequest[TResult],
        handle: TaskHandle[TResult],
    ) -> None:
        """Store the prompt request and shared handle."""

        self._request = request
        self._handle = handle
        self._outcome: PromptAsyncTaskOutcome[TResult] | None = None
        self._lock = Lock()

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the prompt identity associated with this task."""

        return self._request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether the shared task has settled."""

        return bool(self._shared_handle.is_finished)

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult] | None:
        """Return the converted prompt outcome when available."""

        outcome = self._shared_handle.outcome
        if outcome is None:
            return None
        return self._prompt_outcome(outcome)

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Register one prompt-shaped completion callback."""

        _require_non_blank(reason, field_name="reason")
        self._shared_handle.add_done_callback(
            lambda outcome: callback(self._prompt_outcome(outcome)),
            reason=reason,
        )

    def cancel(self, *, reason: str) -> None:
        """Request cancellation of the shared task."""

        _require_non_blank(reason, field_name="reason")
        self._shared_handle.cancel(reason=reason)

    @property
    def _shared_handle(self) -> TaskHandle[TResult]:
        """Return the shared handle with the prompt result type."""

        return self._handle

    def _prompt_outcome(
        self,
        outcome: TaskOutcome[TResult],
    ) -> PromptAsyncTaskOutcome[TResult]:
        """Return the cached prompt outcome for one shared outcome."""

        with self._lock:
            if self._outcome is None:
                self._outcome = prompt_async_outcome_from_task(self._request, outcome)
            return self._outcome


class _RejectedPromptEditorTaskHandle(Generic[TResult]):
    """Represent prompt work rejected before it reached the execution lane."""

    def __init__(
        self,
        *,
        request: PromptAsyncRequest[TResult],
        error: BaseException,
    ) -> None:
        """Create an already-failed prompt task handle."""

        self._outcome: PromptAsyncTaskOutcome[TResult] = PromptAsyncTaskOutcome(
            identity=request.identity,
            context=request.context,
            error=error,
        )

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the rejected request identity."""

        return self._outcome.identity

    @property
    def is_finished(self) -> bool:
        """Return that rejected submissions are immediately settled."""

        return True

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult] | None:
        """Return the failed submission outcome."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Publish the failed outcome immediately."""

        _require_non_blank(reason, field_name="reason")
        callback(self._outcome)

    def cancel(self, *, reason: str) -> None:
        """Accept cancellation after rejection without changing the failure."""

        _require_non_blank(reason, field_name="reason")


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank task-executor labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "build_prompt_editor_executor",
    "PromptEditorTaskExecutorRoute",
    "PromptEditorTaskExecutor",
]
