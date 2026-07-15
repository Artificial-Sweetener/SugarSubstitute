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

"""Own Comfy listener execution timing accumulation and emission."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.ports.comfy_gateway import (
    CubeExecutionTiming,
    GenerationExecutionTiming,
)
from substitute.domain.common import WorkflowId
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("infrastructure.comfy.comfy_execution_timing")


class TimingSourceIdentity(Protocol):
    """Describe source identity fields required for timing attribution."""

    @property
    def source_key(self) -> str:
        """Return the stable output source key."""

    @property
    def cube_alias(self) -> str:
        """Return the cube alias associated with the output source."""


@dataclass(frozen=True)
class ActiveNodeTiming:
    """Track one locally observed active node execution window."""

    node_id: str
    source_identity: TimingSourceIdentity
    started_at_ms: float


class ComfyExecutionTimingTracker:
    """Accumulate prompt and node execution timing from websocket events."""

    def __init__(
        self,
        *,
        workflow_id: WorkflowId,
        prompt_id: str,
        clock_ms: Callable[[], float],
    ) -> None:
        """Initialize timing state for one Comfy prompt."""

        self._workflow_id = workflow_id
        self._prompt_id = prompt_id
        self._clock_ms = clock_ms
        self._prompt_started_at_ms: float | None = None
        self._prompt_ended_at_ms: float | None = None
        self._fallback_started_at_ms: float | None = None
        self._fallback_ended_at_ms: float | None = None
        self._active_nodes: dict[str, ActiveNodeTiming] = {}
        self._cached_nodes: set[str] = set()
        self._duration_by_source: dict[tuple[str, str], float] = {}

    def mark_prompt_started(self, timestamp_ms: float | None) -> None:
        """Record Comfy prompt start timing when supplied."""

        if timestamp_ms is not None:
            self._prompt_started_at_ms = timestamp_ms
        self._mark_fallback_started()

    def mark_prompt_terminal(self, timestamp_ms: float | None) -> None:
        """Record Comfy prompt terminal timing when supplied."""

        if timestamp_ms is not None:
            self._prompt_ended_at_ms = timestamp_ms
        self._fallback_ended_at_ms = self._clock_ms()

    def mark_cached(self, node_id: str) -> None:
        """Exclude one node from accumulated cube execution timing."""

        self._cached_nodes.add(node_id)
        self._active_nodes.pop(node_id, None)

    def mark_running(
        self,
        *,
        node_id: str,
        source_identity: TimingSourceIdentity,
    ) -> None:
        """Start timing one node if it is not already active."""

        if node_id in self._cached_nodes or node_id in self._active_nodes:
            return
        self._mark_fallback_started()
        self._active_nodes[node_id] = ActiveNodeTiming(
            node_id=node_id,
            source_identity=source_identity,
            started_at_ms=self._clock_ms(),
        )

    def mark_finished(self, node_id: str) -> None:
        """Finish one active node and aggregate its duration by output source."""

        active_timing = self._active_nodes.pop(node_id, None)
        if active_timing is None or node_id in self._cached_nodes:
            return
        duration_ms = max(0.0, self._clock_ms() - active_timing.started_at_ms)
        key = (
            active_timing.source_identity.source_key,
            active_timing.source_identity.cube_alias,
        )
        self._duration_by_source[key] = self._duration_by_source.get(key, 0.0) + (
            duration_ms
        )

    def mark_failed(self, node_id: str) -> None:
        """Discard one failed active node without counting it as completed work."""

        self._active_nodes.pop(node_id, None)

    def finish_all(self, *, count_active_nodes: bool) -> None:
        """Close or discard still-active node timing windows."""

        if count_active_nodes:
            for node_id in tuple(self._active_nodes):
                self.mark_finished(node_id)
        else:
            self._active_nodes.clear()
        if self._fallback_ended_at_ms is None:
            self._fallback_ended_at_ms = self._clock_ms()

    def timing_event(self) -> GenerationExecutionTiming:
        """Return the immutable timing event accumulated so far."""

        return GenerationExecutionTiming(
            workflow_id=self._workflow_id,
            prompt_id=self._prompt_id,
            job_duration_ms=self._job_duration_ms(),
            cube_timings=tuple(
                CubeExecutionTiming(
                    source_key=source_key,
                    cube_alias=cube_alias,
                    duration_ms=duration_ms,
                )
                for (source_key, cube_alias), duration_ms in sorted(
                    self._duration_by_source.items()
                )
            ),
        )

    def _mark_fallback_started(self) -> None:
        """Record local fallback start timing once."""

        if self._fallback_started_at_ms is None:
            self._fallback_started_at_ms = self._clock_ms()

    def _job_duration_ms(self) -> float | None:
        """Return prompt duration from Comfy timestamps or local fallback timing."""

        if (
            self._prompt_started_at_ms is not None
            and self._prompt_ended_at_ms is not None
            and self._prompt_ended_at_ms >= self._prompt_started_at_ms
        ):
            return self._prompt_ended_at_ms - self._prompt_started_at_ms
        if (
            self._fallback_started_at_ms is not None
            and self._fallback_ended_at_ms is not None
            and self._fallback_ended_at_ms >= self._fallback_started_at_ms
        ):
            return self._fallback_ended_at_ms - self._fallback_started_at_ms
        return None


class ComfyExecutionTimingEmitter:
    """Emit a captured timing event at most once with prompt-safe diagnostics."""

    def __init__(
        self,
        *,
        tracker: ComfyExecutionTimingTracker,
        on_timing: Callable[[GenerationExecutionTiming], None],
    ) -> None:
        """Initialize one-shot timing emission around an accumulated tracker."""

        self._tracker = tracker
        self._on_timing = on_timing
        self._emitted = False

    def emit_once(self, *, count_active_nodes: bool) -> None:
        """Finish active timing, log safe metrics, and invoke the callback once."""

        if self._emitted:
            return
        self._tracker.finish_all(count_active_nodes=count_active_nodes)
        timing_event = self._tracker.timing_event()
        self._emitted = True
        log_info(
            _LOGGER,
            "Generation execution timing captured",
            workflow_id=timing_event.workflow_id,
            prompt_id=timing_event.prompt_id,
            job_duration_ms=timing_event.job_duration_ms,
            cube_timing_count=len(timing_event.cube_timings),
        )
        self._on_timing(timing_event)


__all__ = [
    "ActiveNodeTiming",
    "ComfyExecutionTimingEmitter",
    "ComfyExecutionTimingTracker",
    "TimingSourceIdentity",
]
