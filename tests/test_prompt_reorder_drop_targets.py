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

"""Cover projection-owned prompt reorder drop-target resolution."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF

from substitute.application.prompt_editor import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_targets import (
    PromptReorderBlankLineDropLane,
    PromptReorderDropTargetResolverInput,
    PromptReorderDropTargetTracker,
    PromptReorderDropTargetVisual,
    PromptReorderRowDropLane,
    axis_distance,
    point_drop_rect,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
    reorder_placement_id_for_target,
    rect_from_centerline,
)


def _row_lane() -> PromptReorderRowDropLane:
    """Return a deterministic row lane with three insertion slots."""

    return PromptReorderRowDropLane(
        row_index=0,
        visual_row_index=0,
        hit_rect=QRectF(0.0, 0.0, 90.0, 20.0),
        slot_visuals=(
            PromptReorderDropTargetVisual(
                target=PromptLineDropTarget(row_index=0, insertion_index=0),
                hit_rect=QRectF(0.0, 0.0, 30.0, 20.0),
            ),
            PromptReorderDropTargetVisual(
                target=PromptLineDropTarget(row_index=0, insertion_index=1),
                hit_rect=QRectF(30.0, 0.0, 30.0, 20.0),
            ),
            PromptReorderDropTargetVisual(
                target=PromptLineDropTarget(row_index=0, insertion_index=2),
                hit_rect=QRectF(60.0, 0.0, 30.0, 20.0),
            ),
        ),
    )


def _tracker_input(
    *,
    active_target: PromptReorderDropTarget | None = None,
    drag_rect: QRectF,
    lanes: tuple[PromptReorderRowDropLane | PromptReorderBlankLineDropLane, ...],
) -> PromptReorderDropTargetResolverInput:
    """Return one resolver input without widget-owned state."""

    return PromptReorderDropTargetResolverInput(
        drop_lanes=lanes,
        target_visuals=tuple(
            visual
            for lane in lanes
            if isinstance(lane, PromptReorderRowDropLane)
            for visual in lane.slot_visuals
        ),
        active_target=active_target,
        drag_rect=drag_rect,
        geometry_generation_id=17,
    )


def test_same_target_returns_unchanged_result() -> None:
    """Resolving the active slot should report the cheap unchanged target path."""

    tracker = PromptReorderDropTargetTracker()
    row_lane = _row_lane()
    active_target = PromptLineDropTarget(row_index=0, insertion_index=1)

    result = tracker.resolve(
        _tracker_input(
            active_target=active_target,
            drag_rect=QRectF(35.0, 4.0, 4.0, 4.0),
            lanes=(row_lane,),
        )
    )

    assert result.target == active_target
    assert not result.changed
    assert result.fast_path_reason == "unchanged_target"
    assert result.geometry_generation_id == 17


def test_row_slot_target_change_is_reported() -> None:
    """Resolving a different row slot should return the new line target."""

    tracker = PromptReorderDropTargetTracker()
    row_lane = _row_lane()

    result = tracker.resolve(
        _tracker_input(
            active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
            drag_rect=QRectF(70.0, 4.0, 4.0, 4.0),
            lanes=(row_lane,),
        )
    )

    assert result.target == PromptLineDropTarget(row_index=0, insertion_index=2)
    assert result.changed
    assert result.fast_path_reason == "target_changed"


def test_blank_line_lane_target_change_is_reported() -> None:
    """Blank-line lanes should resolve from vertical lane intent alone."""

    tracker = PromptReorderDropTargetTracker()
    blank_target = PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=1)
    blank_lane = PromptReorderBlankLineDropLane(
        target=blank_target,
        hit_rect=QRectF(0.0, 24.0, 90.0, 20.0),
    )

    result = tracker.resolve(
        _tracker_input(
            active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
            drag_rect=QRectF(20.0, 30.0, 4.0, 4.0),
            lanes=(_row_lane(), blank_lane),
        )
    )

    assert result.target == blank_target
    assert result.changed
    assert result.fast_path_reason == "target_changed"


def test_no_lane_result_is_explicit() -> None:
    """Missing lane geometry should return an explicit no-lane result."""

    tracker = PromptReorderDropTargetTracker()

    result = tracker.resolve(
        _tracker_input(
            active_target=None,
            drag_rect=QRectF(20.0, 30.0, 4.0, 4.0),
            lanes=(),
        )
    )

    assert result.target is None
    assert result.no_lane
    assert not result.changed
    assert result.fast_path_reason == "no_lanes"


def test_active_target_retained_for_overlapping_slots_and_lanes() -> None:
    """Overlapping candidates should keep the active target when it is valid."""

    tracker = PromptReorderDropTargetTracker()
    active_target = PromptLineDropTarget(row_index=1, insertion_index=0)
    first_lane = PromptReorderRowDropLane(
        row_index=0,
        visual_row_index=0,
        hit_rect=QRectF(0.0, 0.0, 90.0, 20.0),
        slot_visuals=(
            PromptReorderDropTargetVisual(
                target=PromptLineDropTarget(row_index=0, insertion_index=0),
                hit_rect=QRectF(0.0, 0.0, 60.0, 20.0),
            ),
        ),
    )
    active_lane = PromptReorderRowDropLane(
        row_index=1,
        visual_row_index=1,
        hit_rect=QRectF(0.0, 0.0, 90.0, 20.0),
        slot_visuals=(
            PromptReorderDropTargetVisual(
                target=active_target,
                hit_rect=QRectF(0.0, 0.0, 60.0, 20.0),
            ),
            PromptReorderDropTargetVisual(
                target=PromptLineDropTarget(row_index=1, insertion_index=1),
                hit_rect=QRectF(0.0, 0.0, 60.0, 20.0),
            ),
        ),
    )

    result = tracker.resolve(
        _tracker_input(
            active_target=active_target,
            drag_rect=QRectF(10.0, 4.0, 4.0, 4.0),
            lanes=(first_lane, active_lane),
        )
    )

    assert result.target == active_target
    assert not result.changed
    assert result.fast_path_reason == "unchanged_target"


def test_nearest_slot_tie_prefers_active_target() -> None:
    """Nearest-slot ties should keep the active line target."""

    tracker = PromptReorderDropTargetTracker()
    row_lane = _row_lane()
    active_target = PromptLineDropTarget(row_index=0, insertion_index=1)

    result = tracker.row_slot_target_for_drag_rect(
        row_lane,
        QRectF(25.0, 24.0, 10.0, 10.0),
        active_target=active_target,
    )

    assert result == active_target


def test_point_rect_and_axis_distance_helpers_match_drag_policy() -> None:
    """Point-sized compatibility helpers should remain deterministic."""

    tracker = PromptReorderDropTargetTracker()
    point = QPointF(36.0, 8.0)
    drag_rect = point_drop_rect(point)

    assert drag_rect.size().width() == 1.0
    assert tracker.drop_target_at_position(
        point,
        drop_lanes=(_row_lane(),),
        active_target=None,
        geometry_generation_id=19,
    ) == PromptLineDropTarget(row_index=0, insertion_index=1)
    assert axis_distance(axis_value=3.0, start=5.0, end=10.0) == 2.0
    assert axis_distance(axis_value=7.0, start=5.0, end=10.0) == 0.0
    assert axis_distance(axis_value=13.0, start=5.0, end=10.0) == 3.0


def test_placement_snapshot_resolution_uses_prepared_geometry_first() -> None:
    """Placement geometry should win before lane fallback when it is available."""

    tracker = PromptReorderDropTargetTracker()
    placement_target = PromptLineDropTarget(row_index=2, insertion_index=3)
    placement = PromptReorderPlacementGeometry(
        placement_id=reorder_placement_id_for_target(
            placement_target,
            visual_line_index=0,
            ordinal=0,
        ),
        target=placement_target,
        hit_rect=QRectF(100.0, 100.0, 20.0, 20.0),
        insertion_anchor_rect=rect_from_centerline(x=110.0, y=110.0, height=20.0),
        visual_line_rect=QRectF(100.0, 100.0, 80.0, 20.0),
        expected_landing_rect=None,
        source_before=None,
        source_after=None,
    )

    result = tracker.resolve(
        PromptReorderDropTargetResolverInput(
            drop_lanes=(_row_lane(),),
            target_visuals=(),
            active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
            drag_rect=QRectF(108.0, 108.0, 4.0, 4.0),
            geometry_generation_id=23,
            placement_snapshot=PromptReorderPlacementSnapshot(
                placements=(placement,),
                visual_line_count=1,
                layout_width=200.0,
                content_height=120.0,
            ),
            active_placement=None,
        )
    )

    assert result.target == placement_target
    assert result.active_placement == placement
    assert result.changed
    assert result.fast_path_reason == "target_changed"
