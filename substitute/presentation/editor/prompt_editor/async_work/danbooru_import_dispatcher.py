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

"""Dispatch Danbooru URL import lookups through the prompt-editor async boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QObject

from substitute.application.danbooru import DanbooruPromptImportResult

from .cancellation import (
    PromptEditorCancellationController,
    PromptEditorCancellationSource,
)
from .execution import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
)
from .main_thread_dispatcher import (
    PromptEditorMainThreadDispatcher,
    QtPromptEditorMainThreadDispatcher,
)
from .task_executor import PromptEditorTaskExecutor

_DANBOORU_IMPORT_OPERATION = "danbooru_url_import"
_DANBOORU_IMPORT_COMPLETION_REASON = "danbooru_url_import_completed"


class QtDanbooruUrlImportDispatcher:
    """Resolve Danbooru URL imports through prompt async execution."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        is_alive: Callable[[QObject], bool] | None = None,
        executor: PromptEditorExecutor | None = None,
        dispatcher: PromptEditorMainThreadDispatcher | None = None,
    ) -> None:
        """Create a dispatcher bound to the prompt editor host lifetime."""

        self._is_alive = is_alive
        self._parent = parent
        self._dispatcher = dispatcher or QtPromptEditorMainThreadDispatcher(parent)
        if executor is None:
            raise TypeError("executor is required for Danbooru URL import dispatch.")
        self._executor = executor
        self._owns_executor = isinstance(self._executor, PromptEditorTaskExecutor)
        self._cancellation_controller = PromptEditorCancellationController()
        self._next_request_id = 0
        self._is_shutdown = False
        self._callbacks: dict[
            int,
            tuple[
                Callable[[DanbooruPromptImportResult], None],
                Callable[[BaseException], None],
            ],
        ] = {}
        self._handles: dict[
            int,
            PromptEditorTaskHandle[DanbooruPromptImportResult],
        ] = {}
        self._cancellations: dict[int, PromptEditorCancellationSource] = {}
        if parent is not None:
            parent.destroyed.connect(self.shutdown)

    def submit(
        self,
        lookup: Callable[[], DanbooruPromptImportResult],
        *,
        completed: Callable[[DanbooruPromptImportResult], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Run one Danbooru import lookup without blocking the GUI thread."""

        if self._is_shutdown or not self._parent_is_alive():
            return
        self._next_request_id += 1
        request_id = self._next_request_id
        self._callbacks[request_id] = (completed, failed)
        cancellation = self._cancellation_controller.next_source()
        request = PromptAsyncRequest(
            identity=PromptAsyncResultIdentity(
                request_id=request_id,
                cancellation_generation=cancellation.generation,
            ),
            context=PromptAsyncRequestContext(
                operation=_DANBOORU_IMPORT_OPERATION,
                reason="paste_import",
            ),
            work=lambda _token: lookup(),
        )
        handle = self._executor.submit(request, cancellation=cancellation)
        self._handles[request_id] = handle
        self._cancellations[request_id] = cancellation
        handle.add_done_callback(
            self._deliver_outcome,
            reason=_DANBOORU_IMPORT_COMPLETION_REASON,
        )

    def shutdown(self, *_args: object) -> None:
        """Cancel pending Danbooru imports when the editor host is destroyed."""

        if self._is_shutdown:
            return
        self._is_shutdown = True
        self._callbacks.clear()
        for cancellation in tuple(self._cancellations.values()):
            cancellation.cancel(reason="danbooru_url_import_shutdown")
        for handle in tuple(self._handles.values()):
            handle.cancel(reason="danbooru_url_import_shutdown")
        self._handles.clear()
        self._cancellations.clear()
        if self._owns_executor:
            cast(PromptEditorTaskExecutor, self._executor).shutdown(
                wait=False,
                cancel_futures=True,
            )

    def _deliver_outcome(
        self,
        outcome: PromptAsyncTaskOutcome[DanbooruPromptImportResult],
    ) -> None:
        """Deliver one Danbooru import completion on the GUI thread."""

        request_id = outcome.identity.request_id
        self._handles.pop(request_id, None)
        self._cancellations.pop(request_id, None)
        callbacks = self._callbacks.pop(request_id, None)
        if callbacks is None or self._is_shutdown or not self._parent_is_alive():
            return
        completed, failed = callbacks
        if outcome.cancelled:
            return
        if outcome.error is not None:
            failed(outcome.error)
            return
        if outcome.result is None:
            failed(RuntimeError("Danbooru URL import completed without a result."))
            return
        completed(outcome.result)

    def _parent_is_alive(self) -> bool:
        """Return whether the optional Qt parent can still receive results."""

        if self._parent is None or self._is_alive is None:
            return True
        return self._is_alive(self._parent)


__all__ = [
    "QtDanbooruUrlImportDispatcher",
]
