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

"""Own prompt reorder interaction layout, placement, and preview geometry state."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)

from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_drag_geometry_preparation import (
    PromptReorderDragGeometryPreparationOwner,
)
from .reorder_drop_geometry_publication import (
    PromptReorderDropGeometryPublisher,
)
from .reorder_geometry_owner import PromptReorderGeometryOwner
from .reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_interaction_geometry_identity import (
    reorder_preview_target_identity,
)
from .reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigationResult,
    PromptReorderKeyboardNavigator,
    PromptReorderLayoutPolicy,
)
from .reorder_keyboard_projection_transition import (
    PromptReorderKeyboardProjectionTransitionOwner,
)
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
)
from .reorder_preview_geometry_transition import (
    PromptReorderGeometryRefresh,
    PromptReorderPreviewGeometryTransitionOwner,
)
from .reorder_preview_layout_state import PromptReorderPreviewLayoutStateOwner


class PromptReorderInteractionGeometry:
    """Coordinate reorder layout, placement, lane, and preview identity state."""

    def __init__(
        self,
        *,
        layout_policy: PromptReorderLayoutPolicy,
        geometry_owner: PromptReorderGeometryOwner,
    ) -> None:
        """Store projection collaborators without depending on overlay widgets."""

        self._layout_policy = layout_policy
        self._geometry_owner = geometry_owner
        self._keyboard_navigator = PromptReorderKeyboardNavigator(
            layout_policy=layout_policy
        )
        drop_geometry = PromptReorderDropGeometryPublisher()
        self._drag_geometry_preparation = PromptReorderDragGeometryPreparationOwner(
            layout_policy=layout_policy,
            geometry_owner=geometry_owner,
            drop_geometry=drop_geometry,
        )
        self._preview_geometry_transition = PromptReorderPreviewGeometryTransitionOwner(
            geometry_owner=geometry_owner,
            drop_geometry=drop_geometry,
        )
        self._preview_layout_state = PromptReorderPreviewLayoutStateOwner(
            layout_policy=layout_policy
        )
        self._keyboard_projection_transition = (
            PromptReorderKeyboardProjectionTransitionOwner(layout_policy=layout_policy)
        )
        self._state = PromptReorderInteractionGeometryState()

    @property
    def state(self) -> PromptReorderInteractionGeometryState:
        """Return the current atomic interaction-geometry publication."""

        return self._state

    def set_session(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        ordered_indices: tuple[int, ...],
    ) -> None:
        """Replace all source/layout state for a reorder overlay session."""

        self._state = PromptReorderInteractionGeometryState(
            document_view=document_view,
            original_layout_view=layout_view,
            current_layout_view=layout_view,
            original_reorder_state=reorder_state,
            current_reorder_state=reorder_state,
            initial_ordered_indices=ordered_indices,
            ordered_segment_indices=ordered_indices,
        )

    def clear_drag_context(self, *, preserve_preview: bool = False) -> None:
        """Retire drag geometry while optionally preserving the committed frame."""

        state = self._state
        self._state = replace(
            state,
            base_drag_layout_view=None,
            base_drag_reorder_state=None,
            base_drag_chip_geometry_snapshot=None,
            base_drag_snapshot=None,
            preview_layout_view=(
                state.preview_layout_view if preserve_preview else None
            ),
            preview_reorder_state=(
                state.preview_reorder_state if preserve_preview else None
            ),
            preview_chip_geometry_snapshot=(
                state.preview_chip_geometry_snapshot if preserve_preview else None
            ),
            placement_snapshot=None,
            active_placement=None,
            drop_target_visuals=(),
            drop_target_lanes=(),
            last_base_drag_geometry_key=None,
            preview_layout_target_identity=None,
            preview_geometry_target_identity=None,
        )

    def commit_preview_layout(self) -> bool:
        """Promote the coherent preview layout and state to the current session."""

        state = self._state
        if state.preview_layout_view is None:
            return False
        ordered_indices = self._layout_policy.reorder_layout_chip_indices(
            state.preview_layout_view
        )
        self._state = replace(
            state,
            current_layout_view=state.preview_layout_view,
            current_reorder_state=state.preview_reorder_state,
            ordered_segment_indices=ordered_indices,
        )
        return True

    def restore_original_layout(self) -> None:
        """Restore original session layout and clear all preview authority."""

        state = self._state
        self._state = replace(
            state,
            current_layout_view=state.original_layout_view,
            current_reorder_state=state.original_reorder_state,
            preview_layout_view=None,
            preview_reorder_state=None,
            ordered_segment_indices=state.initial_ordered_indices,
            preview_layout_target_identity=None,
            preview_geometry_target_identity=None,
        )

    def clear_preview_target_identity(self) -> None:
        """Clear target identity for preview layout and geometry snapshots."""

        self._state = replace(
            self._state,
            preview_layout_target_identity=None,
            preview_geometry_target_identity=None,
        )

    def build_live_chip_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> PromptReorderChipGeometrySnapshot:
        """Build and publish live chip geometry through the sole geometry owner."""

        snapshot = self._geometry_owner.live_chip_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )
        self._state = replace(self._state, live_chip_geometry_snapshot=snapshot)
        return snapshot

    def begin_drag(
        self,
        *,
        dragged_segment_index: int,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderLayoutView | None:
        """Build and store the base-drag layout for one pointer gesture."""

        self._state = self._drag_geometry_preparation.begin_drag(
            self._state,
            dragged_segment_index=dragged_segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return self._state.base_drag_layout_view

    def prime_base_drag_placement_from_painted_projection(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Prime pointer hit testing from geometry matching the painted layout."""

        state = self._state
        self._state = self._drag_geometry_preparation.prime_from_painted_projection(
            state,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return self._state is not state

    def update_preview_layout(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Refresh the typed reorder preview layout for active drag state."""

        self._state = self._preview_layout_state.build(
            self._state,
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            viewport_identity=viewport_identity,
            gesture_id=gesture_id,
            event_id=event_id,
        )

    def set_preview_snapshots(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None,
        ordered_chip_indices: tuple[int, ...],
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
    ) -> None:
        """Store controller-built preview snapshots with stale-safe identity."""

        state = self._state
        ordered_segment_indices = state.ordered_segment_indices
        preview_layout_target_identity = state.preview_layout_target_identity
        preview_geometry_target_identity = state.preview_geometry_target_identity
        if snapshot is not None:
            ordered_segment_indices = ordered_chip_indices
            preview_layout_target_identity = reorder_preview_target_identity(
                state,
                dragged_segment_index=dragged_segment_index,
                target=active_target,
                viewport_identity=viewport_identity,
                preview_layout_view=state.preview_layout_view,
            )
        else:
            preview_geometry_target_identity = None
        self._state = replace(
            state,
            preview_snapshot=snapshot,
            base_drag_snapshot=base_drag_snapshot,
            ordered_segment_indices=ordered_segment_indices,
            preview_layout_target_identity=preview_layout_target_identity,
            preview_geometry_target_identity=preview_geometry_target_identity,
        )

    def refresh_preview_geometry(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderGeometryRefresh:
        """Refresh preview/base chip snapshots and prepared placement lanes."""

        refresh = self._preview_geometry_transition.build(
            self._state,
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            viewport_identity=viewport_identity,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        self._state = refresh.state
        return refresh

    def move_keyboard_horizontally(
        self,
        *,
        active_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        preferred_x: float | None,
        step: int,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderKeyboardNavigationResult:
        """Apply one horizontal keyboard move through projection navigation."""

        result = self._keyboard_navigator.move_horizontally(
            self._keyboard_projection_transition.navigation_input(
                self._state,
                active_segment_index=active_segment_index,
                active_target=active_target,
                preferred_x=preferred_x,
            ),
            step=step,
        )
        self._state = self._keyboard_projection_transition.apply(
            self._state,
            result,
            active_segment_index=active_segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return result

    def move_keyboard_vertically(
        self,
        *,
        active_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        direction: int,
        preferred_x: float | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderKeyboardNavigationResult:
        """Apply one vertical keyboard move through projection navigation."""

        result = self._keyboard_navigator.move_vertically(
            self._keyboard_projection_transition.navigation_input(
                self._state,
                active_segment_index=active_segment_index,
                active_target=active_target,
                preferred_x=preferred_x,
            ),
            direction=direction,
        )
        self._state = self._keyboard_projection_transition.apply(
            self._state,
            result,
            active_segment_index=active_segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return result

    def resolve_drop_target_for_current_layout(
        self,
        *,
        active_segment_index: int | None,
    ) -> PromptReorderDropTarget | None:
        """Resolve the target whose preview layout matches the current order."""

        return self._keyboard_navigator.resolve_drop_target_for_current_layout(
            self._keyboard_projection_transition.navigation_input(
                self._state,
                active_segment_index=active_segment_index,
                active_target=None,
                preferred_x=None,
            )
        )

    def set_active_placement(
        self,
        placement: PromptReorderPlacementGeometry | None,
    ) -> None:
        """Publish the active placement selected by pointer or landing policy."""

        if placement is self._state.active_placement:
            return
        self._state = replace(self._state, active_placement=placement)


__all__ = [
    "PromptReorderInteractionGeometry",
    "PromptReorderKeyboardNavigationResult",
    "PromptReorderLayoutPolicy",
]
