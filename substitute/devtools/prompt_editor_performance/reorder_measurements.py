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

"""Reorder measurement helpers for prompt editor performance scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QPoint, QRect

from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptLineDropTarget,
    PromptReorderLayoutView,
    PromptSyntaxService,
)
from substitute.devtools.prompt_editor_performance.fakes import (
    wildcard_gateway,
)
from substitute.devtools.prompt_editor_performance.metrics import OperationCounter
from substitute.devtools.prompt_editor_performance.syntax_profile import (
    prompt_syntax_profile,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import SegmentReorderOverlay
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)


class ReorderCounterSource(Protocol):
    """Expose benchmark counters from a reorder interaction owner."""

    def reorder_performance_counters(self) -> dict[str, object]:
        """Return current reorder interaction counters."""


@dataclass(frozen=True, slots=True)
class ReorderMeasurementState:
    """Carry prepared reorder projection state for geometry-cache measurement."""

    preview_state: PromptReorderPreviewState
    preview_layout_view: PromptReorderLayoutView
    base_drag_layout_view: PromptReorderLayoutView


@dataclass(frozen=True, slots=True)
class ReorderPointerTarget:
    """Identify one logical chip target on the production overlay surface."""

    overlay: SegmentReorderOverlay
    segment_index: int

    def rect(self) -> QRect:
        """Return overlay-local bounds for this logical target."""

        return self.overlay.pointer_region_rects()[self.segment_index]


def current_reorder_overlay(editor: PromptEditor) -> SegmentReorderOverlay:
    """Return the active reorder overlay created by the real editor."""

    overlay = getattr(editor, "_segment_overlay", None)
    if not isinstance(overlay, SegmentReorderOverlay):
        raise RuntimeError("Alt did not create a prompt reorder overlay.")
    return overlay


def overlay_chip_by_segment_index(
    overlay: SegmentReorderOverlay,
    segment_index: int,
) -> ReorderPointerTarget:
    """Return one logical reorder target by source segment index."""

    if segment_index not in overlay.pointer_region_rects():
        raise RuntimeError(f"Missing reorder chip for segment {segment_index}.")
    return ReorderPointerTarget(overlay, segment_index)


def chip_drop_target_global(
    chip: ReorderPointerTarget, *, trailing: bool = False
) -> QPoint:
    """Return a stable global point near the chip edge used for drop targeting."""

    rect = chip.rect()
    x = rect.right() - 3 if trailing else rect.left() + 4
    return chip.overlay.mapToGlobal(QPoint(x, rect.center().y()))


def capture_reorder_interaction_counts(
    overlay: ReorderCounterSource,
    extra_counts: dict[str, int | float],
) -> None:
    """Copy reorder interaction counters into one scenario result."""

    for key, value in overlay.reorder_performance_counters().items():
        if isinstance(key, str) and isinstance(value, int | float):
            extra_counts[key] = value


def build_reorder_measurement_state(text: str) -> ReorderMeasurementState:
    """Build prepared reorder state used by the benchmark geometry hot path."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        cast(
            PromptWildcardCatalogGateway,
            wildcard_gateway("empty", OperationCounter()),
        )
    )
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard", "lora")
    dragged_chip_index = 1
    drop_target = PromptLineDropTarget(row_index=0, insertion_index=2)
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
        drop_target=drop_target,
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    preview_document_view = document_service.build_document_view(preview_snapshot.text)
    base_drag_document_view = document_service.build_document_view(
        base_drag_snapshot.text
    )
    preview_state = PromptReorderPreviewState(
        preview_snapshot=PromptReorderProjectionSnapshot(
            document_view=preview_document_view,
            render_plan=syntax_service.build_render_plan(
                preview_document_view,
                syntax_profile,
            ),
            chip_rendered_ranges_by_index=preview_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
        ),
        base_drag_snapshot=PromptReorderProjectionSnapshot(
            document_view=base_drag_document_view,
            render_plan=syntax_service.build_render_plan(
                base_drag_document_view,
                syntax_profile,
            ),
            chip_rendered_ranges_by_index=base_drag_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=base_drag_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=base_drag_snapshot.gap_ranges_by_index,
        ),
        ordered_chip_indices=tuple(
            document_service.reorder_layout_chip_indices(preview_layout_view)
        ),
        dragged_chip_index=dragged_chip_index,
        instrumentation_gesture_id=1,
        instrumentation_reason="measure_reorder_drag",
    )
    return ReorderMeasurementState(
        preview_state=preview_state,
        preview_layout_view=preview_layout_view,
        base_drag_layout_view=base_drag_layout_view,
    )


def exercise_reorder_geometry_caches(
    editor: PromptEditor,
    measurement_state: ReorderMeasurementState,
) -> None:
    """Touch projection-owned reorder geometry queries for cache counters."""

    base_drag_snapshot = measurement_state.preview_state.base_drag_snapshot
    if base_drag_snapshot is None:
        raise RuntimeError("Reorder measurement requires base-drag geometry state.")

    editor.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=measurement_state.base_drag_layout_view,
    )
    placement_snapshot = editor.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=measurement_state.base_drag_layout_view,
    )
    editor.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=measurement_state.base_drag_layout_view,
    )
    editor.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=measurement_state.base_drag_layout_view,
    )

    editor.reorder_preview_chip_geometry_snapshot(
        snapshot=measurement_state.preview_state.preview_snapshot,
        layout_view=measurement_state.preview_layout_view,
    )
    editor.reorder_preview_chip_geometry_snapshot(
        snapshot=measurement_state.preview_state.preview_snapshot,
        layout_view=measurement_state.preview_layout_view,
    )

    if placement_snapshot.placements:
        placement = placement_snapshot.placements[0]
        editor.reorder_placement_at_rect(
            placement.hit_rect,
            snapshot=placement_snapshot,
            active_placement_id=placement.placement_id,
        )


def surface_for(editor: PromptEditor) -> PromptProjectionSurface:
    """Return the prompt projection surface owned by one editor."""

    return cast(PromptProjectionSurface, getattr(editor, "_surface"))


def reorder_cache_counts(editor: PromptEditor) -> dict[str, int]:
    """Return integer reorder geometry cache counters when available."""

    counters = editor.reorder_geometry_cache_counters()
    return {
        key: value
        for key, value in counters.items()
        if isinstance(key, str) and isinstance(value, int)
    }


__all__ = [
    "ReorderMeasurementState",
    "build_reorder_measurement_state",
    "capture_reorder_interaction_counts",
    "chip_drop_target_global",
    "current_reorder_overlay",
    "exercise_reorder_geometry_caches",
    "overlay_chip_by_segment_index",
    "reorder_cache_counts",
    "surface_for",
]
