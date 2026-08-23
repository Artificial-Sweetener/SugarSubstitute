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

"""Provide deterministic execution-route doubles for cube-loader contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from substitute.application.execution import CancellationToken, TaskRequest
from tests.support.execution import ImmediateTaskSubmitter, ManualTaskHandle


class _QueuedSubmitter:
    """Queue execution requests until tests run them manually."""

    def __init__(self) -> None:
        """Create an empty execution queue."""

        self.items: list[
            tuple[TaskRequest[object], CancellationToken, ManualTaskHandle[object]]
        ] = []

    def submit(
        self,
        request: TaskRequest[object],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[object]:
        """Record one execution request without running it."""

        handle: ManualTaskHandle[object] = ManualTaskHandle(request)
        self.items.append((request, cancellation, handle))
        return handle

    def run_next(self) -> None:
        """Run the next queued request and publish its result."""

        request, cancellation, handle = self.items.pop(0)
        handle.complete_success(request.work(cancellation))


class _RejectingRouteFactory:
    """Create cube-load routes that reject one selected submit call."""

    def __init__(self, *, fail_on_call: int) -> None:
        """Create a route factory whose submitter fails on one call number."""

        self.submitter_instance = _RejectingRuntimeSubmitter(
            fail_on_call=fail_on_call,
            close_callback=self._record_close,
        )
        self.close_count = 0

    def route(self, module: Any) -> Any:
        """Return a route through the module's public route value."""

        return module.CubeLoadExecutionRoute(
            submitter=self.submitter_instance,
            close=self.submitter_instance.close,
        )

    def _record_close(self) -> None:
        """Record one owner-route close."""

        self.close_count += 1


class _RejectingRuntimeSubmitter:
    """Run immediate tasks until one configured submission is rejected."""

    def __init__(
        self,
        *,
        fail_on_call: int,
        close_callback: Callable[[], None],
    ) -> None:
        """Store failure and close behavior."""

        self._fail_on_call = fail_on_call
        self._close_callback = close_callback
        self._immediate = ImmediateTaskSubmitter()
        self._submit_count = 0
        self._closed = False

    def submit(
        self,
        request: TaskRequest[object],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[object]:
        """Submit immediately unless this call is configured to fail."""

        self._submit_count += 1
        if self._submit_count == self._fail_on_call:
            raise RuntimeError("execution lane rejected test task")
        return self._immediate.submit(request, cancellation=cancellation)

    def close(self) -> None:
        """Record close once."""

        if self._closed:
            return
        self._closed = True
        self._close_callback()


def _route_factory(
    module: Any,
    submitter: Any,
    close: Callable[[], None] | None = None,
) -> Callable[..., Any]:
    """Return a cube-load route factory for one test submitter."""

    def _factory(*, cube_load_trace_id: str) -> Any:
        """Create a route for one cube-load request."""

        _ = cube_load_trace_id
        return module.CubeLoadExecutionRoute(
            submitter=submitter,
            close=close or (lambda: None),
        )

    return _factory


def _with_submitter(module: Any, callbacks: Any, submitter: _QueuedSubmitter) -> Any:
    """Return callbacks that use the queued test submitter."""

    return replace(
        callbacks,
        cube_load_execution_route_factory=_route_factory(module, submitter),
    )
