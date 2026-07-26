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

"""Resolve prompt reorder keyboard movement from prepared projection geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreparedStateView,
    PromptReorderStateView,
)

from .reorder_drop_targets import PromptReorderDropLane
from .reorder_keyboard_geometry import (
    PromptReorderKeyboardLaneMap,
    PromptReorderKeyboardTargetOccurrence,
)


PromptReorderKeyboardNoOpReason = Literal[
    "missing_context",
    "non_line_target",
    "no_slot_targets",
    "current_target_not_visible",
    "boundary",
    "missing_lane",
    "missing_destination",
    "unchanged_target",
    "unchanged_layout",
]


class PromptReorderLayoutPolicy(Protocol):
    """Provide prepared reorder layout transforms without exposing services."""

    def build_base_drag_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        dragged_segment_index: int,
    ) -> PromptReorderPreparedStateView:
        """Build authoritative hidden-drag state with its derived layout."""

    def build_preview_drop_state(
        self,
        document_view: PromptDocumentView,
        base_drag_state_view: PromptReorderPreparedStateView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderPreparedStateView:
        """Apply one target to the prepared state and derive its layout."""

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return the segment index order represented by a prepared layout."""


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardNavigationInput:
    """Carry prepared widget-free state for one keyboard navigation request."""

    document_view: PromptDocumentView | None
    current_layout_view: PromptReorderLayoutView | None
    base_drag_state: PromptReorderPreparedStateView | None
    active_segment_index: int | None
    active_target: PromptReorderDropTarget | None
    preferred_x: float | None
    drop_target_lanes: tuple[PromptReorderDropLane, ...]
    active_segment_center: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardNavigationResult:
    """Describe one logical keyboard movement without mutating widgets."""

    moved: bool
    destination_target: PromptReorderDropTarget | None
    preferred_x: float | None
    proposed_state: PromptReorderPreparedStateView | None
    proposed_base_drag_state: PromptReorderPreparedStateView | None
    ordered_segment_indices: tuple[int, ...]
    no_op_reason: PromptReorderKeyboardNoOpReason | None = None


class PromptReorderKeyboardNavigator:
    """Own Alt+Arrow reorder target movement over prepared drop lanes."""

    def __init__(self, *, layout_policy: PromptReorderLayoutPolicy) -> None:
        """Store layout policy used to turn selected targets into layout results."""

        self._layout_policy = layout_policy

    def move_horizontally(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
        *,
        step: int,
    ) -> PromptReorderKeyboardNavigationResult:
        """Return the proposed same-row keyboard move for the supplied step."""

        lane_map = PromptReorderKeyboardLaneMap(navigation_input.drop_target_lanes)
        current_occurrence = self._current_effective_occurrence(
            navigation_input,
            lane_map=lane_map,
        )
        current_target = (
            None if current_occurrence is None else current_occurrence.target
        )
        if current_occurrence is None:
            return self._no_op("missing_context")

        target_occurrences = lane_map.occurrences
        if not target_occurrences:
            return self._no_op("no_slot_targets")
        try:
            current_index = target_occurrences.index(current_occurrence)
        except ValueError:
            return self._no_op("current_target_not_visible")

        destination_occurrence = self._next_distinct_target_occurrence(
            target_occurrences,
            current_index=current_index,
            step=step,
            current_target=current_target,
        )
        if destination_occurrence is None:
            return self._no_op("boundary")

        if (
            destination_occurrence.target == current_target
            and destination_occurrence.center_x == navigation_input.preferred_x
        ):
            return self._no_op("unchanged_target")
        return self._apply_keyboard_drop_target(
            navigation_input,
            destination_occurrence.target,
            preferred_x=destination_occurrence.center_x,
            allow_unchanged_layout=destination_occurrence.target == current_target,
        )

    @staticmethod
    def _next_distinct_target_occurrence(
        target_occurrences: tuple[PromptReorderKeyboardTargetOccurrence, ...],
        *,
        current_index: int,
        step: int,
        current_target: PromptReorderDropTarget | None,
    ) -> PromptReorderKeyboardTargetOccurrence | None:
        """Return the next logical target, skipping repeated visual occurrences."""

        target_index = current_index
        while True:
            target_index += step
            if not 0 <= target_index < len(target_occurrences):
                return None
            destination_occurrence = target_occurrences[target_index]
            if destination_occurrence.target != current_target:
                return destination_occurrence

    def move_vertically(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
        *,
        direction: int,
    ) -> PromptReorderKeyboardNavigationResult:
        """Return the proposed lane-to-lane keyboard move for the direction."""

        lane_map = PromptReorderKeyboardLaneMap(navigation_input.drop_target_lanes)
        current_occurrence = self._current_effective_occurrence(
            navigation_input,
            lane_map=lane_map,
        )
        current_target = (
            None if current_occurrence is None else current_occurrence.target
        )
        if current_occurrence is None:
            return self._no_op("missing_context")

        preferred_x = navigation_input.preferred_x
        if preferred_x is None:
            preferred_x = current_occurrence.center_x
        current_lane_index = current_occurrence.lane_index
        if current_lane_index is None:
            return self._no_op("missing_lane")

        destination_lane_index = current_lane_index + direction
        if not 0 <= destination_lane_index < len(navigation_input.drop_target_lanes):
            destination_visual = lane_map.edge_target_visual_for_lane(
                current_lane_index,
                direction=direction,
            )
        else:
            destination_visual = lane_map.target_visual_for_lane(
                destination_lane_index,
                preferred_x=preferred_x,
            )
        if destination_visual is None:
            return self._no_op("missing_destination")
        if (
            destination_visual.target == current_target
            and destination_visual.center_x == preferred_x
        ):
            return self._no_op("unchanged_target")
        return self._apply_keyboard_drop_target(
            navigation_input,
            destination_visual.target,
            preferred_x=destination_visual.center_x,
            allow_unchanged_layout=destination_visual.target == current_target,
        )

    def apply_keyboard_drop_target(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderKeyboardNavigationResult:
        """Return the proposed layout/order for one selected keyboard target."""

        if (
            navigation_input.active_segment_index is None
            or navigation_input.current_layout_view is None
            or navigation_input.document_view is None
        ):
            return self._no_op("missing_context")

        preferred_x = PromptReorderKeyboardLaneMap(
            navigation_input.drop_target_lanes
        ).target_center_x(
            drop_target,
            preferred_x=navigation_input.preferred_x,
        )
        return self._apply_keyboard_drop_target(
            navigation_input,
            drop_target,
            preferred_x=preferred_x,
            allow_unchanged_layout=False,
        )

    def _apply_keyboard_drop_target(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
        drop_target: PromptReorderDropTarget,
        *,
        preferred_x: float,
        allow_unchanged_layout: bool,
    ) -> PromptReorderKeyboardNavigationResult:
        """Return the proposed layout/order for one selected visual occurrence."""

        if (
            navigation_input.active_segment_index is None
            or navigation_input.current_layout_view is None
            or navigation_input.document_view is None
        ):
            return self._no_op("missing_context")

        base_drag_state = navigation_input.base_drag_state
        if base_drag_state is None:
            return self._no_op("missing_context")
        proposed_state = self._layout_policy.build_preview_drop_state(
            navigation_input.document_view,
            base_drag_state,
            dragged_segment_index=navigation_input.active_segment_index,
            drop_target=drop_target,
        )
        proposed_layout_view = proposed_state.layout_view
        if (
            proposed_layout_view == navigation_input.current_layout_view
            and not allow_unchanged_layout
        ):
            return self._no_op("unchanged_layout")

        proposed_base_drag_state = self._layout_policy.build_base_drag_state(
            navigation_input.document_view,
            proposed_state.reorder_state,
            current_layout_view=proposed_layout_view,
            dragged_segment_index=navigation_input.active_segment_index,
        )
        return PromptReorderKeyboardNavigationResult(
            moved=True,
            destination_target=drop_target,
            preferred_x=preferred_x,
            proposed_state=proposed_state,
            proposed_base_drag_state=proposed_base_drag_state,
            ordered_segment_indices=self._layout_policy.reorder_layout_chip_indices(
                proposed_layout_view
            ),
        )

    def current_effective_drop_target(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
    ) -> PromptReorderDropTarget | None:
        """Return the explicit active target or resolve one from the current layout."""

        occurrence = self.current_effective_occurrence(navigation_input)
        if occurrence is not None:
            return occurrence.target
        return None

    def current_effective_occurrence(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
    ) -> PromptReorderKeyboardTargetOccurrence | None:
        """Return the concrete prepared-lane occurrence for keyboard movement."""

        return self._current_effective_occurrence(
            navigation_input,
            lane_map=PromptReorderKeyboardLaneMap(navigation_input.drop_target_lanes),
        )

    def _current_effective_occurrence(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
        *,
        lane_map: PromptReorderKeyboardLaneMap,
    ) -> PromptReorderKeyboardTargetOccurrence | None:
        """Resolve the concrete occurrence using one indexed lane snapshot."""

        if navigation_input.active_target is not None:
            occurrence = lane_map.occurrence_for_target(
                navigation_input.active_target,
                preferred_x=navigation_input.preferred_x,
                active_segment_center=None,
            )
            return occurrence
        target = self._resolve_drop_target_for_current_layout(
            navigation_input,
            lane_map=lane_map,
        )
        if target is None:
            return None
        occurrence = lane_map.occurrence_for_target(
            target,
            preferred_x=navigation_input.preferred_x,
            active_segment_center=navigation_input.active_segment_center,
        )
        if occurrence is not None:
            return occurrence
        if isinstance(target, PromptLineDropTarget):
            return lane_map.trailing_blank_origin_for_hidden_final_row(target)
        return None

    def resolve_drop_target_for_current_layout(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
    ) -> PromptReorderDropTarget | None:
        """Resolve the target whose preview layout matches the current order."""

        return self._resolve_drop_target_for_current_layout(
            navigation_input,
            lane_map=PromptReorderKeyboardLaneMap(navigation_input.drop_target_lanes),
        )

    def _resolve_drop_target_for_current_layout(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
        *,
        lane_map: PromptReorderKeyboardLaneMap,
    ) -> PromptReorderDropTarget | None:
        """Resolve the current semantic target using one indexed lane snapshot."""

        if (
            navigation_input.active_segment_index is None
            or navigation_input.current_layout_view is None
            or navigation_input.document_view is None
        ):
            return None
        row_position_target = self._line_target_for_active_row_position(
            navigation_input.current_layout_view,
            active_segment_index=navigation_input.active_segment_index,
        )
        if row_position_target is not None:
            return row_position_target
        candidate_targets = lane_map.visible_targets
        for candidate_target in candidate_targets:
            base_drag_state = navigation_input.base_drag_state
            if base_drag_state is None:
                return None
            candidate_layout = self._layout_policy.build_preview_drop_state(
                navigation_input.document_view,
                base_drag_state,
                dragged_segment_index=navigation_input.active_segment_index,
                drop_target=candidate_target,
            ).layout_view
            if candidate_layout == navigation_input.current_layout_view:
                return candidate_target
        return None

    @staticmethod
    def _line_target_for_active_row_position(
        current_layout_view: PromptReorderLayoutView,
        *,
        active_segment_index: int,
    ) -> PromptLineDropTarget | None:
        """Return the active chip's current same-row insertion target."""

        for row in current_layout_view.rows:
            try:
                insertion_index = row.chip_indices.index(active_segment_index)
            except ValueError:
                continue
            return PromptLineDropTarget(
                row_index=row.row_index,
                insertion_index=insertion_index,
            )
        return None

    @staticmethod
    def _no_op(
        reason: PromptReorderKeyboardNoOpReason,
    ) -> PromptReorderKeyboardNavigationResult:
        """Return a typed no-op result for a boundary or invalid context."""

        return PromptReorderKeyboardNavigationResult(
            moved=False,
            destination_target=None,
            preferred_x=None,
            proposed_state=None,
            proposed_base_drag_state=None,
            ordered_segment_indices=(),
            no_op_reason=reason,
        )


__all__ = [
    "PromptReorderKeyboardNavigationInput",
    "PromptReorderKeyboardNavigationResult",
    "PromptReorderKeyboardNavigator",
    "PromptReorderKeyboardNoOpReason",
    "PromptReorderLayoutPolicy",
]
