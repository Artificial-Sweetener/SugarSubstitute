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

"""Verify prompt reorder target resolution navigation."""

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
    _ExplodingLayoutPolicy,
    _row_lane,
    _blank_lane,
    _navigator_input,
)


def test_horizontal_move_noops_at_boundary() -> None:
    """Horizontal movement should report a boundary no-op at row edges."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())

    result = navigator.move_horizontally(
        _navigator_input(
            active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
            lanes=(_row_lane(),),
        ),
        step=-1,
    )

    assert not result.moved
    assert result.no_op_reason == "boundary"
    assert result.destination_target is None
    assert result.proposed_state is None


def test_current_target_can_resolve_from_current_layout() -> None:
    """Navigator should recover the current target when no active target is stored."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_FakeLayoutPolicy())
    current_layout = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0, 2)),),
        gaps=(),
    )

    target = navigator.current_effective_drop_target(
        _navigator_input(
            layout_view=current_layout,
            active_target=None,
            lanes=(_row_lane(),),
        )
    )

    assert target == PromptLineDropTarget(row_index=0, insertion_index=0)


def test_current_target_prefers_active_row_position_without_layout_probe() -> None:
    """Initial keyboard movement should derive its target from the active chip row."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_ExplodingLayoutPolicy())
    current_layout = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0, 1)),
            PromptReorderRowView(row_index=3, chip_indices=(4, 2, 5)),
        ),
        gaps=(),
    )

    target = navigator.current_effective_drop_target(
        _navigator_input(
            layout_view=current_layout,
            active_segment_index=2,
            active_target=None,
            lanes=(
                _row_lane(row_index=0, insertion_indices=(0, 1, 2)),
                _row_lane(row_index=3, insertion_indices=(0, 1, 2, 3)),
            ),
        )
    )

    assert target == PromptLineDropTarget(row_index=3, insertion_index=1)


def test_hidden_final_row_resolves_to_trailing_blank_line_origin() -> None:
    """Initial keyboard movement should recover an active final row hidden by base drag."""

    navigator = PromptReorderKeyboardNavigator(layout_policy=_ExplodingLayoutPolicy())
    current_layout = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(1,)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
            ),
        ),
    )

    target = navigator.current_effective_drop_target(
        _navigator_input(
            layout_view=current_layout,
            active_segment_index=1,
            active_target=None,
            active_segment_center=(20.0, 45.0),
            lanes=(
                _row_lane(row_index=0, insertion_indices=(0, 1)),
                _blank_lane(gap_index=0, blank_line_index=0, top=30.0),
                _blank_lane(gap_index=0, blank_line_index=1, top=60.0),
            ),
        )
    )

    assert target == PromptGapBlankLineDropTarget(
        gap_index=0,
        blank_line_index=1,
    )
