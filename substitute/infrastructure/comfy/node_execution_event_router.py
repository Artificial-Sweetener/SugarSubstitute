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

"""Route Comfy node execution events without listener side effects."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    normalize_node_id,
)


class NodeExecutionTimingTracker(Protocol):
    """Describe timing operations required for node execution event routing."""

    def mark_cached(self, node_id: str) -> None:
        """Record a cached node."""

    def mark_finished(self, node_id: str) -> None:
        """Record a finished node."""


class NodeExecutionProgressTracker(Protocol):
    """Describe progress operations required for node execution event routing."""

    def mark_cached(self, node_id: str) -> None:
        """Record a cached node."""

    def mark_finished(self, node_id: str) -> None:
        """Record a finished node."""


@dataclass(frozen=True)
class NodeExecutionRouteResult:
    """Describe the listener action selected for one node execution event."""

    handled: bool
    emit_progress: bool = False


def route_node_execution_event(
    message_type: object,
    data: Mapping[str, object],
    *,
    active_prompt_id: str,
    all_node_ids: set[str],
    timing_tracker: NodeExecutionTimingTracker,
    progress_tracker: NodeExecutionProgressTracker,
) -> NodeExecutionRouteResult:
    """Apply cached and executed node mutations for the active prompt."""

    if message_type == "execution_cached":
        if data.get("prompt_id") == active_prompt_id:
            _mark_cached_nodes(
                data=data,
                all_node_ids=all_node_ids,
                timing_tracker=timing_tracker,
                progress_tracker=progress_tracker,
            )
        return NodeExecutionRouteResult(handled=True)

    if message_type == "executed":
        if data.get("prompt_id") != active_prompt_id:
            return NodeExecutionRouteResult(handled=True)
        normalized_node_id = normalize_node_id(
            node_id=str(data.get("node")),
            all_node_ids=all_node_ids,
            display_node_id=_string_or_none(data.get("display_node")),
        )
        if normalized_node_id is None:
            return NodeExecutionRouteResult(handled=True)
        timing_tracker.mark_finished(normalized_node_id)
        progress_tracker.mark_finished(normalized_node_id)
        return NodeExecutionRouteResult(handled=True, emit_progress=True)

    return NodeExecutionRouteResult(handled=False)


def _mark_cached_nodes(
    *,
    data: Mapping[str, object],
    all_node_ids: set[str],
    timing_tracker: NodeExecutionTimingTracker,
    progress_tracker: NodeExecutionProgressTracker,
) -> None:
    """Mark normalized cached nodes from one execution_cached event."""

    for node_id in cast(Iterable[object], data.get("nodes", [])):
        normalized_node_id = normalize_node_id(
            node_id=str(node_id),
            all_node_ids=all_node_ids,
        )
        if normalized_node_id is not None:
            timing_tracker.mark_cached(normalized_node_id)
            progress_tracker.mark_cached(normalized_node_id)


def _string_or_none(value: object) -> str | None:
    """Return string values while preserving missing optional fields."""

    if isinstance(value, (str, int)):
        return str(value)
    return None


__all__ = [
    "NodeExecutionProgressTracker",
    "NodeExecutionRouteResult",
    "NodeExecutionTimingTracker",
    "route_node_execution_event",
]
