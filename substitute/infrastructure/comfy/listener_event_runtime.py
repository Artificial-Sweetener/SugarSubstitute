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

"""Build run-scoped Comfy listener event routing collaborators."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, cast

from substitute.application.generation.progress_estimation import (
    ComfyWorkflowProgressTracker,
)
from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerStartRequest,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.comfy_execution_timing import (
    ComfyExecutionTimingEmitter,
    ComfyExecutionTimingTracker,
    TimingSourceIdentity,
)
from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    ModelLoadSourceMetadataResolver,
)
from substitute.infrastructure.comfy.comfy_websocket_event_router import (
    ComfyWebsocketEventRouter,
    CubeOutputMessageHandler,
)
from substitute.infrastructure.comfy.listener_progress_emitter import (
    ListenerProgressContext,
    ListenerProgressEmitter,
)
from substitute.infrastructure.comfy.runtime_report_context import (
    fetch_runtime_report_context,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    typed_prompt_nodes,
)
from substitute.infrastructure.comfy.websocket_listener_engine import (
    ListenerEngineCallbacks,
)
from substitute.infrastructure.comfy.websocket_trace import ComfyWebsocketTrace


class ListenerEventRuntimeTrace(Protocol):
    """Describe trace behavior used by listener event runtime callbacks."""

    def trace_message(
        self,
        *,
        message: dict[str, object],
        active_prompt_id: str,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Trace one parsed websocket text message."""

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
class ListenerEventRuntime:
    """Carry event-routing collaborators for one listener run."""

    all_node_ids: set[str]
    timing_emitter: ComfyExecutionTimingEmitter
    json_event_router: ComfyWebsocketEventRouter
    engine_callbacks: ListenerEngineCallbacks


def build_listener_event_runtime(
    *,
    request: ListenerStartRequest,
    callbacks: ListenerCallbacks,
    endpoint: ComfyEndpoint,
    progress_context: ListenerProgressContext,
    source_identity_resolver: Callable[[str], TimingSourceIdentity],
    source_metadata_resolver: ModelLoadSourceMetadataResolver,
    cube_output_handler: CubeOutputMessageHandler,
    trace_factory: Callable[[], ListenerEventRuntimeTrace] = (
        ComfyWebsocketTrace.from_environment
    ),
    clock_ms: Callable[[], float] | None = None,
) -> ListenerEventRuntime:
    """Build prompt-scoped routing, timing, trace, and progress collaborators."""

    timing_clock = clock_ms or _perf_counter_ms
    prompt_nodes = typed_prompt_nodes(request.workflow_payload)
    trace = trace_factory()
    trace_prompt_nodes = cast(dict[str, object], prompt_nodes)
    all_node_ids = {str(node_id) for node_id in prompt_nodes}
    timing_tracker = ComfyExecutionTimingTracker(
        workflow_id=request.workflow_id,
        prompt_id=request.prompt_id,
        clock_ms=timing_clock,
    )
    timing_emitter = ComfyExecutionTimingEmitter(
        tracker=timing_tracker,
        on_timing=callbacks.on_timing,
    )
    progress_emitter = ListenerProgressEmitter(
        context=progress_context,
        trace=trace,
        on_progress=callbacks.on_progress,
    )
    json_event_router = ComfyWebsocketEventRouter(
        workflow_id=request.workflow_id,
        active_prompt_id=request.prompt_id,
        all_node_ids=all_node_ids,
        prompt_nodes=trace_prompt_nodes,
        timing_tracker=timing_tracker,
        progress_tracker=ComfyWorkflowProgressTracker.from_prompt(prompt_nodes),
        source_identity_resolver=source_identity_resolver,
        source_metadata_resolver=source_metadata_resolver,
        cube_output_handler=cube_output_handler,
        runtime_context_provider=lambda: fetch_runtime_report_context(endpoint),
        on_model_load_progress=callbacks.on_model_load_progress,
    )
    engine_callbacks = ListenerEngineCallbacks(
        on_text_message=lambda message: _trace_text_message(
            trace=trace,
            message=message,
            active_prompt_id=request.prompt_id,
            prompt_nodes=trace_prompt_nodes,
        ),
        on_progress=progress_emitter.emit,
    )
    return ListenerEventRuntime(
        all_node_ids=all_node_ids,
        timing_emitter=timing_emitter,
        json_event_router=json_event_router,
        engine_callbacks=engine_callbacks,
    )


def _trace_text_message(
    *,
    trace: ListenerEventRuntimeTrace,
    message: Mapping[str, object],
    active_prompt_id: str,
    prompt_nodes: dict[str, object],
) -> None:
    """Trace one parsed text message with prompt-node context."""

    trace.trace_message(
        message=dict(message),
        active_prompt_id=active_prompt_id,
        prompt_nodes=prompt_nodes,
    )


def _perf_counter_ms() -> float:
    """Return monotonic wall-clock milliseconds for listener timing."""

    return perf_counter() * 1000.0


__all__ = [
    "ListenerEventRuntime",
    "ListenerEventRuntimeTrace",
    "build_listener_event_runtime",
]
