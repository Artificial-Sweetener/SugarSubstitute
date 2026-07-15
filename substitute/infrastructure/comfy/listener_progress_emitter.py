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

"""Emit listener progress callbacks with prompt-safe estimator tracing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.ports.comfy_gateway import ProgressUpdate
from substitute.domain.common import WorkflowId
from substitute.infrastructure.comfy.comfy_websocket_event_router import (
    WebsocketProgressEmission,
)


class ListenerProgressTrace(Protocol):
    """Describe trace behavior required for listener progress emission."""

    def trace_estimator_progress(
        self,
        *,
        source_event: str,
        prompt_id: str,
        workflow_percent: float | None,
        sampler_percent: float | None,
    ) -> None:
        """Trace one app-side progress estimate."""


@dataclass(frozen=True)
class ListenerProgressContext:
    """Describe generation identity attached to progress callbacks."""

    workflow_id: WorkflowId
    generation_run_id: str
    prompt_id: str
    client_id: str


def emit_listener_progress(
    *,
    context: ListenerProgressContext,
    trace: ListenerProgressTrace,
    source_event: str,
    workflow_percent: float | None,
    sampler_percent: float | None,
    on_progress: Callable[[ProgressUpdate], None],
) -> None:
    """Trace and emit one listener progress callback."""

    trace.trace_estimator_progress(
        source_event=source_event,
        prompt_id=context.prompt_id,
        workflow_percent=workflow_percent,
        sampler_percent=sampler_percent,
    )
    on_progress(
        ProgressUpdate(
            workflow_id=context.workflow_id,
            generation_run_id=context.generation_run_id,
            prompt_id=context.prompt_id,
            client_id=context.client_id,
            workflow_percent=workflow_percent,
            sampler_percent=sampler_percent,
        )
    )


@dataclass(frozen=True)
class ListenerProgressEmitter:
    """Emit routed listener progress updates for one listener run."""

    context: ListenerProgressContext
    trace: ListenerProgressTrace
    on_progress: Callable[[ProgressUpdate], None]

    def emit(self, progress: WebsocketProgressEmission) -> None:
        """Trace and dispatch one routed progress update."""

        emit_listener_progress(
            context=self.context,
            trace=self.trace,
            source_event=progress.source_event,
            workflow_percent=progress.workflow_percent,
            sampler_percent=progress.sampler_percent,
            on_progress=self.on_progress,
        )


__all__ = [
    "ListenerProgressContext",
    "ListenerProgressEmitter",
    "ListenerProgressTrace",
    "emit_listener_progress",
]
