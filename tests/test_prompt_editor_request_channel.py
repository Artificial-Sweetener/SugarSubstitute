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

"""Contract tests for prompt-editor latest-wins request channels."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

import pytest

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
    PromptLatestWinsRequestChannel,
)

TResult = TypeVar("TResult")


def test_latest_wins_channel_stamps_generation_and_submits_request() -> None:
    """submit_latest should tie request identity to a cancellation generation."""

    executor: _RecordingExecutor[int] = _RecordingExecutor()
    channel: PromptLatestWinsRequestChannel[int] = PromptLatestWinsRequestChannel(
        executor=cast(PromptEditorExecutor, executor),
    )

    channel.submit_latest(_request(request_id=1, result=7))
    handle = executor.handles[0]

    assert handle is executor.handles[0]
    assert executor.requests[0].identity.cancellation_generation == 1
    assert executor.tokens[0].generation == 1
    assert executor.tokens[0].is_cancelled is False
    assert channel.active_handle is handle


def test_latest_wins_channel_cancels_previous_request_on_new_submit() -> None:
    """A newer request should cancel the older source and handle."""

    executor: _RecordingExecutor[int] = _RecordingExecutor()
    channel: PromptLatestWinsRequestChannel[int] = PromptLatestWinsRequestChannel(
        executor=cast(PromptEditorExecutor, executor),
    )

    channel.submit_latest(_request(request_id=1, result=1))
    second = channel.submit_latest(_request(request_id=2, result=2))
    first = executor.handles[0]

    assert executor.tokens[0].is_cancelled is True
    assert executor.tokens[0].reason == "superseded_by_latest_request"
    assert first.cancel_reasons == ["superseded_by_latest_request"]
    assert executor.requests[1].identity.cancellation_generation == 2
    assert channel.active_handle is second


def test_latest_wins_channel_cancel_pending_clears_active_request() -> None:
    """cancel_pending should cancel and clear the active handle."""

    executor: _RecordingExecutor[int] = _RecordingExecutor()
    channel: PromptLatestWinsRequestChannel[int] = PromptLatestWinsRequestChannel(
        executor=cast(PromptEditorExecutor, executor),
    )

    channel.submit_latest(_request(request_id=1, result=1))
    handle = executor.handles[0]
    channel.cancel_pending(reason="editor_closed")

    assert executor.tokens[0].is_cancelled is True
    assert executor.tokens[0].reason == "editor_closed"
    assert handle.cancel_reasons == ["editor_closed"]
    assert channel.active_handle is None


def test_latest_wins_channel_ignores_stale_handle_completion() -> None:
    """Older handle completion must not clear a newer active request."""

    executor: _RecordingExecutor[int] = _RecordingExecutor()
    channel: PromptLatestWinsRequestChannel[int] = PromptLatestWinsRequestChannel(
        executor=cast(PromptEditorExecutor, executor),
    )

    channel.submit_latest(_request(request_id=1, result=1))
    second = channel.submit_latest(_request(request_id=2, result=2))
    first = executor.handles[0]
    second_fake = executor.handles[1]

    first.complete()

    assert channel.active_handle is second

    second_fake.complete()

    assert channel.active_handle is None


def test_latest_wins_channel_rejects_blank_cancel_reason() -> None:
    """Cancel reasons should be explicit and prompt-safe."""

    channel: PromptLatestWinsRequestChannel[int] = PromptLatestWinsRequestChannel(
        executor=cast(PromptEditorExecutor, _RecordingExecutor[int]()),
    )

    with pytest.raises(ValueError, match="reason"):
        channel.cancel_pending(reason=" ")


def _request(*, request_id: int, result: int) -> PromptAsyncRequest[int]:
    """Create one deterministic request-channel request."""

    return PromptAsyncRequest(
        identity=PromptAsyncResultIdentity(request_id=request_id),
        context=PromptAsyncRequestContext(operation="request_channel", reason="unit"),
        work=lambda _token: result,
    )


class _RecordingExecutor(Generic[TResult]):
    """Record submitted requests and return controllable handles."""

    def __init__(self) -> None:
        """Create an empty executor test double."""

        self.requests: list[PromptAsyncRequest[TResult]] = []
        self.tokens: list[PromptEditorCancellationToken] = []
        self.handles: list[_FakeHandle[TResult]] = []

    def submit(
        self,
        request: PromptAsyncRequest[TResult],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[TResult]:
        """Record one request and return a fake handle."""

        handle: _FakeHandle[TResult] = _FakeHandle(request=request)
        self.requests.append(request)
        self.tokens.append(cancellation)
        self.handles.append(handle)
        return handle


@dataclass(slots=True)
class _DoneCallback(Generic[TResult]):
    """Store one fake-handle completion callback."""

    callback: Callable[[PromptAsyncTaskOutcome[TResult]], None]
    reason: str


class _Token:
    """Provide a never-cancelled token for request-channel fake handles."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _FakeHandle(Generic[TResult]):
    """Provide a controllable task-handle test double."""

    def __init__(self, *, request: PromptAsyncRequest[TResult]) -> None:
        """Store request identity for this fake handle."""

        self._request = request
        self._outcome: PromptAsyncTaskOutcome[TResult] | None = None
        self.callbacks: list[_DoneCallback[TResult]] = []
        self.cancel_reasons: list[str] = []

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self._request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether complete has been called."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult] | None:
        """Return the fake completed outcome."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Record one completion callback."""

        self.callbacks.append(_DoneCallback(callback=callback, reason=reason))

    def cancel(self, *, reason: str) -> None:
        """Record one cancellation request."""

        self.cancel_reasons.append(reason)

    def complete(self) -> None:
        """Complete this fake handle and invoke recorded callbacks."""

        outcome = PromptAsyncTaskOutcome(
            identity=self._request.identity,
            context=self._request.context,
            result=self._request.work(_Token()),
        )
        self._outcome = outcome
        for callback in self.callbacks:
            callback.callback(outcome)
