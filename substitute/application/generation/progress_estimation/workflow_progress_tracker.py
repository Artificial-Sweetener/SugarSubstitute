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

"""Track deterministic Comfy-style workflow progress for one prompt."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from substitute.application.generation.progress_estimation.node_classifier import (
    classify_node,
)


class ComfyWorkflowProgressTracker:
    """Compute node-count workflow progress with sampler-slot interpolation."""

    def __init__(self, prompt_nodes: Mapping[str, Mapping[str, Any]]) -> None:
        """Create a tracker for one executable Comfy prompt."""

        self._node_ids = {str(node_id) for node_id in prompt_nodes}
        self._loader_node_ids = {
            str(node_id)
            for node_id, node_data in prompt_nodes.items()
            if classify_node(node_data) == "loader"
        }
        self._sampler_node_ids = {
            str(node_id)
            for node_id, node_data in prompt_nodes.items()
            if classify_node(node_data) == "sampler"
        }
        self._cached_node_ids: set[str] = set()
        self._finished_node_ids: set[str] = set()
        self._error_node_ids: set[str] = set()
        self._active_sampler_node_id: str | None = None
        self._active_sampler_fraction: float | None = None
        self._last_workflow_percent = 0.0

    @classmethod
    def from_prompt(
        cls,
        prompt_nodes: Mapping[str, Mapping[str, Any]],
    ) -> "ComfyWorkflowProgressTracker":
        """Build a deterministic progress tracker from prompt nodes."""

        return cls(prompt_nodes)

    def mark_cached(self, node_id: str) -> None:
        """Exclude a known cached node from remaining workflow work."""

        if node_id not in self._node_ids:
            return
        self._cached_node_ids.add(node_id)
        self._finished_node_ids.discard(node_id)
        if self._active_sampler_node_id == node_id:
            self._active_sampler_node_id = None
            self._active_sampler_fraction = None

    def mark_running(self, node_id: str) -> None:
        """Record a known node as running."""

        if node_id not in self._node_ids or node_id in self._cached_node_ids:
            return
        if node_id not in self._sampler_node_ids:
            return
        if self._active_sampler_node_id != node_id:
            self._active_sampler_fraction = 0.0
        self._active_sampler_node_id = node_id

    def mark_finished(self, node_id: str) -> None:
        """Record a known non-cached node as finished."""

        if node_id not in self._node_ids or node_id in self._cached_node_ids:
            return
        self._finished_node_ids.add(node_id)
        if self._active_sampler_node_id == node_id:
            self._active_sampler_fraction = 1.0

    def mark_error(self, node_id: str) -> None:
        """Record a known node error without advancing workflow progress."""

        if node_id in self._node_ids:
            self._error_node_ids.add(node_id)

    def mark_sampler_progress(self, node_id: str, fraction: float | None) -> None:
        """Record sampler progress for a known non-cached sampler node."""

        if (
            node_id not in self._sampler_node_ids
            or node_id in self._cached_node_ids
            or fraction is None
        ):
            return
        self._active_sampler_node_id = node_id
        self._active_sampler_fraction = _clamp_fraction(fraction)
        if self._active_sampler_fraction >= 1.0:
            self._finished_node_ids.add(node_id)

    def workflow_percent(self) -> float:
        """Return monotonic workflow percent over remaining meaningful work."""

        denominator_ids = self._workflow_denominator_ids()
        if not denominator_ids:
            return self._last_workflow_percent

        completed = len(self._finished_node_ids & denominator_ids)
        sampler_fraction = self._current_sampler_fraction(denominator_ids)
        raw_percent = 100.0 * (completed + sampler_fraction) / len(denominator_ids)
        bounded = min(100.0, max(0.0, raw_percent))
        self._last_workflow_percent = max(self._last_workflow_percent, bounded)
        return self._last_workflow_percent

    def finish_prompt(self) -> None:
        """Force workflow progress complete when Comfy reports prompt completion."""

        self._last_workflow_percent = 100.0

    def _workflow_denominator_ids(self) -> set[str]:
        """Return nodes that still represent meaningful workflow work."""

        return self._node_ids - self._loader_node_ids - self._cached_node_ids

    def _current_sampler_fraction(self, denominator_ids: set[str]) -> float:
        """Return active sampler fractional contribution when applicable."""

        node_id = self._active_sampler_node_id
        if node_id is None or node_id not in denominator_ids:
            return 0.0
        if node_id in self._finished_node_ids:
            return 0.0
        return self._active_sampler_fraction or 0.0


def _clamp_fraction(value: float) -> float:
    """Clamp fractional progress into workflow-safe bounds."""

    return min(1.0, max(0.0, value))
