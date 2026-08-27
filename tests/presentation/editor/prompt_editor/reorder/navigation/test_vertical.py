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

"""Verify prompt reorder vertical navigation."""

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
    _multi_lane_layout,
    _row_lane,
    _blank_lane,
    _navigator_input,
    _proposed_layout,
)


def test_up_and_down_moves_use_prepared_blank_and_row_lanes() -> None:
    """Vertical movement should use lane order and preserve preferred x."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    lanes = (
        _row_lane(row_index=0, visual_row_index=0, top=0.0),
        _blank_lane(),
        _row_lane(row_index=1, visual_row_index=1, top=60.0),
    )

    up = navigator.move_vertically(
        _navigator_input(
            layout_view=_multi_lane_layout(),
            active_target=PromptLineDropTarget(row_index=1, insertion_index=1),
            preferred_x=75.0,
            lanes=lanes,
        ),
        direction=-1,
    )

    assert up.moved
    assert up.destination_target == PromptGapBlankLineDropTarget(
        gap_index=0,
        blank_line_index=1,
    )
    assert up.ordered_segment_indices == (0, 1, 2)

    down = navigator.move_vertically(
        _navigator_input(
            layout_view=_proposed_layout(up),
            active_target=up.destination_target,
            preferred_x=75.0,
            lanes=lanes,
        ),
        direction=1,
    )

    assert down.moved
    assert down.destination_target == PromptLineDropTarget(
        row_index=1,
        insertion_index=2,
    )
    assert down.preferred_x == 75.0
    assert down.ordered_segment_indices == (0, 2, 1)


def test_vertical_moves_use_preferred_x_to_select_duplicate_wrap_lane() -> None:
    """Vertical movement should not collapse duplicate targets to the first lane."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    lanes = (
        _row_lane(visual_row_index=0, top=0.0, insertion_indices=(0, 1, 2)),
        _row_lane(visual_row_index=1, top=30.0, insertion_indices=(2, 3, 4)),
    )

    down = navigator.move_vertically(
        _navigator_input(
            layout_view=PromptReorderLayoutView(
                rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 2, 1, 3)),),
                gaps=(),
            ),
            active_target=PromptLineDropTarget(row_index=0, insertion_index=2),
            preferred_x=15.0,
            lanes=lanes,
        ),
        direction=1,
    )
    bottom_noop = navigator.move_vertically(
        _navigator_input(
            layout_view=_proposed_layout(down),
            active_target=down.destination_target,
            preferred_x=down.preferred_x,
            lanes=lanes,
        ),
        direction=1,
    )

    assert down.moved
    assert down.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=4,
    )
    assert down.ordered_segment_indices == (0, 2, 3, 1)
    assert not bottom_noop.moved
    assert bottom_noop.no_op_reason == "unchanged_target"


def test_vertical_initial_resolution_uses_active_visual_occurrence() -> None:
    """Initial vertical movement should start from the chip's concrete visual lane."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    lanes = (
        _row_lane(visual_row_index=0, top=0.0, insertion_indices=(0, 1, 2)),
        _row_lane(visual_row_index=1, top=30.0, insertion_indices=(2, 3, 4)),
        _blank_lane(),
        _row_lane(row_index=1, visual_row_index=2, top=60.0, insertion_indices=(0, 1)),
    )

    down = navigator.move_vertically(
        _navigator_input(
            layout_view=PromptReorderLayoutView(
                rows=(
                    PromptReorderRowView(row_index=0, chip_indices=(0, 2, 1, 3)),
                    PromptReorderRowView(row_index=1, chip_indices=(4,)),
                ),
                gaps=(
                    PromptReorderGapView(
                        gap_index=0,
                        separator_text=",\n\n",
                        blank_line_count=1,
                    ),
                ),
            ),
            active_segment_index=1,
            active_target=None,
            active_segment_center=(15.0, 40.0),
            lanes=lanes,
        ),
        direction=1,
    )

    assert down.moved
    assert down.destination_target == PromptGapBlankLineDropTarget(
        gap_index=0,
        blank_line_index=1,
    )


def test_vertical_moves_clamp_to_edge_slots_at_boundaries() -> None:
    """Moving beyond top or bottom lanes should clamp to the lane edge slot."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    row_lane = _row_lane()

    up = navigator.move_vertically(
        _navigator_input(
            active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
            lanes=(row_lane,),
        ),
        direction=-1,
    )
    down = navigator.move_vertically(
        _navigator_input(
            active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
            lanes=(row_lane,),
        ),
        direction=1,
    )

    assert up.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=0,
    )
    assert up.ordered_segment_indices == (1, 0, 2)
    assert down.destination_target == PromptLineDropTarget(
        row_index=0,
        insertion_index=2,
    )
    assert down.ordered_segment_indices == (0, 2, 1)
