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

"""Verify Danbooru import dispatcher teardown behavior."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar, cast

from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete, isValid

from substitute.application.danbooru import DanbooruPromptImportResult
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
    QtDanbooruUrlImportDispatcher,
)

TResult = TypeVar("TResult")


class _DanbooruTaskHandle(Generic[TResult]):
    """Expose one controllable async task handle for dispatcher tests."""

    def __init__(self, request: PromptAsyncRequest[TResult]) -> None:
        """Store the async request and completion callbacks."""

        self._request = request
        self._callbacks: list[Callable[[PromptAsyncTaskOutcome[TResult]], None]] = []
        self._outcome: PromptAsyncTaskOutcome[TResult] | None = None
        self.cancel_reasons: list[str] = []

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the submitted request identity."""

        return self._request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether a terminal outcome was supplied."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult] | None:
        """Return the terminal outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Record one completion callback."""

        _ = reason
        self._callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record task cancellation."""

        self.cancel_reasons.append(reason)

    def complete(self, result: TResult) -> None:
        """Publish one successful completion."""

        self._outcome = PromptAsyncTaskOutcome(
            identity=self.identity, context=self._request.context, result=result
        )
        for callback in tuple(self._callbacks):
            callback(self._outcome)
        self._callbacks.clear()


class _DanbooruExecutor:
    """Record Danbooru async requests without background work."""

    def __init__(self) -> None:
        """Initialize submitted request tracking."""

        self.handles: list[_DanbooruTaskHandle[DanbooruPromptImportResult]] = []
        self.cancellations: list[PromptEditorCancellationToken] = []

    def submit(
        self,
        request: PromptAsyncRequest[DanbooruPromptImportResult],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[DanbooruPromptImportResult]:
        """Record and return one controllable task handle."""

        handle = _DanbooruTaskHandle(request)
        self.handles.append(handle)
        self.cancellations.append(cancellation)
        return cast(PromptEditorTaskHandle[DanbooruPromptImportResult], handle)


def test_dispatcher_drops_completion_after_parent_deleted() -> None:
    """Danbooru task completion must not publish after Qt teardown."""

    app = QApplication.instance() or QApplication([])
    _ = app
    parent = QWidget()
    executor = _DanbooruExecutor()
    completed: list[DanbooruPromptImportResult] = []
    failed: list[BaseException] = []
    dispatcher = QtDanbooruUrlImportDispatcher(
        parent, is_alive=isValid, executor=cast(PromptEditorExecutor, executor)
    )
    dispatcher.submit(
        lambda: DanbooruPromptImportResult(imported_prompt=None),
        completed=completed.append,
        failed=failed.append,
    )
    delete(parent)
    executor.handles[0].complete(DanbooruPromptImportResult(imported_prompt=None))
    assert completed == []
    assert failed == []
    assert executor.handles[0].cancel_reasons == ["danbooru_url_import_shutdown"]
    assert executor.cancellations[0].is_cancelled is True
