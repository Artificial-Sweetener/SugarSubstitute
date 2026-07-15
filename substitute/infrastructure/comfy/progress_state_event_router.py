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

"""Route Comfy progress_state events without listener side effects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar

from substitute.application.generation.progress_estimation import (
    ComfyWorkflowProgressTracker,
    apply_progress_states_to_tracker,
)
from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    parse_progress_state_nodes,
    sampler_percent_from_progress_state,
)

SourceIdentity = TypeVar("SourceIdentity", contravariant=True)


class ProgressStateTimingTracker(Protocol[SourceIdentity]):
    """Describe timing operations required for progress_state routing."""

    def mark_running(
        self,
        *,
        node_id: str,
        source_identity: SourceIdentity,
    ) -> None:
        """Record a running node with its output source identity."""

    def mark_finished(self, node_id: str) -> None:
        """Record a finished node."""

    def mark_failed(self, node_id: str) -> None:
        """Record a failed node."""


@dataclass(frozen=True)
class ProgressStateRouteResult:
    """Describe the listener action selected for one progress_state event."""

    handled: bool
    progress_state_seen: bool
    emit_progress: bool = False
    sampler_percent: float | None = None


def route_progress_state_event(
    message_type: object,
    data: Mapping[str, object],
    *,
    active_prompt_id: str,
    all_node_ids: set[str],
    prompt_nodes: Mapping[str, object],
    progress_state_seen: bool,
    timing_tracker: ProgressStateTimingTracker[SourceIdentity],
    progress_tracker: ComfyWorkflowProgressTracker,
    source_identity_resolver: Callable[[str], SourceIdentity],
) -> ProgressStateRouteResult:
    """Apply progress_state timing and tracker mutations for the active prompt."""

    if message_type != "progress_state":
        return ProgressStateRouteResult(
            handled=False,
            progress_state_seen=progress_state_seen,
        )

    if data.get("prompt_id") != active_prompt_id:
        return ProgressStateRouteResult(
            handled=True,
            progress_state_seen=progress_state_seen,
        )

    progress_states = parse_progress_state_nodes(
        data=data,
        all_node_ids=all_node_ids,
    )
    if not progress_states:
        return ProgressStateRouteResult(
            handled=True,
            progress_state_seen=progress_state_seen,
        )

    for progress_state in progress_states:
        owner_node_id = progress_state.owner_node_id
        if owner_node_id is None:
            continue
        if progress_state.state == "running":
            timing_tracker.mark_running(
                node_id=owner_node_id,
                source_identity=source_identity_resolver(owner_node_id),
            )
        elif progress_state.state == "finished":
            timing_tracker.mark_finished(owner_node_id)
        elif progress_state.state == "error":
            timing_tracker.mark_failed(owner_node_id)

    apply_progress_states_to_tracker(
        tracker=progress_tracker,
        progress_states=progress_states,
    )
    return ProgressStateRouteResult(
        handled=True,
        progress_state_seen=True,
        emit_progress=True,
        sampler_percent=sampler_percent_from_progress_state(
            progress_states=progress_states,
            prompt_nodes=prompt_nodes,
        ),
    )


__all__ = [
    "ProgressStateRouteResult",
    "ProgressStateTimingTracker",
    "route_progress_state_event",
]
