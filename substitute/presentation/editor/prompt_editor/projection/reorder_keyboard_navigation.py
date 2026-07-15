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
from typing import Literal, Protocol, cast

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderStateView,
)

from .reorder_drop_targets import (
    PromptReorderBlankLineDropLane,
    PromptReorderDropLane,
    PromptReorderDropTargetVisual,
    PromptReorderRowDropLane,
    lane_matches_target,
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

    def build_base_drag_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Build the prepared layout used while one segment is lifted."""

    def build_preview_drop_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Build the prepared preview layout for a supplied drop target."""

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return the segment index order represented by a prepared layout."""

    def build_base_drag_reorder_state_from_state(
        self,
        state_view: PromptReorderStateView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderStateView:
        """Build authoritative hidden-drag state from a reorder source state."""

    def build_preview_drop_reorder_state_from_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        base_drag_layout_view: PromptReorderLayoutView | None,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderStateView:
        """Build authoritative preview state from a reorder source state."""


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardNavigationInput:
    """Carry prepared widget-free state for one keyboard navigation request."""

    document_view: PromptDocumentView | None
    current_layout_view: PromptReorderLayoutView | None
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
    proposed_layout_view: PromptReorderLayoutView | None
    proposed_base_drag_layout_view: PromptReorderLayoutView | None
    ordered_segment_indices: tuple[int, ...]
    no_op_reason: PromptReorderKeyboardNoOpReason | None = None


@dataclass(frozen=True, slots=True)
class _KeyboardTargetVisual:
    """Identify one visible keyboard target occurrence inside a prepared lane."""

    target: PromptReorderDropTarget
    center_x: float


@dataclass(frozen=True, slots=True)
class _KeyboardTargetOccurrence:
    """Identify one concrete keyboard target occurrence in the prepared lane graph."""

    target: PromptReorderDropTarget
    lane_index: int
    occurrence_index: int
    center_x: float
    center_y: float


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

        current_occurrence = self.current_effective_occurrence(navigation_input)
        current_target = (
            None if current_occurrence is None else current_occurrence.target
        )
        if current_occurrence is None:
            return self._no_op("missing_context")

        target_occurrences = self._target_occurrences_in_reading_order(
            navigation_input.drop_target_lanes
        )
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
        target_occurrences: tuple[_KeyboardTargetOccurrence, ...],
        *,
        current_index: int,
        step: int,
        current_target: PromptReorderDropTarget | None,
    ) -> _KeyboardTargetOccurrence | None:
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

        current_occurrence = self.current_effective_occurrence(navigation_input)
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
            destination_visual = self.edge_target_visual_for_lane(
                navigation_input.drop_target_lanes[current_lane_index],
                direction=direction,
            )
        else:
            destination_visual = self.target_visual_for_lane(
                navigation_input.drop_target_lanes[destination_lane_index],
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

        preferred_x = self.target_center_x(
            drop_target,
            navigation_input.drop_target_lanes,
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

        proposed_layout_view = (
            self._layout_policy.build_preview_drop_layout_view_from_layout(
                navigation_input.document_view,
                navigation_input.current_layout_view,
                dragged_segment_index=navigation_input.active_segment_index,
                drop_target=drop_target,
            )
        )
        if (
            proposed_layout_view == navigation_input.current_layout_view
            and not allow_unchanged_layout
        ):
            return self._no_op("unchanged_layout")

        proposed_base_drag_layout_view = (
            self._layout_policy.build_base_drag_layout_view_from_layout(
                navigation_input.document_view,
                proposed_layout_view,
                dragged_segment_index=navigation_input.active_segment_index,
            )
        )
        return PromptReorderKeyboardNavigationResult(
            moved=True,
            destination_target=drop_target,
            preferred_x=preferred_x,
            proposed_layout_view=proposed_layout_view,
            proposed_base_drag_layout_view=proposed_base_drag_layout_view,
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
    ) -> _KeyboardTargetOccurrence | None:
        """Return the concrete prepared-lane occurrence for keyboard movement."""

        if navigation_input.active_target is not None:
            occurrence = self._occurrence_for_target(
                navigation_input.active_target,
                navigation_input.drop_target_lanes,
                preferred_x=navigation_input.preferred_x,
                active_segment_center=None,
            )
            return occurrence
        target = self.resolve_drop_target_for_current_layout(navigation_input)
        if target is None:
            return None
        occurrence = self._occurrence_for_target(
            target,
            navigation_input.drop_target_lanes,
            preferred_x=navigation_input.preferred_x,
            active_segment_center=navigation_input.active_segment_center,
        )
        if occurrence is not None:
            return occurrence
        if isinstance(target, PromptLineDropTarget):
            return self._trailing_blank_line_origin_for_hidden_final_row(
                target,
                navigation_input.drop_target_lanes,
            )
        return None

    def resolve_drop_target_for_current_layout(
        self,
        navigation_input: PromptReorderKeyboardNavigationInput,
    ) -> PromptReorderDropTarget | None:
        """Resolve the target whose preview layout matches the current order."""

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
        candidate_targets = self.all_visible_drop_targets(
            navigation_input.drop_target_lanes
        )
        for candidate_target in candidate_targets:
            candidate_layout = (
                self._layout_policy.build_preview_drop_layout_view_from_layout(
                    navigation_input.document_view,
                    navigation_input.current_layout_view,
                    dragged_segment_index=navigation_input.active_segment_index,
                    drop_target=candidate_target,
                )
            )
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

    @classmethod
    def _occurrence_for_target(
        cls,
        target: PromptReorderDropTarget,
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
        *,
        preferred_x: float | None,
        active_segment_center: tuple[float, float] | None,
    ) -> _KeyboardTargetOccurrence | None:
        """Return the concrete occurrence for one target and navigation hint."""

        matching_occurrences = tuple(
            occurrence
            for occurrence in cls._target_occurrences_in_reading_order(
                drop_target_lanes
            )
            if occurrence.target == target
        )
        if not matching_occurrences:
            return None
        if preferred_x is not None:
            return min(
                matching_occurrences,
                key=lambda occurrence: abs(occurrence.center_x - preferred_x),
            )
        if active_segment_center is not None:
            active_x, active_y = active_segment_center
            return min(
                matching_occurrences,
                key=lambda occurrence: (
                    (occurrence.center_x - active_x) ** 2
                    + (occurrence.center_y - active_y) ** 2
                ),
            )
        return matching_occurrences[0]

    @staticmethod
    def all_visible_drop_targets(
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
    ) -> tuple[PromptReorderDropTarget, ...]:
        """Return every visible row-slot and blank-line target in stable order."""

        targets: list[PromptReorderDropTarget] = []
        for lane in drop_target_lanes:
            if isinstance(lane, PromptReorderBlankLineDropLane):
                targets.append(lane.target)
                continue
            targets.extend(
                cast(PromptLineDropTarget, visual.target)
                for visual in lane.slot_visuals
            )
        return tuple(targets)

    @staticmethod
    def row_slot_targets_in_reading_order(
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
    ) -> tuple[PromptLineDropTarget, ...]:
        """Return visible populated-row insertion targets in reading order."""

        targets: list[PromptLineDropTarget] = []
        for lane in drop_target_lanes:
            if isinstance(lane, PromptReorderBlankLineDropLane):
                continue
            targets.extend(
                cast(PromptLineDropTarget, visual.target)
                for visual in lane.slot_visuals
            )
        return tuple(targets)

    @staticmethod
    def lane_index_for_target(
        target: PromptReorderDropTarget,
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
        *,
        preferred_x: float | None = None,
    ) -> int | None:
        """Return the visible lane index that owns the supplied target."""

        best_lane_index: int | None = None
        best_distance: float | None = None
        for lane_index, lane in enumerate(drop_target_lanes):
            target_center_x = target_center_x_for_lane(lane, target)
            if target_center_x is None:
                continue
            if preferred_x is None:
                return lane_index
            distance = abs(target_center_x - preferred_x)
            if best_distance is None or distance < best_distance:
                best_lane_index = lane_index
                best_distance = distance
        return best_lane_index

    def target_for_lane(
        self,
        lane: PromptReorderDropLane,
        *,
        preferred_x: float,
    ) -> PromptReorderDropTarget | None:
        """Resolve one lane-local drop target for keyboard vertical movement."""

        target_visual = self.target_visual_for_lane(lane, preferred_x=preferred_x)
        if target_visual is None:
            return None
        return target_visual.target

    def target_visual_for_lane(
        self,
        lane: PromptReorderDropLane,
        *,
        preferred_x: float,
    ) -> _KeyboardTargetVisual | None:
        """Resolve one lane-local visual target for keyboard vertical movement."""

        if isinstance(lane, PromptReorderBlankLineDropLane):
            return _KeyboardTargetVisual(
                target=lane.target,
                center_x=lane.hit_rect.center().x(),
            )
        visual = self.row_slot_visual_nearest_x(lane, preferred_x=preferred_x)
        if visual is None:
            return None
        return _KeyboardTargetVisual(
            target=visual.target,
            center_x=visual.hit_rect.center().x(),
        )

    @staticmethod
    def edge_target_for_lane(
        lane: PromptReorderDropLane,
        *,
        direction: int,
    ) -> PromptReorderDropTarget | None:
        """Resolve the edge-clamp destination when no further lane exists."""

        if isinstance(lane, PromptReorderBlankLineDropLane):
            return lane.target
        if not lane.slot_visuals:
            return None
        if direction < 0:
            return cast(PromptLineDropTarget, lane.slot_visuals[0].target)
        return cast(PromptLineDropTarget, lane.slot_visuals[-1].target)

    @staticmethod
    def edge_target_visual_for_lane(
        lane: PromptReorderDropLane,
        *,
        direction: int,
    ) -> _KeyboardTargetVisual | None:
        """Resolve the edge-clamp visual occurrence when no further lane exists."""

        if isinstance(lane, PromptReorderBlankLineDropLane):
            return _KeyboardTargetVisual(
                target=lane.target,
                center_x=lane.hit_rect.center().x(),
            )
        if not lane.slot_visuals:
            return None
        visual = lane.slot_visuals[0] if direction < 0 else lane.slot_visuals[-1]
        return _KeyboardTargetVisual(
            target=visual.target,
            center_x=visual.hit_rect.center().x(),
        )

    @staticmethod
    def row_slot_target_nearest_x(
        lane: PromptReorderRowDropLane,
        *,
        preferred_x: float,
    ) -> PromptLineDropTarget | None:
        """Return the populated-row slot whose center is nearest preferred x."""

        best_target: PromptLineDropTarget | None = None
        best_distance: float | None = None
        for visual in lane.slot_visuals:
            target = cast(PromptLineDropTarget, visual.target)
            distance = abs(visual.hit_rect.center().x() - preferred_x)
            if best_distance is None or distance < best_distance:
                best_target = target
                best_distance = distance
        return best_target

    @staticmethod
    def row_slot_visual_nearest_x(
        lane: PromptReorderRowDropLane,
        *,
        preferred_x: float,
    ) -> PromptReorderDropTargetVisual | None:
        """Return the populated-row visual slot nearest to the preferred x."""

        best_visual: PromptReorderDropTargetVisual | None = None
        best_distance: float | None = None
        for visual in lane.slot_visuals:
            distance = abs(visual.hit_rect.center().x() - preferred_x)
            if best_distance is None or distance < best_distance:
                best_visual = visual
                best_distance = distance
        return best_visual

    @staticmethod
    def target_center_x(
        target: PromptReorderDropTarget,
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
        *,
        preferred_x: float | None = None,
    ) -> float:
        """Return the horizontal center used to preserve keyboard lane intent."""

        best_center_x: float | None = None
        best_distance: float | None = None
        for lane in drop_target_lanes:
            center_x = target_center_x_for_lane(lane, target)
            if center_x is None:
                continue
            if preferred_x is None:
                return center_x
            distance = abs(center_x - preferred_x)
            if best_distance is None or distance < best_distance:
                best_center_x = center_x
                best_distance = distance
        if best_center_x is None:
            return 0.0
        return best_center_x

    @staticmethod
    def _row_slot_visuals_in_reading_order(
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
    ) -> tuple[_KeyboardTargetVisual, ...]:
        """Return visible populated-row target occurrences in reading order."""

        targets: list[_KeyboardTargetVisual] = []
        for lane in drop_target_lanes:
            if isinstance(lane, PromptReorderBlankLineDropLane):
                continue
            targets.extend(
                _KeyboardTargetVisual(
                    target=visual.target,
                    center_x=visual.hit_rect.center().x(),
                )
                for visual in lane.slot_visuals
            )
        return tuple(targets)

    @staticmethod
    def _target_occurrences_in_reading_order(
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
    ) -> tuple[_KeyboardTargetOccurrence, ...]:
        """Return every concrete row and blank-line target occurrence."""

        occurrences: list[_KeyboardTargetOccurrence] = []
        for lane_index, lane in enumerate(drop_target_lanes):
            if isinstance(lane, PromptReorderBlankLineDropLane):
                center = lane.hit_rect.center()
                occurrences.append(
                    _KeyboardTargetOccurrence(
                        target=lane.target,
                        lane_index=lane_index,
                        occurrence_index=0,
                        center_x=center.x(),
                        center_y=center.y(),
                    )
                )
                continue
            occurrences.extend(
                _KeyboardTargetOccurrence(
                    target=visual.target,
                    lane_index=lane_index,
                    occurrence_index=occurrence_index,
                    center_x=visual.hit_rect.center().x(),
                    center_y=visual.hit_rect.center().y(),
                )
                for occurrence_index, visual in enumerate(lane.slot_visuals)
            )
        return tuple(occurrences)

    @staticmethod
    def _trailing_blank_line_origin_for_hidden_final_row(
        target: PromptLineDropTarget,
        drop_target_lanes: tuple[PromptReorderDropLane, ...],
    ) -> _KeyboardTargetOccurrence | None:
        """Map a hidden final-row origin to the trailing after-last blank lane."""

        max_visible_row_index: int | None = None
        trailing_blank_origin: _KeyboardTargetOccurrence | None = None
        for lane_index, lane in enumerate(drop_target_lanes):
            if isinstance(lane, PromptReorderRowDropLane):
                if (
                    max_visible_row_index is None
                    or lane.row_index > max_visible_row_index
                ):
                    max_visible_row_index = lane.row_index
                continue
            center = lane.hit_rect.center()
            candidate = _KeyboardTargetOccurrence(
                target=lane.target,
                lane_index=lane_index,
                occurrence_index=0,
                center_x=center.x(),
                center_y=center.y(),
            )
            if trailing_blank_origin is None:
                trailing_blank_origin = candidate
                continue
            current_target = cast(
                PromptGapBlankLineDropTarget,
                trailing_blank_origin.target,
            )
            candidate_target = lane.target
            if candidate_target.gap_index > current_target.gap_index or (
                candidate_target.gap_index == current_target.gap_index
                and candidate_target.blank_line_index > current_target.blank_line_index
            ):
                trailing_blank_origin = candidate
        if max_visible_row_index is None or target.row_index <= max_visible_row_index:
            return None
        return trailing_blank_origin

    @staticmethod
    def _target_visual_index(
        target: PromptLineDropTarget,
        target_visuals: tuple[_KeyboardTargetVisual, ...],
        *,
        preferred_x: float | None,
    ) -> int | None:
        """Return the visible target occurrence matching target and x intent."""

        best_index: int | None = None
        best_distance: float | None = None
        for index, visual in enumerate(target_visuals):
            if visual.target != target:
                continue
            if preferred_x is None:
                return index
            distance = abs(visual.center_x - preferred_x)
            if best_distance is None or distance < best_distance:
                best_index = index
                best_distance = distance
        return best_index

    @staticmethod
    def _no_op(
        reason: PromptReorderKeyboardNoOpReason,
    ) -> PromptReorderKeyboardNavigationResult:
        """Return a typed no-op result for a boundary or invalid context."""

        return PromptReorderKeyboardNavigationResult(
            moved=False,
            destination_target=None,
            preferred_x=None,
            proposed_layout_view=None,
            proposed_base_drag_layout_view=None,
            ordered_segment_indices=(),
            no_op_reason=reason,
        )


def target_center_x_for_lane(
    lane: PromptReorderDropLane,
    target: PromptReorderDropTarget,
) -> float | None:
    """Return the target center x for one lane occurrence when present."""

    if isinstance(lane, PromptReorderBlankLineDropLane):
        if lane.target == target:
            return lane.hit_rect.center().x()
        return None
    if not lane_matches_target(lane, target):
        return None
    for visual in lane.slot_visuals:
        if visual.target == target:
            return visual.hit_rect.center().x()
    return None


__all__ = [
    "PromptReorderKeyboardNavigationInput",
    "PromptReorderKeyboardNavigationResult",
    "PromptReorderKeyboardNavigator",
    "PromptReorderKeyboardNoOpReason",
    "PromptReorderLayoutPolicy",
]
