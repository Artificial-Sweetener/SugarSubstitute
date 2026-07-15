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

"""Route Comfy progress events without listener side effects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    compute_sampler_percent,
    fraction_from_progress_data,
    is_sampler_node,
    normalize_node_id,
)


class ProgressEventTracker(Protocol):
    """Describe progress operations required for progress event routing."""

    def mark_running(self, node_id: str) -> None:
        """Record a running node."""

    def mark_sampler_progress(self, node_id: str, fraction: float | None) -> None:
        """Record sampler progress for one node."""


@dataclass(frozen=True)
class ProgressEventRouteResult:
    """Describe the listener action selected for one progress event."""

    handled: bool
    emit_progress: bool = False
    sampler_percent: float | None = None
    unknown_node_id: str | None = None


def route_progress_event(
    message_type: object,
    data: Mapping[str, object],
    *,
    active_prompt_id: str,
    all_node_ids: set[str],
    prompt_nodes: Mapping[str, object],
    progress_tracker: ProgressEventTracker,
) -> ProgressEventRouteResult:
    """Apply progress event mutations for the active prompt."""

    if message_type != "progress":
        return ProgressEventRouteResult(handled=False)

    if data.get("prompt_id") != active_prompt_id:
        return ProgressEventRouteResult(handled=True)

    node_value = data.get("node")
    if not isinstance(node_value, (int, str)):
        return ProgressEventRouteResult(handled=True)

    raw_node_id = str(node_value)
    node_id = normalize_node_id(
        node_id=raw_node_id,
        all_node_ids=all_node_ids,
    )
    if node_id is None:
        return ProgressEventRouteResult(
            handled=True,
            unknown_node_id=raw_node_id,
        )

    sampler_percent = (
        compute_sampler_percent(data)
        if is_sampler_node(node_id, prompt_nodes)
        else None
    )
    if sampler_percent is not None:
        progress_tracker.mark_sampler_progress(
            node_id,
            fraction_from_progress_data(data),
        )
    else:
        progress_tracker.mark_running(node_id)
    return ProgressEventRouteResult(
        handled=True,
        emit_progress=True,
        sampler_percent=sampler_percent,
    )


__all__ = [
    "ProgressEventRouteResult",
    "ProgressEventTracker",
    "route_progress_event",
]
