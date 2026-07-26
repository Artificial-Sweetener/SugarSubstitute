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

"""Own keyboard reorder navigation and displacement intent publication."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderKeyboardDirection,
)
from substitute.application.prompt_editor.reorder.views import PromptReorderDropTarget

from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_interaction_geometry import PromptReorderInteractionGeometry
from ..projection.reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigationResult,
)
from .chip_visuals import PromptChipVisual
from .reorder_animation_presentation import PromptReorderAnimationPresentationOwner
from .reorder_displacement_intent import ReorderDisplacementIntent
from .reorder_gesture_controller import PromptReorderGestureController


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardVisualContext:
    """Carry already-prepared visuals needed to animate one keyboard move."""

    segment_indices: tuple[int, ...]
    preview_active: bool
    live_visuals_by_index: Mapping[int, PromptChipVisual]
    preview_visuals_by_index: Mapping[int, PromptChipVisual]


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardInteractionResult:
    """Publish one keyboard action and its authoritative geometry state."""

    moved: bool
    context_prepared: bool
    state: PromptReorderInteractionGeometryState


class PromptReorderKeyboardInteractionOwner:
    """Coordinate keyboard reorder over geometry and gesture authorities."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        animation: PromptReorderAnimationPresentationOwner,
    ) -> None:
        """Bind the three focused authorities used by keyboard navigation."""

        self._geometry = geometry
        self._gesture = gesture
        self._animation = animation

    def move(
        self,
        *,
        direction: PromptReorderKeyboardDirection,
        gesture_id: int | None,
        event_id: int | None,
        visuals: PromptReorderKeyboardVisualContext,
    ) -> PromptReorderKeyboardInteractionResult:
        """Apply one typed directional keyboard reorder command."""

        return self._move(
            horizontal_step=(
                -1 if direction == "left" else 1 if direction == "right" else None
            ),
            vertical_direction=(
                -1 if direction == "up" else 1 if direction == "down" else None
            ),
            gesture_id=gesture_id,
            event_id=event_id,
            visuals=visuals,
        )

    def committable_drop_target(self) -> PromptReorderDropTarget | None:
        """Return the target represented by the current keyboard preview."""

        active_target = self._gesture.state.active_drop_target
        if active_target is not None:
            return active_target
        state = self._geometry.state
        active_segment_index = self._gesture.state.base_drag_segment_index
        if (
            active_segment_index is None
            or state.current_layout_view is None
            or state.document_view is None
        ):
            return None
        return self._geometry.resolve_drop_target_for_current_layout(
            active_segment_index=active_segment_index
        )

    def _move(
        self,
        *,
        horizontal_step: int | None,
        vertical_direction: int | None,
        gesture_id: int | None,
        event_id: int | None,
        visuals: PromptReorderKeyboardVisualContext,
    ) -> PromptReorderKeyboardInteractionResult:
        """Apply one directional move and publish its coherent result."""

        ready, context_prepared = self._prepare_context(
            gesture_id=gesture_id,
            event_id=event_id,
        )
        if not ready:
            return self._result(moved=False, context_prepared=context_prepared)

        gesture_state = self._gesture.state
        navigation: PromptReorderKeyboardNavigationResult
        if horizontal_step is not None:
            navigation = self._geometry.move_keyboard_horizontally(
                active_segment_index=gesture_state.base_drag_segment_index,
                active_target=gesture_state.active_drop_target,
                preferred_x=gesture_state.keyboard_preferred_x,
                step=horizontal_step,
                gesture_id=gesture_id,
                event_id=event_id,
            )
        else:
            assert vertical_direction is not None
            navigation = self._geometry.move_keyboard_vertically(
                active_segment_index=gesture_state.base_drag_segment_index,
                active_target=gesture_state.active_drop_target,
                direction=vertical_direction,
                preferred_x=gesture_state.keyboard_preferred_x,
                gesture_id=gesture_id,
                event_id=event_id,
            )
        if not navigation.moved:
            return self._result(moved=False, context_prepared=context_prepared)

        held_segment_index = gesture_state.base_drag_segment_index
        if held_segment_index is None:
            return self._result(moved=False, context_prepared=context_prepared)
        self._animation.record_target_change(
            ReorderDisplacementIntent(
                source="keyboard",
                held_segment_index=held_segment_index,
                target=navigation.destination_target,
                pointer_global_pos=None,
                reason="keyboard_target_changed",
            ),
            segment_indices=visuals.segment_indices,
            preview_active=visuals.preview_active,
            live_visuals_by_index=visuals.live_visuals_by_index,
            preview_visuals_by_index=visuals.preview_visuals_by_index,
        )
        self._gesture.set_active_drop_target(navigation.destination_target)
        self._gesture.set_keyboard_preferred_x(navigation.preferred_x)
        return self._result(moved=True, context_prepared=context_prepared)

    def _prepare_context(
        self,
        *,
        gesture_id: int | None,
        event_id: int | None,
    ) -> tuple[bool, bool]:
        """Prepare stable base-drag geometry once for keyboard navigation."""

        gesture_state = self._gesture.state
        if gesture_state.dragged_segment_index is not None:
            return False, False
        active_segment_index = gesture_state.active_segment_index
        state = self._geometry.state
        if (
            active_segment_index is None
            or state.current_layout_view is None
            or state.document_view is None
        ):
            return False, False
        if (
            gesture_state.base_drag_segment_index == active_segment_index
            and state.base_drag_layout_view is not None
            and state.drop_target_lanes
        ):
            return True, False

        self._gesture.set_base_drag_segment(active_segment_index)
        self._geometry.begin_drag(
            dragged_segment_index=active_segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return bool(self._geometry.state.drop_target_lanes), True

    def _result(
        self,
        *,
        moved: bool,
        context_prepared: bool,
    ) -> PromptReorderKeyboardInteractionResult:
        """Return one result bound to the latest geometry publication."""

        return PromptReorderKeyboardInteractionResult(
            moved=moved,
            context_prepared=context_prepared,
            state=self._geometry.state,
        )
