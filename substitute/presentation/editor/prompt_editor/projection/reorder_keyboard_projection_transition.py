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

"""Own keyboard-navigation input and immutable reorder projection transitions."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderPreparedStateView,
    PromptReorderDropTarget,
)

from .observability import (
    log_reorder_drag_event,
    reorder_drag_target_kind,
)
from .reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigationInput,
    PromptReorderKeyboardNavigationResult,
    PromptReorderLayoutPolicy,
)


class PromptReorderKeyboardProjectionTransitionOwner:
    """Project keyboard queries and adopt successful navigation atomically."""

    def __init__(self, *, layout_policy: PromptReorderLayoutPolicy) -> None:
        """Store the policy used to derive coherent reorder state generations."""

        self._layout_policy = layout_policy

    def navigation_input(
        self,
        state: PromptReorderInteractionGeometryState,
        *,
        active_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        preferred_x: float | None,
    ) -> PromptReorderKeyboardNavigationInput:
        """Build one bounded navigator input from the current state publication."""

        active_segment_center: tuple[float, float] | None = None
        if (
            active_segment_index is not None
            and state.live_chip_geometry_snapshot is not None
        ):
            active_geometry = (
                state.live_chip_geometry_snapshot.geometries_by_chip_index.get(
                    active_segment_index
                )
            )
            if active_geometry is not None:
                center = active_geometry.hotspot_rect.center()
                active_segment_center = (center.x(), center.y())
        return PromptReorderKeyboardNavigationInput(
            document_view=state.document_view,
            current_layout_view=state.current_layout_view,
            base_drag_state=(
                None
                if state.base_drag_layout_view is None
                or state.base_drag_reorder_state is None
                else PromptReorderPreparedStateView(
                    reorder_state=state.base_drag_reorder_state,
                    layout_view=state.base_drag_layout_view,
                )
            ),
            active_segment_index=active_segment_index,
            active_target=active_target,
            preferred_x=preferred_x,
            drop_target_lanes=state.drop_target_lanes,
            active_segment_center=active_segment_center,
        )

    def apply(
        self,
        state: PromptReorderInteractionGeometryState,
        result: PromptReorderKeyboardNavigationResult,
        *,
        active_segment_index: int | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderInteractionGeometryState:
        """Return one coherent state generation for a valid keyboard movement."""

        if (
            not result.moved
            or result.proposed_state is None
            or result.proposed_base_drag_state is None
            or state.document_view is None
            or state.current_layout_view is None
            or state.current_reorder_state is None
            or result.destination_target is None
            or active_segment_index is None
        ):
            return state

        proposed_layout_view = result.proposed_state.layout_view
        proposed_reorder_state = result.proposed_state.reorder_state
        if (
            result.ordered_segment_indices == state.initial_ordered_indices
            and proposed_layout_view == state.original_layout_view
            and state.original_layout_view is not None
            and state.original_reorder_state is not None
        ):
            proposed_layout_view = state.original_layout_view
            proposed_reorder_state = state.original_reorder_state

        base_drag_reorder_state = result.proposed_base_drag_state.reorder_state
        ordered_segment_indices = self._layout_policy.reorder_layout_chip_indices(
            proposed_layout_view
        )
        base_drag_layout_view = result.proposed_base_drag_state.layout_view
        next_state = replace(
            state,
            current_reorder_state=proposed_reorder_state,
            base_drag_reorder_state=base_drag_reorder_state,
            current_layout_view=proposed_layout_view,
            preview_layout_view=None,
            preview_reorder_state=None,
            ordered_segment_indices=ordered_segment_indices,
            base_drag_layout_view=base_drag_layout_view,
            preview_layout_target_identity=None,
            preview_geometry_target_identity=None,
        )
        log_reorder_drag_event(
            "drop_target.changed_rebuild_path",
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=active_segment_index,
            target_kind=reorder_drag_target_kind(result.destination_target),
            ordered_count=len(next_state.ordered_segment_indices),
        )
        return next_state


__all__ = ["PromptReorderKeyboardProjectionTransitionOwner"]
