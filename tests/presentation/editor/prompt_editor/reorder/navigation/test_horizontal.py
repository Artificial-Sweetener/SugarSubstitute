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

"""Verify prompt reorder horizontal navigation."""

from __future__ import annotations


from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigator,
)

from .support import (
    _FakeLayoutPolicy,
    _wrapped_row_layout,
    _row_lane,
    _blank_lane,
    _navigator_input,
    _proposed_layout,
)


def test_left_and_right_moves_follow_populated_row_reading_order() -> None:
    """Horizontal keyboard movement should step across row slots in order."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    row_lane = _row_lane()

    left = navigator.move_horizontally(
        _navigator_input(
            active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
            lanes=(row_lane,),
        ),
        step=-1,
    )

    assert left.moved
    assert left.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=0,
    )
    assert left.preferred_x == 15.0
    assert left.ordered_segment_indices == (1, 0, 2)

    right = navigator.move_horizontally(
        _navigator_input(
            layout_view=_proposed_layout(left),
            active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
            lanes=(row_lane,),
        ),
        step=1,
    )

    assert right.moved
    assert right.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=1,
    )
    assert right.ordered_segment_indices == (0, 1, 2)


def test_horizontal_moves_skip_duplicate_visual_wrap_slots() -> None:
    """Horizontal movement should collapse duplicate logical targets at wrap boundaries."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    lanes = (
        _row_lane(visual_row_index=0, top=0.0, insertion_indices=(0, 1, 2)),
        _row_lane(visual_row_index=1, top=30.0, insertion_indices=(2, 3, 4)),
    )

    first_wrap_edge = navigator.move_horizontally(
        _navigator_input(
            layout_view=_wrapped_row_layout(),
            active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
            lanes=lanes,
        ),
        step=1,
    )
    after_wrap_edge = navigator.move_horizontally(
        _navigator_input(
            layout_view=_proposed_layout(first_wrap_edge),
            active_target=first_wrap_edge.destination_target,
            preferred_x=first_wrap_edge.preferred_x,
            lanes=lanes,
        ),
        step=1,
    )

    assert first_wrap_edge.moved
    assert first_wrap_edge.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=2,
    )
    assert first_wrap_edge.preferred_x == 75.0
    assert first_wrap_edge.ordered_segment_indices == (0, 2, 1, 3)
    assert after_wrap_edge.moved
    assert after_wrap_edge.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=3,
    )
    assert after_wrap_edge.preferred_x == 45.0
    assert after_wrap_edge.ordered_segment_indices == (0, 2, 3, 1)


def test_horizontal_moves_left_skip_duplicate_visual_wrap_slots() -> None:
    """Left movement should also skip repeated wrap-seam occurrences."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    lanes = (
        _row_lane(visual_row_index=0, top=0.0, insertion_indices=(0, 1, 2)),
        _row_lane(visual_row_index=1, top=30.0, insertion_indices=(2, 3, 4)),
    )

    before_wrap_edge = navigator.move_horizontally(
        _navigator_input(
            layout_view=PromptReorderLayoutView(
                rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 2, 3, 1)),),
                gaps=(),
            ),
            active_target=PromptLineDropTarget(row_index=0, insertion_index=3),
            preferred_x=45.0,
            lanes=lanes,
        ),
        step=-1,
    )
    before_previous_chip = navigator.move_horizontally(
        _navigator_input(
            layout_view=_proposed_layout(before_wrap_edge),
            active_target=before_wrap_edge.destination_target,
            preferred_x=before_wrap_edge.preferred_x,
            lanes=lanes,
        ),
        step=-1,
    )

    assert before_wrap_edge.moved
    assert before_wrap_edge.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=2,
    )
    assert before_wrap_edge.preferred_x == 15.0
    assert before_wrap_edge.ordered_segment_indices == (0, 2, 1, 3)
    assert before_previous_chip.moved
    assert before_previous_chip.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=1,
    )
    assert before_previous_chip.preferred_x == 45.0
    assert before_previous_chip.ordered_segment_indices == (0, 1, 2, 3)


def test_horizontal_moves_include_blank_line_lanes() -> None:
    """Horizontal keyboard movement should use the same blank targets as drag."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    lanes = (
        _row_lane(row_index=0, visual_row_index=0, top=0.0, insertion_indices=(0, 1)),
        _blank_lane(),
        _row_lane(row_index=1, visual_row_index=1, top=60.0, insertion_indices=(0, 1)),
    )
    layout_view = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0, 1)),
            PromptReorderRowView(row_index=1, chip_indices=(2,)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
            ),
        ),
    )

    right = navigator.move_horizontally(
        _navigator_input(
            layout_view=layout_view,
            active_segment_index=1,
            active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
            lanes=lanes,
        ),
        step=1,
    )

    assert right.moved
    assert right.destination_target == PromptGapBlankLineDropTarget(
        gap_index=0,
        blank_line_index=1,
    )
    assert right.ordered_segment_indices == (0, 1, 2)
