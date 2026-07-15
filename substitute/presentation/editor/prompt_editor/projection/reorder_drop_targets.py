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

"""Resolve prompt reorder pointer targets from prepared projection geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QPointF, QRectF, QSizeF

from substitute.application.prompt_editor import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
)

from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_point_context,
    reorder_drag_rect_context,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
    placement_for_drag_rect,
    placement_geometry_context,
)


@dataclass(frozen=True, slots=True)
class PromptReorderDropTargetVisual:
    """Describe one prepared drag destination and the rect used to hit test it."""

    target: PromptReorderDropTarget
    hit_rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptReorderRowDropLane:
    """Describe one populated-row hit lane plus its stable insertion slots."""

    row_index: int
    visual_row_index: int
    hit_rect: QRectF
    slot_visuals: tuple[PromptReorderDropTargetVisual, ...]


@dataclass(frozen=True, slots=True)
class PromptReorderBlankLineDropLane:
    """Describe one blank-line hit lane that should win on vertical intent alone."""

    target: PromptGapBlankLineDropTarget
    hit_rect: QRectF


type PromptReorderDropLane = PromptReorderRowDropLane | PromptReorderBlankLineDropLane


@dataclass(frozen=True, slots=True)
class PromptReorderDropTargetResolverInput:
    """Carry one widget-free prepared-geometry target-resolution request.

    Writer:
        `PromptReorderInteractionGeometry` publishes prepared lanes, target
        visuals, placement geometry, and active target state for one pointer
        intent rect.
    Readers:
        `PromptReorderDropTargetTracker` reads this snapshot without accessing
        QWidget state or rebuilding projection data.
    State kind:
        Projection geometry state. It has no source mutation authority.
    """

    drop_lanes: tuple[PromptReorderDropLane, ...]
    target_visuals: tuple[PromptReorderDropTargetVisual, ...]
    active_target: PromptReorderDropTarget | None
    drag_rect: QRectF
    geometry_generation_id: int | None
    placement_snapshot: PromptReorderPlacementSnapshot | None = None
    active_placement: PromptReorderPlacementGeometry | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderDropTargetResolution:
    """Describe one drag-rect target-selection result."""

    target: PromptReorderDropTarget | None
    active_placement: PromptReorderPlacementGeometry | None
    changed: bool
    no_lane: bool = False
    fast_path_reason: str = "target_changed"
    geometry_generation_id: int | None = None


class PromptReorderDropTargetTracker:
    """Resolve pointer drop targets from prepared projection-owned geometry."""

    def resolve(
        self,
        resolver_input: PromptReorderDropTargetResolverInput,
        *,
        gesture_id: int | None = None,
        event_id: int | None = None,
    ) -> PromptReorderDropTargetResolution:
        """Return the target selected by the supplied drag intent rect."""

        if (
            resolver_input.placement_snapshot is not None
            and resolver_input.placement_snapshot.placements
        ):
            return self._resolve_from_placements(
                resolver_input,
                gesture_id=gesture_id,
                event_id=event_id,
            )

        if not resolver_input.drop_lanes:
            log_reorder_drag_event(
                "drop_target.no_lanes",
                gesture_id=gesture_id,
                event_id=event_id,
                **reorder_drag_rect_context(resolver_input.drag_rect, prefix="intent"),
            )
            return self._resolution(
                target=None,
                active_placement=None,
                active_target=resolver_input.active_target,
                no_lane=True,
                fast_path_reason="no_lanes",
                geometry_generation_id=resolver_input.geometry_generation_id,
            )

        lane = self.drop_lane_for_drag_rect(
            resolver_input.drag_rect,
            drop_lanes=resolver_input.drop_lanes,
            active_target=resolver_input.active_target,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        if lane is None:
            return self._resolution(
                target=None,
                active_placement=None,
                active_target=resolver_input.active_target,
                fast_path_reason="no_lane",
                geometry_generation_id=resolver_input.geometry_generation_id,
            )
        if isinstance(lane, PromptReorderBlankLineDropLane):
            return self._resolution(
                target=lane.target,
                active_placement=None,
                active_target=resolver_input.active_target,
                geometry_generation_id=resolver_input.geometry_generation_id,
            )
        target = self.row_slot_target_for_drag_rect(
            lane,
            resolver_input.drag_rect,
            active_target=resolver_input.active_target,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return self._resolution(
            target=target,
            active_placement=None,
            active_target=resolver_input.active_target,
            geometry_generation_id=resolver_input.geometry_generation_id,
        )

    def drop_target_at_position(
        self,
        point: QPointF,
        *,
        drop_lanes: tuple[PromptReorderDropLane, ...],
        active_target: PromptReorderDropTarget | None,
        geometry_generation_id: int | None,
    ) -> PromptReorderDropTarget | None:
        """Resolve a point-sized fallback target without QWidget state."""

        return self.resolve(
            PromptReorderDropTargetResolverInput(
                drop_lanes=drop_lanes,
                target_visuals=(),
                active_target=active_target,
                drag_rect=point_drop_rect(point),
                geometry_generation_id=geometry_generation_id,
            )
        ).target

    def drop_lane_at_position(
        self,
        point: QPointF,
        *,
        drop_lanes: tuple[PromptReorderDropLane, ...],
        active_target: PromptReorderDropTarget | None,
    ) -> PromptReorderDropLane | None:
        """Resolve a point-sized fallback lane without QWidget state."""

        return self.drop_lane_for_drag_rect(
            point_drop_rect(point),
            drop_lanes=drop_lanes,
            active_target=active_target,
        )

    def drop_lane_for_drag_rect(
        self,
        drag_rect: QRectF,
        *,
        drop_lanes: tuple[PromptReorderDropLane, ...],
        active_target: PromptReorderDropTarget | None,
        gesture_id: int | None = None,
        event_id: int | None = None,
    ) -> PromptReorderDropLane | None:
        """Resolve the active vertical lane from logical held-chip geometry."""

        started_at = reorder_drag_started_at()
        point = drag_rect.center()
        containing_lanes = [
            lane for lane in drop_lanes if lane.hit_rect.contains(point)
        ]
        if containing_lanes:
            active_lane = self.active_lane_from_candidates(
                containing_lanes,
                active_target=active_target,
            )
            selected = active_lane or containing_lanes[0]
            log_reorder_drag_timing(
                "drop_lane.containing_first",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                containing_lane_count=len(containing_lanes),
                lane_count=len(drop_lanes),
                lane_kind=selected.__class__.__name__,
                active_lane_matched=active_lane is not None,
                **reorder_drag_point_context(point, prefix="intent_center"),
            )
            return selected

        best_lane: PromptReorderDropLane | None = None
        best_distance: float | None = None
        for lane in drop_lanes:
            distance = axis_distance(
                axis_value=point.y(),
                start=lane.hit_rect.top(),
                end=lane.hit_rect.bottom(),
            )
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_lane = lane
                continue
            if (
                distance == best_distance
                and best_lane is not None
                and self.lane_matches_target(lane, active_target)
                and not self.lane_matches_target(best_lane, active_target)
            ):
                best_lane = lane
        log_reorder_drag_timing(
            "drop_lane.nearest",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            containing_lane_count=0,
            lane_count=len(drop_lanes),
            lane_kind="none" if best_lane is None else best_lane.__class__.__name__,
            best_distance="none" if best_distance is None else f"{best_distance:.2f}",
            **reorder_drag_point_context(point, prefix="intent_center"),
        )
        return best_lane

    def active_lane_from_candidates(
        self,
        lanes: list[PromptReorderDropLane],
        *,
        active_target: PromptReorderDropTarget | None,
    ) -> PromptReorderDropLane | None:
        """Prefer the current lane when multiple bands contain the pointer."""

        for lane in lanes:
            if self.lane_matches_target(lane, active_target):
                return lane
        return None

    @staticmethod
    def lane_matches_target(
        lane: PromptReorderDropLane,
        target: PromptReorderDropTarget | None,
    ) -> bool:
        """Return whether one prepared lane owns the supplied typed target."""

        return lane_matches_target(lane, target)

    def row_slot_target_at_position(
        self,
        lane: PromptReorderRowDropLane,
        point: QPointF,
        *,
        active_target: PromptReorderDropTarget | None,
    ) -> PromptLineDropTarget | None:
        """Resolve a point-sized fallback row slot without QWidget state."""

        return self.row_slot_target_for_drag_rect(
            lane,
            point_drop_rect(point),
            active_target=active_target,
        )

    def row_slot_target_for_drag_rect(
        self,
        lane: PromptReorderRowDropLane,
        drag_rect: QRectF,
        *,
        active_target: PromptReorderDropTarget | None,
        gesture_id: int | None = None,
        event_id: int | None = None,
    ) -> PromptLineDropTarget | None:
        """Resolve one row insertion slot from logical held-chip geometry."""

        started_at = reorder_drag_started_at()
        point = drag_rect.center()
        containing_slots = [
            visual.target
            for visual in lane.slot_visuals
            if visual.hit_rect.contains(point)
        ]
        if containing_slots:
            if (
                isinstance(active_target, PromptLineDropTarget)
                and active_target in containing_slots
            ):
                return active_target
            return cast(PromptLineDropTarget, containing_slots[0])

        best_target: PromptLineDropTarget | None = None
        best_distance: float | None = None
        for visual in lane.slot_visuals:
            distance = axis_distance(
                axis_value=point.x(),
                start=visual.hit_rect.left(),
                end=visual.hit_rect.right(),
            )
            target = cast(PromptLineDropTarget, visual.target)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_target = target
                continue
            if (
                distance == best_distance
                and best_target is not None
                and target == active_target
                and best_target != active_target
            ):
                best_target = target
        log_reorder_drag_timing(
            "row_slot.nearest",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            row_index=lane.row_index,
            visual_row_index=lane.visual_row_index,
            slot_count=len(lane.slot_visuals),
            containing_slot_count=0,
            target_kind=reorder_drag_target_kind(best_target),
            best_distance="none" if best_distance is None else f"{best_distance:.2f}",
            **reorder_drag_point_context(point, prefix="intent_center"),
        )
        return best_target

    def _resolve_from_placements(
        self,
        resolver_input: PromptReorderDropTargetResolverInput,
        *,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderDropTargetResolution:
        """Resolve a target from prepared placement geometry before lane fallback."""

        assert resolver_input.placement_snapshot is not None
        placement = placement_for_drag_rect(
            resolver_input.placement_snapshot,
            resolver_input.drag_rect,
            active_placement_id=None
            if resolver_input.active_placement is None
            else resolver_input.active_placement.placement_id,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        if placement is None:
            log_reorder_drag_timing(
                "drop_target.placement_none",
                started_at=reorder_drag_started_at(),
                gesture_id=gesture_id,
                event_id=event_id,
                placement_count=len(resolver_input.placement_snapshot.placements),
                **reorder_drag_rect_context(resolver_input.drag_rect, prefix="intent"),
            )
            return self._resolution(
                target=None,
                active_placement=None,
                active_target=resolver_input.active_target,
                fast_path_reason="placement_none",
                geometry_generation_id=resolver_input.geometry_generation_id,
            )
        log_reorder_drag_event(
            "placement_hit.selected",
            gesture_id=gesture_id,
            event_id=event_id,
            **placement_geometry_context(placement),
            **reorder_drag_rect_context(resolver_input.drag_rect, prefix="intent"),
        )
        return self._resolution(
            target=placement.target,
            active_placement=placement,
            active_target=resolver_input.active_target,
            geometry_generation_id=resolver_input.geometry_generation_id,
        )

    @staticmethod
    def _resolution(
        *,
        target: PromptReorderDropTarget | None,
        active_placement: PromptReorderPlacementGeometry | None,
        active_target: PromptReorderDropTarget | None,
        no_lane: bool = False,
        fast_path_reason: str | None = None,
        geometry_generation_id: int | None,
    ) -> PromptReorderDropTargetResolution:
        """Build one changed/unchanged result with a structural reason."""

        changed = target != active_target
        if fast_path_reason is None:
            fast_path_reason = "target_changed" if changed else "unchanged_target"
        return PromptReorderDropTargetResolution(
            target=target,
            active_placement=active_placement,
            changed=changed,
            no_lane=no_lane,
            fast_path_reason=fast_path_reason,
            geometry_generation_id=geometry_generation_id,
        )


def lane_matches_target(
    lane: PromptReorderDropLane,
    target: PromptReorderDropTarget | None,
) -> bool:
    """Return whether one prepared lane owns the supplied typed target."""

    if target is None:
        return False
    if isinstance(lane, PromptReorderBlankLineDropLane):
        return lane.target == target
    if not isinstance(target, PromptLineDropTarget):
        return False
    return any(visual.target == target for visual in lane.slot_visuals)


def axis_distance(*, axis_value: float, start: float, end: float) -> float:
    """Return the one-dimensional distance from a point to an inclusive interval."""

    if axis_value < start:
        return start - axis_value
    if axis_value > end:
        return axis_value - end
    return 0.0


def point_drop_rect(point: QPointF) -> QRectF:
    """Return a one-pixel logical drag rect centered on the supplied point."""

    return QRectF(point, QSizeF(1.0, 1.0))


__all__ = [
    "PromptReorderBlankLineDropLane",
    "PromptReorderDropLane",
    "PromptReorderDropTargetResolution",
    "PromptReorderDropTargetResolverInput",
    "PromptReorderDropTargetTracker",
    "PromptReorderDropTargetVisual",
    "PromptReorderRowDropLane",
    "axis_distance",
    "lane_matches_target",
    "point_drop_rect",
]
