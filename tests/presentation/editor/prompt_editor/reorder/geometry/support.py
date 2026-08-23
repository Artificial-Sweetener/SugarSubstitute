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

"""Provide shared immutable prompt reorder geometry fixtures."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderGapView,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreparedStateView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry_owner import (
    PromptReorderGeometryEnvironment,
    PromptReorderGeometryOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_identity import (
    reorder_preview_target_identity,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_projection_owner import (
    PromptReorderPreviewProjectionOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.applicator import (
    PromptProjectionApplicator,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)


class _FakeLayoutPolicy:
    """Provide deterministic reorder layouts for geometry-owner tests."""

    def build_base_drag_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        dragged_segment_index: int,
    ) -> PromptReorderPreparedStateView:
        """Return matching fake layout and state with the held chip removed."""

        _ = document_view
        remaining = tuple(
            index
            for index in state_view.ordered_chip_indices
            if index != dragged_segment_index
        )
        reorder_state = PromptReorderStateView(
            ordered_chip_indices=remaining,
            separator_slots=state_view.separator_slots[: max(0, len(remaining) - 1)],
            has_trailing_comma=state_view.has_trailing_comma,
        )
        return PromptReorderPreparedStateView(
            reorder_state=reorder_state,
            layout_view=PromptReorderLayoutView(
                rows=tuple(
                    replace(
                        row,
                        chip_indices=tuple(
                            index
                            for index in row.chip_indices
                            if index != dragged_segment_index
                        ),
                    )
                    for row in current_layout_view.rows
                    if row.chip_indices != (dragged_segment_index,)
                ),
                gaps=current_layout_view.gaps,
                partition_index_by_chip_index=(
                    current_layout_view.partition_index_by_chip_index
                ),
                prefix_text=current_layout_view.prefix_text,
                suffix_text=current_layout_view.suffix_text,
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
        """Return matching fake state and layout for one target."""

        _ = document_view
        assert isinstance(drop_target, PromptLineDropTarget)
        ordered = list(base_drag_state_view.reorder_state.ordered_chip_indices)
        ordered.insert(drop_target.insertion_index, dragged_segment_index)
        reorder_state = PromptReorderStateView(
            ordered_chip_indices=tuple(ordered),
            separator_slots=tuple(", " for _ in ordered[:-1]),
            has_trailing_comma=base_drag_state_view.reorder_state.has_trailing_comma,
        )
        layout_view = PromptReorderLayoutView(
            rows=(
                PromptReorderRowView(
                    row_index=drop_target.row_index,
                    chip_indices=tuple(ordered),
                ),
            ),
            gaps=base_drag_state_view.layout_view.gaps,
        )
        return PromptReorderPreparedStateView(
            reorder_state=reorder_state,
            layout_view=layout_view,
        )

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return the flattened layout order."""

        return tuple(index for row in layout_view.rows for index in row.chip_indices)


class _FakeDragGeometrySource:
    """Return exact live geometry publications selected by each test."""

    def __init__(
        self,
        *,
        chip_snapshot: PromptReorderChipGeometrySnapshot,
        placement_snapshot: PromptReorderPlacementSnapshot,
    ) -> None:
        """Store immutable geometry publications and query counters."""

        self.chip_snapshot = chip_snapshot
        self.placement_snapshot = placement_snapshot
        self.live_placement_query_count = 0

    def live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Return the prepared live placement publication."""

        _ = layout_view
        _ = chip_geometry_snapshot
        _ = gap_ranges_by_index
        self.live_placement_query_count += 1
        return self.placement_snapshot


def _unused_geometry_environment(reason: str) -> PromptReorderGeometryEnvironment:
    """Reject geometry work in an identity-only owner test."""

    raise AssertionError(f"geometry environment should not be requested: {reason}")


def _geometry_owner() -> PromptReorderGeometryOwner:
    """Build the real focused owner without a widget-host protocol."""

    preview_projection = PromptReorderPreviewProjectionOwner(
        projection_applicator=PromptProjectionApplicator(PromptProjectionBuilder()),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    return PromptReorderGeometryOwner(
        environment=_unused_geometry_environment,
        preview_projection=preview_projection,
    )


def _document_view(source_text: str) -> PromptDocumentView:
    """Return a minimal prompt document view for geometry identity tests."""

    return PromptDocumentView(
        source_text=source_text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(len(source_text)),
        has_trailing_comma=False,
    )


def _layout_view() -> PromptReorderLayoutView:
    """Return a minimal one-row reorder layout."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1, 2)),),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=", ",
                blank_line_count=0,
            ),
        ),
    )


def _state_view() -> PromptReorderStateView:
    """Return a minimal authoritative reorder state."""

    return PromptReorderStateView(
        ordered_chip_indices=(0, 1, 2),
        separator_slots=(", ", ", "),
        has_trailing_comma=False,
    )


def _empty_chip_snapshot() -> PromptReorderChipGeometrySnapshot:
    """Return a stable live chip publication for preparation-owner tests."""

    return PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={},
        ordered_chip_indices=(0, 1, 2),
        visual_line_count=1,
        layout_width=320.0,
        content_height=40.0,
        scroll_offset=0.0,
    )


def _placement_snapshot(*, populated: bool) -> PromptReorderPlacementSnapshot:
    """Return an empty or single-row placement publication."""

    placements: tuple[PromptReorderPlacementGeometry, ...] = ()
    if populated:
        target = PromptLineDropTarget(row_index=0, insertion_index=0)
        placements = (
            PromptReorderPlacementGeometry(
                placement_id=PromptReorderPlacementId(
                    target_kind=type(target).__name__,
                    row_index=0,
                    insertion_index=0,
                    gap_index=None,
                    blank_line_index=None,
                    visual_line_index=0,
                    ordinal=0,
                ),
                target=target,
                hit_rect=QRectF(0.0, 0.0, 20.0, 20.0),
                insertion_anchor_rect=QRectF(0.0, 0.0, 2.0, 20.0),
                visual_line_rect=QRectF(0.0, 0.0, 320.0, 20.0),
                expected_landing_rect=None,
                source_before=0,
                source_after=0,
            ),
        )
    return PromptReorderPlacementSnapshot(
        placements=placements,
        visual_line_count=1,
        layout_width=320.0,
        content_height=40.0,
    )


def _session_geometry_state() -> PromptReorderInteractionGeometryState:
    """Return one coherent interaction state before drag preparation."""

    layout_view = _layout_view()
    reorder_state = _state_view()
    state = PromptReorderInteractionGeometryState(
        document_view=_document_view("alpha, beta, gamma"),
        original_layout_view=layout_view,
        current_layout_view=layout_view,
        original_reorder_state=reorder_state,
        current_reorder_state=reorder_state,
        initial_ordered_indices=(0, 1, 2),
        ordered_segment_indices=(0, 1, 2),
        preview_layout_view=layout_view,
        preview_reorder_state=reorder_state,
    )
    identity = reorder_preview_target_identity(
        state,
        dragged_segment_index=0,
        target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
        preview_layout_view=layout_view,
    )
    return replace(
        state,
        preview_layout_target_identity=identity,
        preview_geometry_target_identity=identity,
    )
