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

"""Apply normalized Comfy progress-state entries to workflow progress tracking."""

from __future__ import annotations

from typing import Literal, Protocol

from substitute.application.generation.progress_estimation.workflow_progress_tracker import (
    ComfyWorkflowProgressTracker,
)

ProgressStateName = Literal["pending", "running", "finished", "error"]


class ProgressStateEntry(Protocol):
    """Describe normalized progress-state data required by the tracker."""

    @property
    def owner_node_id(self) -> str | None:
        """Return the workflow node that owns this progress-state entry."""

    @property
    def state(self) -> ProgressStateName:
        """Return the normalized Comfy progress-state name."""

    @property
    def value(self) -> float:
        """Return the current progress-state value."""

    @property
    def maximum(self) -> float:
        """Return the maximum progress-state value."""


def apply_progress_states_to_tracker(
    *,
    tracker: ComfyWorkflowProgressTracker,
    progress_states: tuple[ProgressStateEntry, ...],
) -> None:
    """Apply normalized progress-state entries to the workflow tracker."""

    for progress_state in progress_states:
        owner_node_id = progress_state.owner_node_id
        if owner_node_id is None:
            continue
        if progress_state.state == "finished":
            tracker.mark_finished(owner_node_id)
        elif progress_state.state == "running":
            tracker.mark_running(owner_node_id)
            tracker.mark_sampler_progress(
                owner_node_id,
                _fraction_from_values(
                    value=progress_state.value,
                    maximum=progress_state.maximum,
                ),
            )
        elif progress_state.state == "error":
            tracker.mark_error(owner_node_id)


def _fraction_from_values(*, value: float, maximum: float) -> float | None:
    """Return a bounded fraction from progress values."""

    if maximum <= 0:
        return None
    return min(1.0, max(0.0, value / maximum))


__all__ = [
    "ProgressStateEntry",
    "ProgressStateName",
    "apply_progress_states_to_tracker",
]
