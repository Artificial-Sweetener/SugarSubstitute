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

"""Cover projection-owned prompt reorder keyboard navigation."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_targets import (
    PromptReorderBlankLineDropLane,
    PromptReorderDropTargetVisual,
    PromptReorderRowDropLane,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigationInput,
    PromptReorderKeyboardNavigator,
)


class _FakeLayoutPolicy:
    """Build deterministic reorder layouts from typed keyboard targets."""

    def build_base_drag_reorder_state_from_state(
        self,
        state_view: PromptReorderStateView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderStateView:
        """Return the state with the dragged segment removed from its order."""

        ordered_indices = tuple(
            index
            for index in state_view.ordered_chip_indices
            if index != dragged_segment_index
        )
        return PromptReorderStateView(
            ordered_chip_indices=ordered_indices,
            separator_slots=state_view.separator_slots[
                : max(0, len(ordered_indices) - 1)
            ],
            has_trailing_comma=state_view.has_trailing_comma,
        )

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
        """Return source state matching the deterministic preview layout."""

        _ = (state_view, current_layout_view, base_drag_layout_view)
        layout_view = self.build_preview_drop_layout_view_from_layout(
            document_view,
            PromptReorderLayoutView(
                rows=(
                    PromptReorderRowView(
                        row_index=0,
                        chip_indices=state_view.ordered_chip_indices,
                    ),
                ),
                gaps=(),
            ),
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
        )
        ordered_indices = self.reorder_layout_chip_indices(layout_view)
        return PromptReorderStateView(
            ordered_chip_indices=ordered_indices,
            separator_slots=tuple(", " for _ in ordered_indices[:-1]),
            has_trailing_comma=state_view.has_trailing_comma,
        )

    def build_base_drag_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Return the layout with the dragged segment removed from its rows."""

        _ = document_view
        rows: list[PromptReorderRowView] = []
        for row in layout_view.rows:
            chip_indices = tuple(
                index for index in row.chip_indices if index != dragged_segment_index
            )
            if chip_indices:
                rows.append(
                    PromptReorderRowView(
                        row_index=row.row_index,
                        chip_indices=chip_indices,
                    )
                )
        return PromptReorderLayoutView(rows=tuple(rows), gaps=layout_view.gaps)

    def build_preview_drop_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Return a simple layout that reflects the supplied target."""

        base_layout = self.build_base_drag_layout_view_from_layout(
            document_view,
            layout_view,
            dragged_segment_index=dragged_segment_index,
        )
        if isinstance(drop_target, PromptLineDropTarget):
            rows = list(base_layout.rows)
            row = rows[drop_target.row_index]
            chip_indices = list(row.chip_indices)
            chip_indices.insert(drop_target.insertion_index, dragged_segment_index)
            rows[drop_target.row_index] = PromptReorderRowView(
                row_index=row.row_index,
                chip_indices=tuple(chip_indices),
            )
            return PromptReorderLayoutView(rows=tuple(rows), gaps=layout_view.gaps)

        rows = list(base_layout.rows)
        rows.insert(
            drop_target.gap_index + 1,
            PromptReorderRowView(
                row_index=drop_target.gap_index + 1,
                chip_indices=(dragged_segment_index,),
            ),
        )
        return PromptReorderLayoutView(rows=tuple(rows), gaps=layout_view.gaps)

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return the flattened layout order."""

        return tuple(index for row in layout_view.rows for index in row.chip_indices)


class _ExplodingLayoutPolicy:
    """Fail if target resolution reaches preview-layout probing."""

    def build_base_drag_reorder_state_from_state(
        self,
        state_view: PromptReorderStateView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderStateView:
        """Raise because this policy should not be used by row-position recovery."""

        _ = (state_view, dragged_segment_index)
        raise AssertionError("row-position target recovery should not build state")

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
        """Raise because this policy should not be used by row-position recovery."""

        _ = (
            document_view,
            state_view,
            current_layout_view,
            base_drag_layout_view,
            dragged_segment_index,
            drop_target,
        )
        raise AssertionError("row-position target recovery should not build state")

    def build_base_drag_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Raise because this policy should not be used by row-position recovery."""

        _ = (document_view, layout_view, dragged_segment_index)
        raise AssertionError("row-position target recovery should not build layouts")

    def build_preview_drop_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Raise because this policy should not be used by row-position recovery."""

        _ = (document_view, layout_view, dragged_segment_index, drop_target)
        raise AssertionError("row-position target recovery should not build layouts")

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Raise because this policy should not be used by row-position recovery."""

        _ = layout_view
        raise AssertionError("row-position target recovery should not build layouts")


def _document_view() -> PromptDocumentView:
    """Return a minimal document view for keyboard navigation tests."""

    return PromptDocumentView(
        source_text="alpha, beta, gamma",
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        has_trailing_comma=False,
    )


def _one_row_layout() -> PromptReorderLayoutView:
    """Return a single-row reorder layout."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1, 2)),),
        gaps=(),
    )


def _wrapped_row_layout() -> PromptReorderLayoutView:
    """Return a single logical row that can span multiple visual lanes."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1, 2, 3)),),
        gaps=(),
    )


def _multi_lane_layout() -> PromptReorderLayoutView:
    """Return a layout with a blank-line gap between two populated rows."""

    return PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(2, 1)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n\n",
                blank_line_count=2,
            ),
        ),
    )


def _row_lane(
    *,
    row_index: int = 0,
    visual_row_index: int = 0,
    top: float = 0.0,
    insertion_indices: tuple[int, ...] = (0, 1, 2),
) -> PromptReorderRowDropLane:
    """Return a deterministic row lane with configured insertion slots."""

    slot_width = 30.0

    return PromptReorderRowDropLane(
        row_index=row_index,
        visual_row_index=visual_row_index,
        hit_rect=QRectF(0.0, top, slot_width * len(insertion_indices), 20.0),
        slot_visuals=(
            *(
                PromptReorderDropTargetVisual(
                    target=PromptLineDropTarget(
                        row_index=row_index,
                        insertion_index=insertion_index,
                    ),
                    hit_rect=QRectF(
                        slot_width * slot_index,
                        top,
                        slot_width,
                        20.0,
                    ),
                )
                for slot_index, insertion_index in enumerate(insertion_indices)
            ),
        ),
    )


def _blank_lane(
    *,
    gap_index: int = 0,
    blank_line_index: int = 1,
    top: float = 30.0,
) -> PromptReorderBlankLineDropLane:
    """Return a deterministic blank-line lane between populated rows."""

    return PromptReorderBlankLineDropLane(
        target=PromptGapBlankLineDropTarget(
            gap_index=gap_index,
            blank_line_index=blank_line_index,
        ),
        hit_rect=QRectF(0.0, top, 90.0, 20.0),
    )


def _navigator_input(
    *,
    layout_view: PromptReorderLayoutView | None = None,
    active_segment_index: int | None = 1,
    active_target: PromptReorderDropTarget | None,
    preferred_x: float | None = None,
    active_segment_center: tuple[float, float] | None = None,
    lanes: tuple[PromptReorderRowDropLane | PromptReorderBlankLineDropLane, ...],
) -> PromptReorderKeyboardNavigationInput:
    """Return one navigation request over prepared lanes."""

    return PromptReorderKeyboardNavigationInput(
        document_view=_document_view(),
        current_layout_view=layout_view or _one_row_layout(),
        active_segment_index=active_segment_index,
        active_target=active_target,
        preferred_x=preferred_x,
        drop_target_lanes=lanes,
        active_segment_center=active_segment_center,
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
            layout_view=left.proposed_layout_view,
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
            layout_view=first_wrap_edge.proposed_layout_view,
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
            layout_view=before_wrap_edge.proposed_layout_view,
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
            layout_view=up.proposed_layout_view,
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
            layout_view=down.proposed_layout_view,
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
    assert result.proposed_layout_view is None


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
