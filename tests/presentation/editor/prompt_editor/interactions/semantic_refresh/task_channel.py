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

"""Provide controllable semantic task and request-channel doubles."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorTaskHandle,
    PromptSemanticRefreshResult,
)


class FakeSemanticTaskHandle(PromptEditorTaskHandle[PromptSemanticRefreshResult]):
    """Store one semantic async request until a test completes it."""

    def __init__(
        self,
        request: PromptAsyncRequest[PromptSemanticRefreshResult],
    ) -> None:
        """Store the request and callback list."""

        self.request = request
        self.cancel_calls: list[str] = []
        self.callbacks: list[
            Callable[[PromptAsyncTaskOutcome[PromptSemanticRefreshResult]], None]
        ] = []
        self._outcome: PromptAsyncTaskOutcome[PromptSemanticRefreshResult] | None = None

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self.request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether the fake task has completed."""

        return self._outcome is not None

    @property
    def outcome(
        self,
    ) -> PromptAsyncTaskOutcome[PromptSemanticRefreshResult] | None:
        """Return the completed outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[PromptSemanticRefreshResult]], None],
        *,
        reason: str,
    ) -> None:
        """Record a completion callback."""

        _ = reason
        if self._outcome is not None:
            callback(self._outcome)
            return
        self.callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation without preventing explicit test completion."""

        self.cancel_calls.append(reason)

    def run_work(self) -> None:
        """Execute request work and publish one fake task outcome."""

        try:
            result = self.request.work(_Token())
        except BaseException as error:  # noqa: BLE001
            self.complete(error=error)
            return
        self.complete(result=result)

    def complete(
        self,
        *,
        result: PromptSemanticRefreshResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Publish a fake async task outcome to all callbacks."""

        self._outcome = PromptAsyncTaskOutcome(
            identity=self.request.identity,
            context=self.request.context,
            result=result,
            error=error,
        )
        callbacks = tuple(self.callbacks)
        self.callbacks.clear()
        for callback in callbacks:
            callback(self._outcome)


class _Token:
    """Provide a never-cancelled token for semantic interaction tests."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class FakeSemanticRequestChannel:
    """Record semantic async requests and return controllable fake handles."""

    def __init__(self) -> None:
        """Initialize request and cancellation tracking."""

        self.handles: list[FakeSemanticTaskHandle] = []
        self.cancel_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[PromptSemanticRefreshResult],
    ) -> FakeSemanticTaskHandle:
        """Store the latest semantic request for deterministic completion."""

        handle = FakeSemanticTaskHandle(request)
        self.handles.append(handle)
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Record request-channel cancellation."""

        self.cancel_reasons.append(reason)
