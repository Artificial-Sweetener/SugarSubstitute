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

"""Index prepared reorder lanes for keyboard navigation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
)

from .reorder_drop_targets import (
    PromptReorderBlankLineDropLane,
    PromptReorderDropLane,
    PromptReorderDropTargetVisual,
    PromptReorderRowDropLane,
)


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardTargetVisual:
    """Identify one lane-local keyboard destination."""

    target: PromptReorderDropTarget
    center_x: float


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardTargetOccurrence:
    """Identify one concrete target occurrence in the prepared lane graph."""

    target: PromptReorderDropTarget
    lane_index: int
    occurrence_index: int
    center_x: float
    center_y: float


class PromptReorderKeyboardLaneMap:
    """Own keyboard-only queries over one immutable drop-lane snapshot."""

    def __init__(self, lanes: tuple[PromptReorderDropLane, ...]) -> None:
        """Index concrete occurrences once for one keyboard action."""

        self._lanes = lanes
        self._occurrences = _target_occurrences_in_reading_order(lanes)

    @property
    def lanes(self) -> tuple[PromptReorderDropLane, ...]:
        """Return the immutable lanes represented by this map."""

        return self._lanes

    @property
    def occurrences(self) -> tuple[PromptReorderKeyboardTargetOccurrence, ...]:
        """Return every concrete target occurrence in reading order."""

        return self._occurrences

    @property
    def visible_targets(self) -> tuple[PromptReorderDropTarget, ...]:
        """Return visible targets in stable occurrence order."""

        return tuple(occurrence.target for occurrence in self._occurrences)

    def occurrence_for_target(
        self,
        target: PromptReorderDropTarget,
        *,
        preferred_x: float | None,
        active_segment_center: tuple[float, float] | None,
    ) -> PromptReorderKeyboardTargetOccurrence | None:
        """Return the best concrete occurrence for a semantic target."""

        matching = tuple(
            occurrence
            for occurrence in self._occurrences
            if occurrence.target == target
        )
        if not matching:
            return None
        if preferred_x is not None:
            return min(
                matching,
                key=lambda occurrence: abs(occurrence.center_x - preferred_x),
            )
        if active_segment_center is not None:
            active_x, active_y = active_segment_center
            return min(
                matching,
                key=lambda occurrence: (
                    (occurrence.center_x - active_x) ** 2
                    + (occurrence.center_y - active_y) ** 2
                ),
            )
        return matching[0]

    def trailing_blank_origin_for_hidden_final_row(
        self,
        target: PromptLineDropTarget,
    ) -> PromptReorderKeyboardTargetOccurrence | None:
        """Map a hidden final-row origin to the trailing blank-line lane."""

        max_visible_row_index = max(
            (
                lane.row_index
                for lane in self._lanes
                if isinstance(lane, PromptReorderRowDropLane)
            ),
            default=None,
        )
        if max_visible_row_index is None or target.row_index <= max_visible_row_index:
            return None
        blank_occurrences = tuple(
            occurrence
            for occurrence in self._occurrences
            if isinstance(occurrence.target, PromptGapBlankLineDropTarget)
        )
        if not blank_occurrences:
            return None
        return max(
            blank_occurrences,
            key=lambda occurrence: (
                cast(PromptGapBlankLineDropTarget, occurrence.target).gap_index,
                cast(
                    PromptGapBlankLineDropTarget,
                    occurrence.target,
                ).blank_line_index,
            ),
        )

    def target_visual_for_lane(
        self,
        lane_index: int,
        *,
        preferred_x: float,
    ) -> PromptReorderKeyboardTargetVisual | None:
        """Resolve the lane-local destination nearest the preferred x."""

        if not 0 <= lane_index < len(self._lanes):
            return None
        lane = self._lanes[lane_index]
        if isinstance(lane, PromptReorderBlankLineDropLane):
            return PromptReorderKeyboardTargetVisual(
                target=lane.target,
                center_x=lane.hit_rect.center().x(),
            )
        visual = _row_slot_visual_nearest_x(lane, preferred_x=preferred_x)
        if visual is None:
            return None
        return PromptReorderKeyboardTargetVisual(
            target=visual.target,
            center_x=visual.hit_rect.center().x(),
        )

    def edge_target_visual_for_lane(
        self,
        lane_index: int,
        *,
        direction: int,
    ) -> PromptReorderKeyboardTargetVisual | None:
        """Resolve the edge-clamp destination for one visible lane."""

        if not 0 <= lane_index < len(self._lanes):
            return None
        lane = self._lanes[lane_index]
        if isinstance(lane, PromptReorderBlankLineDropLane):
            return PromptReorderKeyboardTargetVisual(
                target=lane.target,
                center_x=lane.hit_rect.center().x(),
            )
        if not lane.slot_visuals:
            return None
        visual = lane.slot_visuals[0] if direction < 0 else lane.slot_visuals[-1]
        return PromptReorderKeyboardTargetVisual(
            target=visual.target,
            center_x=visual.hit_rect.center().x(),
        )

    def target_center_x(
        self,
        target: PromptReorderDropTarget,
        *,
        preferred_x: float | None,
    ) -> float:
        """Return the target center preserving prior horizontal intent."""

        matching = tuple(
            occurrence
            for occurrence in self._occurrences
            if occurrence.target == target
        )
        if not matching:
            return 0.0
        if preferred_x is None:
            return matching[0].center_x
        return min(
            matching,
            key=lambda occurrence: abs(occurrence.center_x - preferred_x),
        ).center_x


def _target_occurrences_in_reading_order(
    lanes: tuple[PromptReorderDropLane, ...],
) -> tuple[PromptReorderKeyboardTargetOccurrence, ...]:
    """Index every concrete row and blank-line target occurrence."""

    occurrences: list[PromptReorderKeyboardTargetOccurrence] = []
    for lane_index, lane in enumerate(lanes):
        if isinstance(lane, PromptReorderBlankLineDropLane):
            center = lane.hit_rect.center()
            occurrences.append(
                PromptReorderKeyboardTargetOccurrence(
                    target=lane.target,
                    lane_index=lane_index,
                    occurrence_index=0,
                    center_x=center.x(),
                    center_y=center.y(),
                )
            )
            continue
        occurrences.extend(
            PromptReorderKeyboardTargetOccurrence(
                target=visual.target,
                lane_index=lane_index,
                occurrence_index=occurrence_index,
                center_x=visual.hit_rect.center().x(),
                center_y=visual.hit_rect.center().y(),
            )
            for occurrence_index, visual in enumerate(lane.slot_visuals)
        )
    return tuple(occurrences)


def _row_slot_visual_nearest_x(
    lane: PromptReorderRowDropLane,
    *,
    preferred_x: float,
) -> PromptReorderDropTargetVisual | None:
    """Return the populated-row slot nearest the preferred x."""

    return min(
        lane.slot_visuals,
        key=lambda visual: abs(visual.hit_rect.center().x() - preferred_x),
        default=None,
    )


__all__ = [
    "PromptReorderKeyboardLaneMap",
    "PromptReorderKeyboardTargetOccurrence",
    "PromptReorderKeyboardTargetVisual",
]
