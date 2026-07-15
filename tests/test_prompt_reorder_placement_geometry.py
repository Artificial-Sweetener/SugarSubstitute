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

"""Contract tests for projection-owned prompt reorder placement geometry."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
    placement_for_drag_rect,
    placement_geometry_context,
    reorder_placement_id_for_target,
)


def test_reorder_placement_id_represents_line_targets_without_prompt_text() -> None:
    """Line placement identity should be stable and safe for logs."""

    target = PromptLineDropTarget(row_index=2, insertion_index=3)
    placement_id = reorder_placement_id_for_target(
        target,
        visual_line_index=4,
        ordinal=5,
    )
    placement = PromptReorderPlacementGeometry(
        placement_id=placement_id,
        target=target,
        hit_rect=QRectF(1.0, 2.0, 30.0, 40.0),
        insertion_anchor_rect=QRectF(3.0, 4.0, 1.0, 40.0),
        visual_line_rect=QRectF(0.0, 2.0, 120.0, 40.0),
        expected_landing_rect=QRectF(8.0, 9.0, 10.0, 11.0),
        source_before=12,
        source_after=18,
    )

    context = placement_geometry_context(placement)

    assert placement_id.row_index == 2
    assert placement_id.insertion_index == 3
    assert context["placement_target_kind"] == "PromptLineDropTarget"
    assert context["placement_row_index"] == 2
    assert context["placement_expected_landing_width"] == "10.00"
    assert all("alpha" not in str(value) for value in context.values())


def test_reorder_placement_id_represents_blank_line_targets() -> None:
    """Blank-line placement identity should include its gap and blank row."""

    target = PromptGapBlankLineDropTarget(gap_index=1, blank_line_index=2)
    placement_id = reorder_placement_id_for_target(
        target,
        visual_line_index=3,
        ordinal=4,
    )

    assert placement_id.target_kind == "PromptGapBlankLineDropTarget"
    assert placement_id.gap_index == 1
    assert placement_id.blank_line_index == 2
    assert placement_id.row_index is None
    assert placement_id.insertion_index is None


def test_reorder_placement_hit_testing_prefers_active_overlap() -> None:
    """Overlapping placement hit tests should keep the active placement stable."""

    first_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    second_target = PromptLineDropTarget(row_index=0, insertion_index=1)
    first = PromptReorderPlacementGeometry(
        placement_id=reorder_placement_id_for_target(
            first_target,
            visual_line_index=0,
            ordinal=0,
        ),
        target=first_target,
        hit_rect=QRectF(0.0, 0.0, 60.0, 30.0),
        insertion_anchor_rect=QRectF(0.0, 0.0, 1.0, 30.0),
        visual_line_rect=QRectF(0.0, 0.0, 120.0, 30.0),
        expected_landing_rect=None,
        source_before=None,
        source_after=0,
    )
    second = PromptReorderPlacementGeometry(
        placement_id=reorder_placement_id_for_target(
            second_target,
            visual_line_index=0,
            ordinal=1,
        ),
        target=second_target,
        hit_rect=QRectF(30.0, 0.0, 60.0, 30.0),
        insertion_anchor_rect=QRectF(90.0, 0.0, 1.0, 30.0),
        visual_line_rect=QRectF(0.0, 0.0, 120.0, 30.0),
        expected_landing_rect=None,
        source_before=4,
        source_after=8,
    )
    snapshot = PromptReorderPlacementSnapshot(
        placements=(first, second),
        visual_line_count=1,
        layout_width=120.0,
        content_height=30.0,
    )

    selected = placement_for_drag_rect(
        snapshot,
        QRectF(40.0, 5.0, 10.0, 10.0),
        active_placement_id=second.placement_id,
    )

    assert selected == second


def test_reorder_placement_hit_testing_uses_nearest_anchor_on_selected_line() -> None:
    """A drag outside hit rects should resolve by nearest anchor on the nearest line."""

    top_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    bottom_target = PromptLineDropTarget(row_index=1, insertion_index=0)
    top = PromptReorderPlacementGeometry(
        placement_id=reorder_placement_id_for_target(
            top_target,
            visual_line_index=0,
            ordinal=0,
        ),
        target=top_target,
        hit_rect=QRectF(0.0, 0.0, 40.0, 20.0),
        insertion_anchor_rect=QRectF(0.0, 0.0, 1.0, 20.0),
        visual_line_rect=QRectF(0.0, 0.0, 100.0, 20.0),
        expected_landing_rect=None,
        source_before=None,
        source_after=0,
    )
    bottom = PromptReorderPlacementGeometry(
        placement_id=reorder_placement_id_for_target(
            bottom_target,
            visual_line_index=1,
            ordinal=1,
        ),
        target=bottom_target,
        hit_rect=QRectF(0.0, 60.0, 40.0, 20.0),
        insertion_anchor_rect=QRectF(80.0, 60.0, 1.0, 20.0),
        visual_line_rect=QRectF(0.0, 60.0, 100.0, 20.0),
        expected_landing_rect=None,
        source_before=10,
        source_after=20,
    )
    snapshot = PromptReorderPlacementSnapshot(
        placements=(top, bottom),
        visual_line_count=2,
        layout_width=100.0,
        content_height=80.0,
    )

    selected = placement_for_drag_rect(
        snapshot,
        QRectF(70.0, 40.0, 10.0, 10.0),
        active_placement_id=None,
    )

    assert selected == bottom
