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

"""Test helpers for runtime-backed prompt-editor execution adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from PySide6.QtWidgets import QWidget

from substitute.application.execution import CancellationToken, TaskHandle, TaskRequest
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.infrastructure.execution import ThreadPoolExecutionLane
from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    QtDanbooruWikiLookupDispatcher,
)
from substitute.presentation.editor.panel.service_bundle import (
    EditorPanelExecutionFactories,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorTaskExecutor,
)
from substitute.presentation.widgets.model_picker import (
    ModelPickerThumbnailPreloadRoute,
)

TResult = TypeVar("TResult")


class TestCompletionDispatcher(Protocol):
    """Publish task completions in prompt execution tests."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Publish one completion callback."""


def prompt_task_executor(
    *,
    dispatcher: TestCompletionDispatcher,
    max_workers: int = 1,
    queue_capacity: int | None = 32,
    name: str = "prompt_editor_test",
) -> PromptEditorTaskExecutor:
    """Build a prompt task executor over the shared thread-pool lane."""

    lane = ThreadPoolExecutionLane(
        name=name,
        max_workers=max_workers,
        queue_capacity=queue_capacity,
        thread_name_prefix=name.replace("_", "-"),
        dispatcher=dispatcher,
    )
    return PromptEditorTaskExecutor(
        submitter=lane,
        shutdown_callback=lambda: lane.shutdown(wait=False, cancel_futures=True),
    )


def immediate_prompt_task_executor_factory() -> Callable[
    [object, str], PromptEditorTaskExecutor
]:
    """Return a prompt executor factory backed by immediate task execution."""

    def create_executor(_owner: object, _owner_id: str) -> PromptEditorTaskExecutor:
        """Create one immediate prompt executor for direct widget tests."""

        return PromptEditorTaskExecutor(
            submitter=ImmediateTaskSubmitter(),
            shutdown_callback=lambda: None,
        )

    return create_executor


def immediate_editor_panel_execution_factories() -> EditorPanelExecutionFactories:
    """Return immediate execution factories for direct editor-panel tests."""

    def create_danbooru_dispatcher(parent: QWidget) -> QtDanbooruWikiLookupDispatcher:
        """Create one immediate Danbooru lookup dispatcher."""

        return QtDanbooruWikiLookupDispatcher(
            parent,
            submitter=ImmediateTaskSubmitter(),
            close_submitter=lambda: None,
        )

    def create_thumbnail_route(_receiver: QWidget) -> ModelPickerThumbnailPreloadRoute:
        """Create one immediate model-picker thumbnail route."""

        return ModelPickerThumbnailPreloadRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
        )

    return EditorPanelExecutionFactories(
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
        danbooru_lookup_dispatcher_factory=create_danbooru_dispatcher,
        model_picker_thumbnail_preload_route_factory=create_thumbnail_route,
    )


class ExecutionRuntimeStub:
    """Expose the execution-runtime submitter API for prompt-editor tests."""

    def __init__(self) -> None:
        """Initialize owned submitters."""

        self.submitter_requests: list[tuple[str, str, object]] = []
        self.closed_count = 0
        self._close_callbacks: list[Callable[[], None]] = []

    def submitter(
        self,
        lane_name: str,
        *,
        owner_id: str,
        dispatcher: TestCompletionDispatcher,
    ) -> _RuntimeSubmitter:
        """Return a closeable submitter for one runtime owner."""

        self.submitter_requests.append((lane_name, owner_id, dispatcher))
        lane = ThreadPoolExecutionLane(
            name=f"{lane_name}_{len(self.submitter_requests)}",
            max_workers=1,
            queue_capacity=32,
            thread_name_prefix=f"{lane_name}-test",
            dispatcher=dispatcher,
        )

        def close() -> None:
            """Close the lane and record runtime ownership release."""

            lane.shutdown(wait=False, cancel_futures=True)
            self.closed_count += 1

        self._close_callbacks.append(close)
        return _RuntimeSubmitter(lane=lane, close_callback=close)

    def close_all(self) -> None:
        """Close all submitters that remain open."""

        for close in tuple(self._close_callbacks):
            close()
        self._close_callbacks.clear()


class _RuntimeSubmitter:
    """Wrap a thread-pool lane with the runtime submitter close API."""

    def __init__(
        self,
        *,
        lane: ThreadPoolExecutionLane,
        close_callback: Callable[[], None],
    ) -> None:
        """Store the lane and close callback."""

        self._lane = lane
        self._close_callback = close_callback

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Submit one request through the underlying lane."""

        return self._lane.submit(request, cancellation=cancellation)

    def close(self) -> None:
        """Release the underlying lane."""

        self._close_callback()


class ImmediateExecutionRuntimeStub:
    """Expose the execution-runtime API with synchronous test execution."""

    def __init__(self) -> None:
        """Initialize request and close accounting."""

        self.submitter_requests: list[tuple[str, str, object]] = []
        self.closed_count = 0

    def submitter(
        self,
        lane_name: str,
        *,
        owner_id: str,
        dispatcher: TestCompletionDispatcher,
    ) -> _ImmediateRuntimeSubmitter:
        """Return a closeable synchronous submitter for one runtime owner."""

        _ = dispatcher
        self.submitter_requests.append((lane_name, owner_id, dispatcher))
        return _ImmediateRuntimeSubmitter(close_callback=self._record_close)

    def _record_close(self) -> None:
        """Record release of one runtime submitter."""

        self.closed_count += 1


class _ImmediateRuntimeSubmitter:
    """Wrap the immediate test submitter with the runtime close API."""

    def __init__(self, *, close_callback: Callable[[], None]) -> None:
        """Store submitter and close callback."""

        self._submitter = ImmediateTaskSubmitter()
        self._close_callback = close_callback
        self._is_closed = False

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Run one request synchronously."""

        if self._is_closed:
            raise RuntimeError("immediate runtime submitter is closed.")
        return self._submitter.submit(request, cancellation=cancellation)

    def close(self) -> None:
        """Release this no-thread test submitter once."""

        if self._is_closed:
            return
        self._is_closed = True
        self._close_callback()
