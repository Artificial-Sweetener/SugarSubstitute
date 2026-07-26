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

"""Prepare coherent live and base-drag geometry state for prompt reordering."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
)

from .observability import (
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_drop_geometry_publication import (
    PromptReorderDropGeometryPublisher,
)
from .reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_keyboard_navigation import PromptReorderLayoutPolicy
from .reorder_placement_geometry import PromptReorderPlacementSnapshot


class PromptReorderDragGeometrySource(Protocol):
    """Provide painted-projection placement geometry needed to begin a drag."""

    def live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Return placements derived from the matching live chip geometry."""

        ...


class PromptReorderDragGeometryPreparationOwner:
    """Derive one drag's layout, chip, placement, and lane publications."""

    def __init__(
        self,
        *,
        layout_policy: PromptReorderLayoutPolicy,
        geometry_owner: PromptReorderDragGeometrySource,
        drop_geometry: PromptReorderDropGeometryPublisher,
    ) -> None:
        """Store focused derivation owners used only at drag boundaries."""

        self._layout_policy = layout_policy
        self._geometry_owner = geometry_owner
        self._drop_geometry = drop_geometry

    def begin_drag(
        self,
        state: PromptReorderInteractionGeometryState,
        *,
        dragged_segment_index: int,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderInteractionGeometryState:
        """Return the initial immutable base-drag state for one gesture."""

        if (
            state.document_view is None
            or state.current_layout_view is None
            or state.current_reorder_state is None
        ):
            return state

        started_at = reorder_drag_started_at()
        base_drag_state = self._layout_policy.build_base_drag_state(
            state.document_view,
            state.current_reorder_state,
            current_layout_view=state.current_layout_view,
            dragged_segment_index=dragged_segment_index,
        )
        base_drag_reorder_state = base_drag_state.reorder_state
        base_drag_layout_view = base_drag_state.layout_view
        next_state = replace(
            state,
            base_drag_reorder_state=base_drag_reorder_state,
            base_drag_layout_view=base_drag_layout_view,
            preview_layout_view=None,
            preview_reorder_state=None,
            preview_layout_target_identity=None,
            preview_geometry_target_identity=None,
            placement_snapshot=None,
            active_placement=None,
            last_base_drag_geometry_key=None,
        )
        log_reorder_drag_timing(
            "start.base_drag_layout",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            row_count=len(base_drag_layout_view.rows),
            gap_count=len(base_drag_layout_view.gaps),
        )
        return next_state

    def prime_from_painted_projection(
        self,
        state: PromptReorderInteractionGeometryState,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderInteractionGeometryState:
        """Publish pointer placements derived from the matching painted frame."""

        if state.base_drag_layout_view is None:
            return state

        started_at = reorder_drag_started_at()
        placement_snapshot = self._geometry_owner.live_placement_snapshot(
            layout_view=state.base_drag_layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
        )
        if not placement_snapshot.placements:
            return state

        drop_geometry = self._drop_geometry.publish(
            placement_snapshot,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        next_state = replace(
            state,
            placement_snapshot=drop_geometry.placement_snapshot,
            drop_target_visuals=drop_geometry.target_visuals,
            drop_target_lanes=drop_geometry.lanes,
        )
        log_reorder_drag_timing(
            "start.live_placement_prime",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            placement_count=len(drop_geometry.placement_snapshot.placements),
            lane_count=len(drop_geometry.lanes),
        )
        return next_state


__all__ = [
    "PromptReorderDragGeometryPreparationOwner",
    "PromptReorderDragGeometrySource",
]
