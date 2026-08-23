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

"""Verify settled reorder geometry becomes animation targets."""

from __future__ import annotations


from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationPlanner,
    PromptReorderAnimationTarget,
)
from tests.presentation.editor.prompt_editor.reorder.animation.planner_support import (
    _layout,
)


def test_same_line_move_produces_settled_target_rect_shift() -> None:
    """Planner should emit same-line displacement from supplied settled rects."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=1,
        current_visuals={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 20.0, 10.0),
        },
        proposed_layout_view=_layout((1, 0, 2)),
        proposed_chip_geometry={
            0: QRectF(24.0, 0.0, 20.0, 10.0),
            1: QRectF(0.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 20.0, 10.0),
        },
        ordered_segment_indices=(1, 0, 2),
        dragged_segment_index=1,
        reason="pointer_target_changed",
    )

    assert plan.changed_targets == (
        PromptReorderAnimationTarget(
            segment_index=0,
            start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
            target_rect=QRectF(24.0, 0.0, 20.0, 10.0),
            target_visible=True,
        ),
    )
    assert plan.immediate_segment_indices == frozenset()
    assert plan.skipped_segment_indices == frozenset()
    assert plan.animated_segment_indices == frozenset({0, 1})


def test_wrapped_move_uses_next_line_settled_target_rect() -> None:
    """Planner should preserve wrapped-line y positions from settled geometry."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=1,
        current_visuals={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 26.0, 10.0),
            3: QRectF(78.0, 0.0, 26.0, 10.0),
        },
        proposed_layout_view=_layout((0, 1), (2, 3)),
        proposed_chip_geometry={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
            2: QRectF(0.0, 18.0, 26.0, 10.0),
            3: QRectF(30.0, 18.0, 26.0, 10.0),
        },
        ordered_segment_indices=(0, 1, 2, 3),
        dragged_segment_index=1,
        reason="pointer_target_changed_wrap",
    )

    target_by_segment = {
        target.segment_index: target.target_rect for target in plan.changed_targets
    }

    assert target_by_segment[2] == QRectF(0.0, 18.0, 26.0, 10.0)
    assert target_by_segment[3] == QRectF(30.0, 18.0, 26.0, 10.0)


def test_multiline_gap_move_uses_settled_gap_target_rect() -> None:
    """Planner should preserve gap-spanning target rects from settled geometry."""

    planner = PromptReorderAnimationPlanner()
    layout = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(1, 2)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text="\n\n",
                blank_line_count=2,
                placement=PromptReorderGapPlacement.BETWEEN_ROWS,
            ),
        ),
    )
    plan = planner.build_plan(
        generation=1,
        current_visuals={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 26.0, 10.0),
        },
        proposed_layout_view=layout,
        proposed_chip_geometry={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(0.0, 46.0, 20.0, 10.0),
            2: QRectF(24.0, 46.0, 26.0, 10.0),
        },
        ordered_segment_indices=(0, 1, 2),
        dragged_segment_index=None,
        reason="pointer_target_changed_multiline_gap",
    )

    target_by_segment = {
        target.segment_index: target.target_rect for target in plan.changed_targets
    }

    assert plan.layout_view.gaps == layout.gaps
    assert target_by_segment[1] == QRectF(0.0, 46.0, 20.0, 10.0)
    assert target_by_segment[2] == QRectF(24.0, 46.0, 26.0, 10.0)
