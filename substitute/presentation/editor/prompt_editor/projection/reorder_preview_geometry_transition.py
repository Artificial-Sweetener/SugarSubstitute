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

"""Own one atomic reorder preview-geometry state transition."""

from __future__ import annotations

from dataclasses import dataclass, replace

from substitute.application.prompt_editor.reorder.views import PromptReorderDropTarget

from .observability import log_reorder_drag_event
from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_drop_geometry_publication import PromptReorderDropGeometryPublisher
from .reorder_drop_targets import (
    PromptReorderDropLane,
    PromptReorderDropTargetVisual,
)
from .reorder_geometry_owner import PromptReorderGeometryOwner
from .reorder_interaction_geometry_identity import (
    reorder_interaction_base_drag_geometry_key,
    reorder_preview_target_identity,
)
from .reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_placement_geometry import PromptReorderPlacementSnapshot
from .reorder_preview_layout_policy import reorder_layout_for_painted_preview
from .reorder_state import PromptReorderPreviewTargetIdentity


@dataclass(frozen=True, slots=True)
class PromptReorderGeometryRefresh:
    """Carry projection snapshot changes produced by one geometry refresh."""

    state: PromptReorderInteractionGeometryState
    previous_preview_chip_snapshot: PromptReorderChipGeometrySnapshot | None
    preview_chip_snapshot: PromptReorderChipGeometrySnapshot | None
    base_drag_chip_snapshot: PromptReorderChipGeometrySnapshot | None
    placement_snapshot: PromptReorderPlacementSnapshot | None
    drop_target_visuals: tuple[PromptReorderDropTargetVisual, ...]
    drop_target_lanes: tuple[PromptReorderDropLane, ...]
    preview_geometry_identity: PromptReorderPreviewTargetIdentity | None
    base_drag_geometry_reused: bool
    base_drag_geometry_rebuilt: bool


class PromptReorderPreviewGeometryTransitionOwner:
    """Build preview, base-drag, placement, lane, and reuse state atomically."""

    def __init__(
        self,
        *,
        geometry_owner: PromptReorderGeometryOwner,
        drop_geometry: PromptReorderDropGeometryPublisher,
    ) -> None:
        """Store the focused geometry and drop-publication collaborators."""

        self._geometry_owner = geometry_owner
        self._drop_geometry = drop_geometry

    def build(
        self,
        state: PromptReorderInteractionGeometryState,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderGeometryRefresh:
        """Return one complete preview-geometry transition."""

        previous_preview_chip_snapshot = state.preview_chip_geometry_snapshot
        preview_chip_snapshot: PromptReorderChipGeometrySnapshot | None = None
        preview_geometry_identity: PromptReorderPreviewTargetIdentity | None = None
        preview_layout = reorder_layout_for_painted_preview(
            state,
            dragged_segment_index=dragged_segment_index,
            preview_layout_view=state.preview_layout_view,
        )
        if state.preview_snapshot is not None and preview_layout is not None:
            preview_chip_snapshot = self._geometry_owner.preview_chip_snapshot(
                snapshot=state.preview_snapshot,
                layout_view=preview_layout,
            )
            preview_geometry_identity = (
                state.preview_layout_target_identity
                if state.preview_layout_target_identity is not None
                else reorder_preview_target_identity(
                    state,
                    dragged_segment_index=dragged_segment_index,
                    target=active_target,
                    viewport_identity=viewport_identity,
                    preview_layout_view=state.preview_layout_view,
                )
            )

        base_drag_chip_snapshot: PromptReorderChipGeometrySnapshot | None = None
        placement_snapshot: PromptReorderPlacementSnapshot | None = None
        drop_target_visuals: tuple[PromptReorderDropTargetVisual, ...] = ()
        drop_target_lanes: tuple[PromptReorderDropLane, ...] = ()
        base_drag_geometry_reused = False
        base_drag_geometry_rebuilt = False
        base_geometry_key = reorder_interaction_base_drag_geometry_key(
            state,
            viewport_identity=viewport_identity,
            dragged_segment_index=dragged_segment_index,
        )
        if (
            base_geometry_key is not None
            and base_geometry_key == state.last_base_drag_geometry_key
            and state.base_drag_chip_geometry_snapshot is not None
            and state.placement_snapshot is not None
        ):
            base_drag_geometry_reused = True
            base_drag_chip_snapshot = state.base_drag_chip_geometry_snapshot
            placement_snapshot = state.placement_snapshot
            drop_target_visuals = state.drop_target_visuals
            drop_target_lanes = state.drop_target_lanes
            log_reorder_drag_event(
                "preview_geometry.base_drag_reused",
                gesture_id=gesture_id,
                event_id=event_id,
                base_visual_count=len(base_drag_chip_snapshot.geometries_by_chip_index),
                placement_count=len(placement_snapshot.placements),
                lane_count=len(drop_target_lanes),
                key_changed=False,
            )
        elif (
            state.base_drag_layout_view is not None
            and state.base_drag_snapshot is not None
        ):
            base_drag_chip_snapshot = self._geometry_owner.base_drag_chip_snapshot(
                snapshot=state.base_drag_snapshot,
                layout_view=state.base_drag_layout_view,
            )
            placement_snapshot = self._geometry_owner.base_drag_placement_snapshot(
                snapshot=state.base_drag_snapshot,
                layout_view=state.base_drag_layout_view,
            )
            drop_geometry = self._drop_geometry.publish(
                placement_snapshot,
                gesture_id=gesture_id,
                event_id=event_id,
            )
            placement_snapshot = drop_geometry.placement_snapshot
            drop_target_visuals = drop_geometry.target_visuals
            drop_target_lanes = drop_geometry.lanes
            base_drag_geometry_rebuilt = True
            log_reorder_drag_event(
                "preview_geometry.base_drag_rebuilt",
                gesture_id=gesture_id,
                event_id=event_id,
                base_visual_count=len(base_drag_chip_snapshot.geometries_by_chip_index),
                placement_count=len(placement_snapshot.placements),
                lane_count=len(drop_target_lanes),
                key_changed=True,
            )
        next_base_geometry_key = (
            base_geometry_key
            if base_drag_geometry_reused or base_drag_geometry_rebuilt
            else None
        )
        next_state = replace(
            state,
            preview_chip_geometry_snapshot=preview_chip_snapshot,
            preview_geometry_target_identity=preview_geometry_identity,
            base_drag_chip_geometry_snapshot=base_drag_chip_snapshot,
            placement_snapshot=placement_snapshot,
            drop_target_visuals=drop_target_visuals,
            drop_target_lanes=drop_target_lanes,
            last_base_drag_geometry_key=next_base_geometry_key,
        )
        refresh = PromptReorderGeometryRefresh(
            state=next_state,
            previous_preview_chip_snapshot=previous_preview_chip_snapshot,
            preview_chip_snapshot=preview_chip_snapshot,
            base_drag_chip_snapshot=base_drag_chip_snapshot,
            placement_snapshot=placement_snapshot,
            drop_target_visuals=drop_target_visuals,
            drop_target_lanes=drop_target_lanes,
            preview_geometry_identity=preview_geometry_identity,
            base_drag_geometry_reused=base_drag_geometry_reused,
            base_drag_geometry_rebuilt=base_drag_geometry_rebuilt,
        )
        return refresh


__all__ = [
    "PromptReorderGeometryRefresh",
    "PromptReorderPreviewGeometryTransitionOwner",
]
