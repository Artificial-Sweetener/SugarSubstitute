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

"""Route parsed Comfy websocket JSON messages into listener actions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.application.errors import ErrorReport, RuntimeReportContext
from substitute.application.generation.progress_estimation import (
    ComfyWorkflowProgressTracker,
)
from substitute.application.ports.comfy_gateway import ModelLoadProgressUpdate
from substitute.domain.common import WorkflowId
from substitute.infrastructure.comfy.comfy_execution_timing import (
    ComfyExecutionTimingTracker,
    TimingSourceIdentity,
)
from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    ModelLoadSourceMetadataResolver,
)
from substitute.infrastructure.comfy.execution_error_mapper import (
    route_execution_error_event,
)
from substitute.infrastructure.comfy.executing_event_router import (
    route_executing_event,
)
from substitute.infrastructure.comfy.model_load_progress_event_router import (
    route_model_load_progress_event,
)
from substitute.infrastructure.comfy.node_execution_event_router import (
    route_node_execution_event,
)
from substitute.infrastructure.comfy.progress_event_router import (
    route_progress_event,
)
from substitute.infrastructure.comfy.progress_state_event_router import (
    route_progress_state_event,
)
from substitute.infrastructure.comfy.prompt_lifecycle_event_router import (
    route_prompt_lifecycle_event,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.comfy_websocket_event_router")


class CubeOutputMessageHandler(Protocol):
    """Describe cube-output handling needed by JSON websocket routing."""

    def handle(self, data: Mapping[str, object]) -> None:
        """Handle one parsed Substitute cube-output payload."""


@dataclass(frozen=True)
class WebsocketProgressEmission:
    """Describe one progress callback requested by JSON event routing."""

    source_event: str
    workflow_percent: float | None
    sampler_percent: float | None


@dataclass(frozen=True)
class WebsocketExecutionFailure:
    """Describe an execution failure routed from a JSON event."""

    message: str
    detail: str | None
    error_report: ErrorReport | None


@dataclass(frozen=True)
class WebsocketJsonRouteResult:
    """Describe listener actions selected for one parsed JSON message."""

    progress_emission: WebsocketProgressEmission | None = None
    failure: WebsocketExecutionFailure | None = None
    interrupted: bool = False
    prompt_finished: bool = False


class ComfyWebsocketEventRouter:
    """Own stateful routing for parsed Comfy websocket JSON messages."""

    def __init__(
        self,
        *,
        workflow_id: WorkflowId,
        active_prompt_id: str,
        all_node_ids: set[str],
        prompt_nodes: Mapping[str, object],
        timing_tracker: ComfyExecutionTimingTracker,
        progress_tracker: ComfyWorkflowProgressTracker,
        source_identity_resolver: Callable[[str], TimingSourceIdentity],
        source_metadata_resolver: ModelLoadSourceMetadataResolver,
        cube_output_handler: CubeOutputMessageHandler,
        runtime_context_provider: Callable[[], RuntimeReportContext],
        on_model_load_progress: Callable[[ModelLoadProgressUpdate], None],
    ) -> None:
        """Initialize routing context and mutable event-stream state."""

        self._workflow_id = workflow_id
        self._active_prompt_id = active_prompt_id
        self._all_node_ids = all_node_ids
        self._prompt_nodes = prompt_nodes
        self._timing_tracker = timing_tracker
        self._progress_tracker = progress_tracker
        self._source_identity_resolver = source_identity_resolver
        self._source_metadata_resolver = source_metadata_resolver
        self._cube_output_handler = cube_output_handler
        self._runtime_context_provider = runtime_context_provider
        self._on_model_load_progress = on_model_load_progress
        self._current_node: str | None = None
        self._progress_state_seen = False

    def route_message(
        self,
        *,
        message_type: object,
        data: Mapping[str, object],
    ) -> WebsocketJsonRouteResult:
        """Route one parsed text websocket message to listener actions."""

        prompt_lifecycle_route = route_prompt_lifecycle_event(
            message_type,
            data,
            active_prompt_id=self._active_prompt_id,
            timing_tracker=self._timing_tracker,
        )
        if prompt_lifecycle_route.interrupted:
            return WebsocketJsonRouteResult(interrupted=True)
        if prompt_lifecycle_route.handled:
            return WebsocketJsonRouteResult()

        progress_route = route_progress_event(
            message_type,
            data,
            active_prompt_id=self._active_prompt_id,
            all_node_ids=self._all_node_ids,
            prompt_nodes=self._prompt_nodes,
            progress_tracker=self._progress_tracker,
        )
        if progress_route.handled:
            if progress_route.unknown_node_id is not None:
                self._log_unknown_node(
                    "Ignoring progress for unknown Comfy node",
                    progress_route.unknown_node_id,
                )
                return WebsocketJsonRouteResult()
            if progress_route.emit_progress:
                return WebsocketJsonRouteResult(
                    progress_emission=self._progress_emission(
                        source_event="progress",
                        sampler_percent=progress_route.sampler_percent,
                    )
                )
            return WebsocketJsonRouteResult()

        progress_state_route = route_progress_state_event(
            message_type,
            data,
            active_prompt_id=self._active_prompt_id,
            all_node_ids=self._all_node_ids,
            prompt_nodes=self._prompt_nodes,
            progress_state_seen=self._progress_state_seen,
            timing_tracker=self._timing_tracker,
            progress_tracker=self._progress_tracker,
            source_identity_resolver=self._source_identity_resolver,
        )
        if progress_state_route.handled:
            self._progress_state_seen = progress_state_route.progress_state_seen
            if progress_state_route.emit_progress:
                return WebsocketJsonRouteResult(
                    progress_emission=self._progress_emission(
                        source_event="progress_state",
                        sampler_percent=progress_state_route.sampler_percent,
                    )
                )
            return WebsocketJsonRouteResult()

        model_load_route = route_model_load_progress_event(
            message_type,
            data,
            workflow_id=self._workflow_id,
            active_prompt_id=self._active_prompt_id,
            all_node_ids=self._all_node_ids,
            source_metadata_resolver=self._source_metadata_resolver,
            on_model_load_progress=self._on_model_load_progress,
        )
        if model_load_route.handled:
            return WebsocketJsonRouteResult()

        if message_type == "substitute_cube_output":
            self._cube_output_handler.handle(data)
            return WebsocketJsonRouteResult()

        execution_error_route = route_execution_error_event(
            message_type,
            data,
            workflow_id=self._workflow_id,
            active_prompt_id=self._active_prompt_id,
            timing_tracker=self._timing_tracker,
            runtime_context_provider=self._runtime_context_provider,
        )
        if execution_error_route.error_message is not None:
            return WebsocketJsonRouteResult(
                failure=WebsocketExecutionFailure(
                    message=execution_error_route.error_message,
                    detail=execution_error_route.error_detail,
                    error_report=execution_error_route.error_report,
                )
            )
        if execution_error_route.handled:
            return WebsocketJsonRouteResult()

        node_execution_route = route_node_execution_event(
            message_type,
            data,
            active_prompt_id=self._active_prompt_id,
            all_node_ids=self._all_node_ids,
            timing_tracker=self._timing_tracker,
            progress_tracker=self._progress_tracker,
        )
        if node_execution_route.handled:
            if node_execution_route.emit_progress:
                return WebsocketJsonRouteResult(
                    progress_emission=self._progress_emission(
                        source_event="executed",
                        sampler_percent=None,
                    )
                )
            return WebsocketJsonRouteResult()

        executing_route = route_executing_event(
            message_type,
            data,
            active_prompt_id=self._active_prompt_id,
            all_node_ids=self._all_node_ids,
            current_node=self._current_node,
            progress_state_seen=self._progress_state_seen,
            timing_tracker=self._timing_tracker,
            progress_tracker=self._progress_tracker,
            source_identity_resolver=self._source_identity_resolver,
        )
        if executing_route.handled:
            self._current_node = executing_route.current_node
            if executing_route.unknown_node_id is not None:
                self._log_unknown_node(
                    "Ignoring executing event for unknown Comfy node",
                    executing_route.unknown_node_id,
                )
                return WebsocketJsonRouteResult()
            if executing_route.emit_progress_source is not None:
                return WebsocketJsonRouteResult(
                    progress_emission=WebsocketProgressEmission(
                        source_event=executing_route.emit_progress_source,
                        workflow_percent=(
                            100.0
                            if executing_route.prompt_finished
                            else self._progress_tracker.workflow_percent()
                        ),
                        sampler_percent=None,
                    ),
                    prompt_finished=executing_route.prompt_finished,
                )
            return WebsocketJsonRouteResult(
                prompt_finished=executing_route.prompt_finished,
            )

        return WebsocketJsonRouteResult()

    def _progress_emission(
        self,
        *,
        source_event: str,
        sampler_percent: float | None,
    ) -> WebsocketProgressEmission:
        """Build a progress emission from current tracker state."""

        return WebsocketProgressEmission(
            source_event=source_event,
            workflow_percent=self._progress_tracker.workflow_percent(),
            sampler_percent=sampler_percent,
        )

    def _log_unknown_node(self, message: str, node_id: str) -> None:
        """Log ignored node-scoped events with workflow and prompt context."""

        log_warning(
            _LOGGER,
            message,
            workflow_id=self._workflow_id,
            prompt_id=self._active_prompt_id,
            node_id=node_id,
        )


__all__ = [
    "ComfyWebsocketEventRouter",
    "WebsocketExecutionFailure",
    "WebsocketJsonRouteResult",
    "WebsocketProgressEmission",
]
