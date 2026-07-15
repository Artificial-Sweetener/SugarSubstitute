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

"""Adapt prompt-editor latest-wins requests onto generic execution policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, Protocol, TypeVar, cast

from substitute.application.execution import (
    LatestWinsRequestChannel,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskSubmitter,
)

from .cancellation import PromptEditorCancellationController
from .execution import (
    PromptAsyncRequest,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
    prompt_async_context_from_execution,
    prompt_async_identity_from_task,
    prompt_task_outcome_from_async,
    prompt_task_request_from_async,
)

TResult = TypeVar("TResult")


class PromptEditorRequestChannel(Protocol, Generic[TResult]):
    """Submit prompt-editor async requests with channel-owned request policy."""

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> PromptEditorTaskHandle[TResult]:
        """Submit one request after cancelling any older active request."""

    def cancel_pending(self, *, reason: str) -> None:
        """Cancel any active request owned by this channel."""


class PromptLatestWinsRequestChannel(Generic[TResult]):
    """Submit only the latest prompt-editor async request as active."""

    def __init__(
        self,
        *,
        executor: PromptEditorExecutor,
        cancellation_controller: PromptEditorCancellationController | None = None,
    ) -> None:
        """Store a generic latest-wins channel behind prompt-shaped adapters."""

        self._channel: LatestWinsRequestChannel[TResult] = LatestWinsRequestChannel(
            submitter=_PromptChannelSubmitter(executor),
            cancellation_controller=cancellation_controller,
        )

    def submit_latest(
        self,
        request: PromptAsyncRequest[TResult],
    ) -> PromptEditorTaskHandle[TResult]:
        """Submit one request after cancelling the previous active handle."""

        generic_handle = self._channel.submit_latest(
            prompt_task_request_from_async(request)
        )
        return cast(_PromptChannelTaskHandle[TResult], generic_handle).prompt_handle

    def cancel_pending(self, *, reason: str) -> None:
        """Cancel the active source and handle with a prompt-safe reason."""

        self._channel.cancel_pending(reason=reason)

    @property
    def active_handle(self) -> PromptEditorTaskHandle[TResult] | None:
        """Return the currently active handle for tests and lifecycle adapters."""

        active_handle = self._channel.active_handle
        if active_handle is None:
            return None
        return cast(_PromptChannelTaskHandle[TResult], active_handle).prompt_handle


class _PromptChannelSubmitter(TaskSubmitter):
    """Submit generic channel requests through a prompt executor."""

    def __init__(self, executor: PromptEditorExecutor) -> None:
        """Store the prompt executor used by the channel."""

        self._executor = executor

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> TaskHandle[TResult]:
        """Convert one generic request into a prompt request and submit it."""

        prompt_request = PromptAsyncRequest(
            identity=prompt_async_identity_from_task(request.identity),
            context=prompt_async_context_from_execution(request.context),
            work=request.work,
        )
        prompt_handle = self._executor.submit(
            prompt_request,
            cancellation=cancellation,
        )
        return _PromptChannelTaskHandle(
            prompt_handle=prompt_handle,
            identity=request.identity,
            request=prompt_request,
            generic_request=request,
        )


class _PromptChannelTaskHandle(Generic[TResult]):
    """Expose a prompt task handle as a generic task handle for policy callbacks."""

    def __init__(
        self,
        *,
        prompt_handle: PromptEditorTaskHandle[TResult],
        identity: TaskIdentity,
        request: PromptAsyncRequest[TResult],
        generic_request: TaskRequest[TResult],
    ) -> None:
        """Store both prompt and generic request views."""

        self.prompt_handle = prompt_handle
        self._identity = identity
        self._request = request
        self._generic_request = generic_request

    @property
    def identity(self) -> TaskIdentity:
        """Return the generic execution identity."""

        return self._identity

    @property
    def is_finished(self) -> bool:
        """Return whether the prompt task has settled."""

        return self.prompt_handle.is_finished

    @property
    def outcome(self) -> TaskOutcome[TResult] | None:
        """Return the prompt outcome converted to generic execution form."""

        outcome = self.prompt_handle.outcome
        if outcome is None:
            return None
        return self._generic_outcome(outcome)

    @property
    def state(self) -> str:
        """Return coarse state for the generic task-handle protocol."""

        if self.prompt_handle.is_finished:
            return "finished"
        return "running"

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Register a generic completion callback on the prompt handle."""

        self.prompt_handle.add_done_callback(
            lambda outcome: callback(self._generic_outcome(outcome)),
            reason=reason,
        )

    def cancel(self, *, reason: str) -> None:
        """Request cancellation on the prompt task handle."""

        self.prompt_handle.cancel(reason=reason)

    def _generic_outcome(
        self,
        outcome: PromptAsyncTaskOutcome[TResult],
    ) -> TaskOutcome[TResult]:
        """Convert one prompt outcome into generic execution form."""

        return prompt_task_outcome_from_async(
            outcome,
            identity=self._identity,
            context=self._generic_request.context,
        )


__all__ = [
    "PromptEditorRequestChannel",
    "PromptLatestWinsRequestChannel",
]
