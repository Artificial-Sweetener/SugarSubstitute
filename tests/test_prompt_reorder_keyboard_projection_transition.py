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

"""Verify keyboard navigation projects and adopts one immutable state generation."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPainterPath

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreparedStateView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigationResult,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_keyboard_projection_transition import (
    PromptReorderKeyboardProjectionTransitionOwner,
)


class _LayoutPolicy:
    """Build deterministic layouts and state for keyboard-transition tests."""

    def build_base_drag_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        dragged_segment_index: int,
    ) -> PromptReorderPreparedStateView:
        """Return matching state and layout with the held segment removed."""

        _ = document_view
        remaining = tuple(
            index
            for index in state_view.ordered_chip_indices
            if index != dragged_segment_index
        )
        return PromptReorderPreparedStateView(
            reorder_state=_state(*remaining),
            layout_view=_layout(*remaining),
        )

    def build_preview_drop_state(
        self,
        document_view: PromptDocumentView,
        base_drag_state_view: PromptReorderPreparedStateView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderPreparedStateView:
        """Insert the held segment and return matching state and layout."""

        _ = document_view
        assert isinstance(drop_target, PromptLineDropTarget)
        indices = list(base_drag_state_view.reorder_state.ordered_chip_indices)
        indices.insert(drop_target.insertion_index, dragged_segment_index)
        return PromptReorderPreparedStateView(
            reorder_state=_state(*indices),
            layout_view=_layout(*indices),
        )

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Flatten the one-row test layout."""

        return tuple(index for row in layout_view.rows for index in row.chip_indices)


def _document() -> PromptDocumentView:
    """Return a minimal immutable document view."""

    return PromptDocumentView(
        source_text="alpha, beta, gamma",
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(18),
        has_trailing_comma=False,
    )


def _layout(*indices: int) -> PromptReorderLayoutView:
    """Return one row containing the supplied chip order."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=indices),),
        gaps=(),
    )


def _state(*indices: int) -> PromptReorderStateView:
    """Return reorder state containing the supplied chip order."""

    return PromptReorderStateView(
        ordered_chip_indices=indices,
        separator_slots=tuple(", " for _ in indices[:-1]),
        has_trailing_comma=False,
    )


def _chip_snapshot() -> PromptReorderChipGeometrySnapshot:
    """Return one live chip whose hotspot exposes an exact center."""

    geometry = PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(chip_index=0, visual_revision=4),
        chip_index=0,
        source_start=0,
        source_end=5,
        rendered_start=0,
        rendered_end=5,
        visual_lines=(),
        hotspot_rect=QRect(10, 20, 20, 10),
        chrome_path=QPainterPath(),
        outline_bounds=QRectF(10.0, 20.0, 20.0, 10.0),
        slot_before=QPointF(10.0, 25.0),
        slot_after=QPointF(30.0, 25.0),
        marker_height=10.0,
    )
    return PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={0: geometry},
        ordered_chip_indices=(0,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=40.0,
        scroll_offset=0.0,
    )


def _ready_state() -> PromptReorderInteractionGeometryState:
    """Return one coherent state ready to adopt keyboard navigation."""

    original_layout = _layout(0, 1, 2)
    original_state = _state(0, 1, 2)
    return PromptReorderInteractionGeometryState(
        document_view=_document(),
        original_layout_view=original_layout,
        current_layout_view=original_layout,
        base_drag_layout_view=_layout(1, 2),
        original_reorder_state=original_state,
        current_reorder_state=original_state,
        base_drag_reorder_state=_state(1, 2),
        live_chip_geometry_snapshot=_chip_snapshot(),
        initial_ordered_indices=(0, 1, 2),
        ordered_segment_indices=(0, 1, 2),
    )


def test_keyboard_projection_input_captures_live_center_without_state_work() -> None:
    """Input projection should read one indexed chip and leave state untouched."""

    owner = PromptReorderKeyboardProjectionTransitionOwner(
        layout_policy=_LayoutPolicy()
    )
    state = _ready_state()
    target = PromptLineDropTarget(row_index=0, insertion_index=0)

    navigation_input = owner.navigation_input(
        state,
        active_segment_index=0,
        active_target=target,
        preferred_x=37.0,
    )

    assert navigation_input.document_view is state.document_view
    assert navigation_input.current_layout_view is state.current_layout_view
    assert navigation_input.active_target is target
    assert navigation_input.active_segment_center == (19.0, 24.0)


def test_keyboard_projection_rejects_incomplete_result_by_identity() -> None:
    """Invalid navigation must return the existing state without allocation."""

    owner = PromptReorderKeyboardProjectionTransitionOwner(
        layout_policy=_LayoutPolicy()
    )
    state = _ready_state()

    next_state = owner.apply(
        state,
        PromptReorderKeyboardNavigationResult(
            moved=False,
            destination_target=None,
            preferred_x=None,
            proposed_state=None,
            proposed_base_drag_state=None,
            ordered_segment_indices=(),
            no_op_reason="boundary",
        ),
        active_segment_index=0,
        gesture_id=None,
        event_id=None,
    )

    assert next_state is state


def test_keyboard_projection_adopts_complete_move_and_retires_preview_identity() -> (
    None
):
    """Successful navigation should publish one coherent layout/state generation."""

    owner = PromptReorderKeyboardProjectionTransitionOwner(
        layout_policy=_LayoutPolicy()
    )
    state = _ready_state()
    proposed_layout = _layout(1, 0, 2)

    next_state = owner.apply(
        state,
        PromptReorderKeyboardNavigationResult(
            moved=True,
            destination_target=PromptLineDropTarget(
                row_index=0,
                insertion_index=1,
            ),
            preferred_x=45.0,
            proposed_state=PromptReorderPreparedStateView(
                reorder_state=_state(1, 0, 2),
                layout_view=proposed_layout,
            ),
            proposed_base_drag_state=PromptReorderPreparedStateView(
                reorder_state=_state(1, 2),
                layout_view=_layout(1, 2),
            ),
            ordered_segment_indices=(1, 0, 2),
        ),
        active_segment_index=0,
        gesture_id=8,
        event_id=13,
    )

    assert next_state is not state
    assert next_state.current_layout_view is proposed_layout
    assert next_state.current_reorder_state == _state(1, 0, 2)
    assert next_state.base_drag_layout_view == _layout(1, 2)
    assert next_state.base_drag_reorder_state == _state(1, 2)
    assert next_state.ordered_segment_indices == (1, 0, 2)
    assert next_state.preview_layout_view is None
    assert next_state.preview_reorder_state is None


def test_keyboard_projection_restores_original_objects_for_original_order() -> None:
    """Returning to the initial order should reuse original layout/state identity."""

    owner = PromptReorderKeyboardProjectionTransitionOwner(
        layout_policy=_LayoutPolicy()
    )
    original = _ready_state()
    moved_state = replace(
        original,
        current_layout_view=_layout(1, 0, 2),
        current_reorder_state=_state(1, 0, 2),
    )

    restored = owner.apply(
        moved_state,
        PromptReorderKeyboardNavigationResult(
            moved=True,
            destination_target=PromptLineDropTarget(
                row_index=0,
                insertion_index=0,
            ),
            preferred_x=20.0,
            proposed_state=PromptReorderPreparedStateView(
                reorder_state=_state(0, 1, 2),
                layout_view=_layout(0, 1, 2),
            ),
            proposed_base_drag_state=PromptReorderPreparedStateView(
                reorder_state=_state(1, 2),
                layout_view=_layout(1, 2),
            ),
            ordered_segment_indices=(0, 1, 2),
        ),
        active_segment_index=0,
        gesture_id=None,
        event_id=None,
    )

    assert restored.current_layout_view is original.original_layout_view
    assert restored.current_reorder_state is original.original_reorder_state
