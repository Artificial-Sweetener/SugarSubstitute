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

"""Provide typed lanes and layouts for reorder navigation proof."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderPreparedStateView,
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
    PromptReorderKeyboardNavigationResult,
)


class _FakeLayoutPolicy:
    """Build deterministic reorder layouts from typed keyboard targets."""

    def build_base_drag_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        dragged_segment_index: int,
    ) -> PromptReorderPreparedStateView:
        """Return matching state and layout with the held chip removed."""

        _ = document_view
        ordered_indices = tuple(
            index
            for index in state_view.ordered_chip_indices
            if index != dragged_segment_index
        )
        reorder_state = PromptReorderStateView(
            ordered_chip_indices=ordered_indices,
            separator_slots=state_view.separator_slots[
                : max(0, len(ordered_indices) - 1)
            ],
            has_trailing_comma=state_view.has_trailing_comma,
        )
        rows: list[PromptReorderRowView] = []
        for row in current_layout_view.rows:
            chip_indices = tuple(
                index for index in row.chip_indices if index != dragged_segment_index
            )
            if chip_indices:
                rows.append(
                    PromptReorderRowView(
                        row_index=len(rows),
                        chip_indices=chip_indices,
                    )
                )
        return PromptReorderPreparedStateView(
            reorder_state=reorder_state,
            layout_view=PromptReorderLayoutView(
                rows=tuple(rows),
                gaps=current_layout_view.gaps,
            ),
        )

    def build_preview_drop_state(
        self,
        document_view: PromptDocumentView,
        base_drag_state_view: PromptReorderPreparedStateView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderPreparedStateView:
        """Return matching state and layout for the deterministic target."""

        _ = document_view
        layout_view = self._preview_layout(
            base_drag_state_view.layout_view,
            dragged_segment_index,
            drop_target,
        )
        ordered_indices = self.reorder_layout_chip_indices(layout_view)
        reorder_state = PromptReorderStateView(
            ordered_chip_indices=ordered_indices,
            separator_slots=tuple(", " for _ in ordered_indices[:-1]),
            has_trailing_comma=(base_drag_state_view.reorder_state.has_trailing_comma),
        )
        return PromptReorderPreparedStateView(
            reorder_state=reorder_state,
            layout_view=layout_view,
        )

    @staticmethod
    def _preview_layout(
        layout_view: PromptReorderLayoutView,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Return a simple layout that reflects the supplied target."""

        if isinstance(drop_target, PromptLineDropTarget):
            rows = list(layout_view.rows)
            row = rows[drop_target.row_index]
            chip_indices = list(row.chip_indices)
            chip_indices.insert(drop_target.insertion_index, dragged_segment_index)
            rows[drop_target.row_index] = PromptReorderRowView(
                row_index=row.row_index,
                chip_indices=tuple(chip_indices),
            )
            return PromptReorderLayoutView(rows=tuple(rows), gaps=layout_view.gaps)

        rows = list(layout_view.rows)
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

    def build_base_drag_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        dragged_segment_index: int,
    ) -> PromptReorderPreparedStateView:
        """Raise because this policy should not be used by row-position recovery."""

        _ = (
            document_view,
            state_view,
            current_layout_view,
            dragged_segment_index,
        )
        raise AssertionError("row-position target recovery should not build state")

    def build_preview_drop_state(
        self,
        document_view: PromptDocumentView,
        base_drag_state_view: PromptReorderPreparedStateView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderPreparedStateView:
        """Raise because this policy should not be used by row-position recovery."""

        _ = (
            document_view,
            base_drag_state_view,
            dragged_segment_index,
            drop_target,
        )
        raise AssertionError("row-position target recovery should not build state")

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
        region_structure=PromptRegionStructureView.empty(len("alpha, beta, gamma")),
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

    current_layout = layout_view or _one_row_layout()
    ordered_indices = tuple(
        index for row in current_layout.rows for index in row.chip_indices
    )
    current_state = PromptReorderStateView(
        ordered_chip_indices=ordered_indices,
        separator_slots=tuple(", " for _ in ordered_indices[:-1]),
        has_trailing_comma=False,
    )
    base_drag_state = (
        None
        if active_segment_index is None
        else _FakeLayoutPolicy().build_base_drag_state(
            _document_view(),
            current_state,
            current_layout_view=current_layout,
            dragged_segment_index=active_segment_index,
        )
    )
    return PromptReorderKeyboardNavigationInput(
        document_view=_document_view(),
        current_layout_view=current_layout,
        base_drag_state=base_drag_state,
        active_segment_index=active_segment_index,
        active_target=active_target,
        preferred_x=preferred_x,
        drop_target_lanes=lanes,
        active_segment_center=active_segment_center,
    )


def _proposed_layout(
    result: PromptReorderKeyboardNavigationResult,
) -> PromptReorderLayoutView:
    """Return the coherent proposed layout required by a successful movement."""

    assert result.proposed_state is not None
    return result.proposed_state.layout_view
