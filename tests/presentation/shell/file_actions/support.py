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

"""Provide workspace file action test support."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace
from typing import TypeVar, cast

from substitute.application.execution import CancellationToken
from substitute.application.execution.executor import TaskRequest
from tests.support.execution import ManualTaskHandle

ValueT = TypeVar("ValueT")
ReturnT = TypeVar("ReturnT")
TaskResultT = TypeVar("TaskResultT")


def _import_module() -> ModuleType:
    """Import the workspace file actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_file_actions"
    )


def _append(values: list[ValueT], value: ValueT) -> None:
    """Append one value from callback doubles that should return None."""

    values.append(value)


def _append_then(
    values: list[ValueT],
    value: ValueT,
    result: ReturnT,
) -> ReturnT:
    """Append one callback value and return the requested test double result."""

    values.append(value)
    return result


class _EditorBusyRecorder:
    """Record editor busy controller calls for file action tests."""

    def __init__(self, calls: list[object] | None = None) -> None:
        """Store the optional call list."""

        self._calls = calls

    def begin(self, workflow_id: str, *, message: str = "Loading") -> object:
        """Record a begin request and return a stable token."""

        if self._calls is not None:
            self._calls.append(("begin", (workflow_id, message)))
        return "busy-token"

    def end(self, token: object) -> None:
        """Record an end request."""

        if self._calls is not None:
            self._calls.append(("end", token))

    def set_cancel_callback(self, _token: object, _callback: object) -> None:
        """Accept cancel callback updates for download tests."""

    def update_download(self, _token: object, _state: object) -> None:
        """Accept download progress updates for download tests."""


class _QueuedRuntimeSubmitter:
    """Capture one runtime task for deterministic completion in tests."""

    def __init__(self) -> None:
        """Create empty submission state."""

        self.requests: list[TaskRequest[object]] = []
        self.handles: list[ManualTaskHandle[object]] = []
        self.cancellations: list[CancellationToken] = []
        self.closed = False

    def submit(
        self,
        request: TaskRequest[TaskResultT],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TaskResultT]:
        """Queue one request and return a manual handle."""

        handle: ManualTaskHandle[TaskResultT] = ManualTaskHandle(request)
        self.requests.append(cast(TaskRequest[object], request))
        self.handles.append(cast(ManualTaskHandle[object], handle))
        self.cancellations.append(cancellation)
        return handle

    def close(self) -> None:
        """Record route closure."""

        self.closed = True


class _QueuedExecutionRuntime:
    """Expose the submitter factory shape used by production runtime."""

    def __init__(self, submitter: _QueuedRuntimeSubmitter) -> None:
        """Store the submitter returned to action code."""

        self.submitter_instance = submitter
        self.calls: list[tuple[str, str, object]] = []

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> _QueuedRuntimeSubmitter:
        """Record runtime route creation."""

        self.calls.append((name, owner_id, dispatcher))
        return self.submitter_instance


def _noop_output_registrar() -> object:
    """Return an Output registrar double for tests that do not restore outputs."""

    return SimpleNamespace(add_output_image=lambda *_args: None)


def _recipe_output_registrar(
    added_outputs: list[tuple[str, object, object]],
) -> object:
    """Return an Output registrar double for recipe-output tests."""

    return SimpleNamespace(
        add_output_image=lambda workflow_id, image, image_meta: added_outputs.append(
            (workflow_id, image, image_meta)
        )
    )


class _TabItem:
    """Workflow-tab item double with mutable text and route key."""

    def __init__(self, route_key: str, text: str) -> None:
        self._route_key = route_key
        self._text = text

    def routeKey(self) -> str:
        """Return the current route key."""

        return self._route_key

    def text(self) -> str:
        """Return the current tab text."""

        return self._text

    def setText(self, text: str) -> None:
        """Record tab text updates."""

        self._text = text


class _CubeStack:
    """Cube-stack double tracking placeholder tab insertion."""

    def __init__(self) -> None:
        self.items: list[object] = []
        self.cleared = 0
        self.current_indices: list[int] = []

    def count(self) -> int:
        """Return current item count."""

        return len(self.items)

    def clear(self) -> None:
        """Record clear operations."""

        self.cleared += 1
        self.items.clear()

    def insertTab(self, index: int, **kwargs: object) -> object:
        """Insert and return a placeholder tab item."""

        item = SimpleNamespace(index=index, kwargs=kwargs)
        self.items.insert(index, item)
        return item

    def setCurrentIndex(self, index: int) -> None:
        """Record current-index updates."""

        self.current_indices.append(index)


class _EditorPanel:
    """Editor-panel double tracking clear-layout calls."""

    def __init__(self) -> None:
        self.clear_calls = 0

    def clear_layout(self) -> None:
        """Record layout clearing."""

        self.clear_calls += 1
