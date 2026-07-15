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

"""Route Comfy executing events without listener-owned state transitions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    normalize_node_id,
)

SourceIdentity = TypeVar("SourceIdentity", contravariant=True)
ExecutingProgressEvent = Literal["executing", "executing_done"]


class ExecutingTimingTracker(Protocol[SourceIdentity]):
    """Describe timing operations required for executing event routing."""

    def mark_finished(self, node_id: str) -> None:
        """Record a finished node."""

    def mark_running(
        self,
        *,
        node_id: str,
        source_identity: SourceIdentity,
    ) -> None:
        """Record a running node with its output source identity."""


class ExecutingProgressTracker(Protocol):
    """Describe progress operations required for executing event routing."""

    def mark_finished(self, node_id: str) -> None:
        """Record a finished node."""

    def mark_running(self, node_id: str) -> None:
        """Record a running node."""

    def finish_prompt(self) -> None:
        """Record prompt completion."""


@dataclass(frozen=True)
class ExecutingRouteResult:
    """Describe listener state and callback actions after executing routing."""

    handled: bool
    current_node: str | None
    emit_progress_source: ExecutingProgressEvent | None = None
    prompt_finished: bool = False
    unknown_node_id: str | None = None


def route_executing_event(
    message_type: object,
    data: Mapping[str, object],
    *,
    active_prompt_id: str,
    all_node_ids: set[str],
    current_node: str | None,
    progress_state_seen: bool,
    timing_tracker: ExecutingTimingTracker[SourceIdentity],
    progress_tracker: ExecutingProgressTracker,
    source_identity_resolver: Callable[[str], SourceIdentity],
) -> ExecutingRouteResult:
    """Apply executing event state transitions for the active prompt."""

    if message_type != "executing":
        return ExecutingRouteResult(handled=False, current_node=current_node)

    if data.get("prompt_id") != active_prompt_id:
        return ExecutingRouteResult(handled=True, current_node=current_node)

    node_value = data.get("node")
    if node_value is None:
        if current_node in all_node_ids:
            timing_tracker.mark_finished(current_node)
            progress_tracker.mark_finished(current_node)
        progress_tracker.finish_prompt()
        return ExecutingRouteResult(
            handled=True,
            current_node=None,
            emit_progress_source="executing_done",
            prompt_finished=True,
        )

    next_node = str(node_value)
    normalized_next_node = normalize_node_id(
        node_id=next_node,
        all_node_ids=all_node_ids,
        display_node_id=_string_or_none(data.get("display_node")),
    )
    if normalized_next_node is None:
        return ExecutingRouteResult(
            handled=True,
            current_node=current_node,
            unknown_node_id=next_node,
        )

    if (
        not progress_state_seen
        and current_node in all_node_ids
        and current_node != normalized_next_node
    ):
        timing_tracker.mark_finished(current_node)
        progress_tracker.mark_finished(current_node)

    timing_tracker.mark_running(
        node_id=normalized_next_node,
        source_identity=source_identity_resolver(normalized_next_node),
    )
    progress_tracker.mark_running(normalized_next_node)
    return ExecutingRouteResult(
        handled=True,
        current_node=normalized_next_node,
        emit_progress_source="executing",
    )


def _string_or_none(value: object) -> str | None:
    """Return string values while preserving missing optional fields."""

    if isinstance(value, (str, int)):
        return str(value)
    return None


__all__ = [
    "ExecutingProgressEvent",
    "ExecutingProgressTracker",
    "ExecutingRouteResult",
    "ExecutingTimingTracker",
    "route_executing_event",
]
