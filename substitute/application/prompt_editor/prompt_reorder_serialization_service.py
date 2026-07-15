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

"""Serialize prompt reorder views into preview and commit text snapshots."""

from __future__ import annotations

import time

from substitute.domain.prompt import (
    PromptReorderSerialization,
    blank_line_drop_offsets as domain_blank_line_drop_offsets,
    build_reorder_chips,
    serialize_reorder_state_for_chips,
)
from substitute.shared.logging.logger import elapsed_ms_since, get_logger, log_debug

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_views import PromptDocumentView
from .prompt_reorder_gap_layout import between_row_gaps
from .prompt_reorder_projection_service import (
    domain_state_from_view,
    state_from_layout_view,
)
from .prompt_reorder_views import (
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)

_LOGGER = get_logger("application.prompt_editor.prompt_reorder_serialization_service")


class PromptReorderSerializationService:
    """Own prompt reorder serialization and range bookkeeping."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
    ) -> None:
        """Store the prompt document projector used to preserve source syntax."""

        self._document_projector = document_projector or PromptDocumentProjector()

    def serialize_reorder_layout_view(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
    ) -> str:
        """Serialize one reorder layout view using canonical separator-slot rules."""

        started_at = time.perf_counter()
        serialization = self._serialize_layout_view(document_view, layout_view)
        _log_reorder_serialization(
            "serialize_reorder_layout_view",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_count=len(serialization.chip_ranges_by_index),
            gap_count=len(layout_view.gaps),
        )
        return serialization.text

    def serialize_reorder_state_view(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
    ) -> str:
        """Serialize authoritative reorder source state without layout reversal."""

        started_at = time.perf_counter()
        serialization = self._serialize_state_view(document_view, state_view)
        _log_reorder_serialization(
            "serialize_reorder_state_view",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_count=len(serialization.chip_ranges_by_index),
            gap_count=0,
        )
        return serialization.text

    def build_reorder_preview_snapshot(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        include_edge_gaps: bool = True,
    ) -> PromptReorderPreviewSnapshot:
        """Build one syntax-ready preview snapshot for the supplied reorder layout."""

        started_at = time.perf_counter()
        state = state_from_layout_view(
            layout_view,
            has_trailing_comma=document_view.has_trailing_comma,
        )
        serialization = self._serialize_layout_view(document_view, layout_view)
        preview_snapshot = preview_snapshot_from_serialization(
            serialization,
            layout_view=layout_view,
            include_edge_gaps=include_edge_gaps,
            has_trailing_comma=state.has_trailing_comma,
        )
        _log_reorder_serialization(
            "build_reorder_preview_snapshot",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_count=len(preview_snapshot.chip_ranges_by_index),
            gap_count=len(preview_snapshot.gap_ranges_by_index),
            include_edge_gaps=include_edge_gaps,
        )
        return preview_snapshot

    def build_reorder_preview_snapshot_from_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        layout_view: PromptReorderLayoutView,
        include_edge_gaps: bool = True,
    ) -> PromptReorderPreviewSnapshot:
        """Build a syntax-ready preview from authoritative reorder source state."""

        started_at = time.perf_counter()
        serialization = self._serialize_state_view(document_view, state_view)
        state = domain_state_from_view(state_view)
        preview_snapshot = preview_snapshot_from_serialization(
            serialization,
            layout_view=layout_view,
            include_edge_gaps=include_edge_gaps,
            has_trailing_comma=state.has_trailing_comma,
        )
        _log_reorder_serialization(
            "build_reorder_preview_snapshot_from_state",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_count=len(preview_snapshot.chip_ranges_by_index),
            gap_count=len(preview_snapshot.gap_ranges_by_index),
            include_edge_gaps=include_edge_gaps,
        )
        return preview_snapshot

    def _serialize_layout_view(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderSerialization:
        """Serialize one layout view while preserving source-owned chip syntax."""

        document = self._document_projector.parse_document(document_view.source_text)
        chips = build_reorder_chips(document)
        return serialize_reorder_state_for_chips(
            state_from_layout_view(
                layout_view,
                has_trailing_comma=document_view.has_trailing_comma,
            ),
            chips_by_index=chips,
        )

    def _serialize_state_view(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
    ) -> PromptReorderSerialization:
        """Serialize one authoritative state view with source-owned chip syntax."""

        document = self._document_projector.parse_document(document_view.source_text)
        chips = build_reorder_chips(document)
        return serialize_reorder_state_for_chips(
            domain_state_from_view(state_view),
            chips_by_index=chips,
        )


def preview_snapshot_from_serialization(
    serialization: PromptReorderSerialization,
    *,
    layout_view: PromptReorderLayoutView,
    include_edge_gaps: bool,
    has_trailing_comma: bool,
) -> PromptReorderPreviewSnapshot:
    """Convert domain serialization ranges into application preview ranges."""

    preview_text, edge_gap_ranges_by_index = append_edge_gap_text(
        serialization.text,
        layout_view=layout_view,
        include_edge_gaps=include_edge_gaps,
        has_trailing_comma=has_trailing_comma,
    )
    gap_ranges_by_index = {
        gap.gap_index: (
            serialization.slot_ranges_by_index[slot_index].start,
            serialization.slot_ranges_by_index[slot_index].end,
        )
        for gap, slot_index in gap_slot_indices_from_layout_view(layout_view)
        if slot_index in serialization.slot_ranges_by_index
    }
    gap_ranges_by_index.update(edge_gap_ranges_by_index)
    return PromptReorderPreviewSnapshot(
        text=preview_text,
        chip_ranges_by_index={
            chip_index: (source_range.start, source_range.end)
            for chip_index, source_range in serialization.chip_ranges_by_index.items()
        },
        chip_rendered_ranges_by_index={
            chip_index: (source_range.start, source_range.end)
            for chip_index, source_range in serialization.rendered_ranges_by_index.items()
        },
        chip_owned_ranges_by_index={
            chip_index: tuple(
                (source_range.start, source_range.end) for source_range in source_ranges
            )
            for chip_index, source_ranges in serialization.owned_ranges_by_index.items()
        },
        gap_ranges_by_index=gap_ranges_by_index,
    )


def blank_line_drop_offsets(separator_text: str) -> tuple[int, ...]:
    """Return blank-line split offsets for one reorder separator string."""

    return domain_blank_line_drop_offsets(separator_text)


def append_edge_gap_text(
    text: str,
    *,
    layout_view: PromptReorderLayoutView,
    include_edge_gaps: bool,
    has_trailing_comma: bool,
) -> tuple[str, dict[int, tuple[int, int]]]:
    """Append visible edge gaps and return their serialized ranges."""

    if not include_edge_gaps:
        return text, {}

    serialized_text = text
    gap_ranges_by_index: dict[int, tuple[int, int]] = {}
    for gap in layout_view.gaps:
        if gap.placement is not PromptReorderGapPlacement.AFTER_LAST_ROW:
            continue
        serialized_text, gap_range = append_after_last_row_gap_text(
            serialized_text,
            gap.separator_text,
            has_trailing_comma=has_trailing_comma,
        )
        gap_ranges_by_index[gap.gap_index] = gap_range
    return serialized_text, gap_ranges_by_index


def append_after_last_row_gap_text(
    text: str,
    separator_text: str,
    *,
    has_trailing_comma: bool,
) -> tuple[str, tuple[int, int]]:
    """Append one trailing gap without duplicating canonical trailing commas."""

    if not has_trailing_comma:
        start = len(text)
        return f"{text}{separator_text}", (start, start + len(separator_text))

    if text.endswith(", "):
        start = len(text) - 2
        updated_text = f"{text[:-2]}{separator_text}"
        return updated_text, (start, start + len(separator_text))
    if text.endswith(","):
        start = len(text) - 1
        updated_text = f"{text[:-1]}{separator_text}"
        return updated_text, (start, start + len(separator_text))

    start = len(text)
    return f"{text}{separator_text}", (start, start + len(separator_text))


def gap_slot_indices_from_layout_view(
    layout_view: PromptReorderLayoutView,
) -> tuple[tuple[PromptReorderGapView, int], ...]:
    """Return the separator-slot index that corresponds to each exposed gap."""

    gap_slot_indices: list[tuple[PromptReorderGapView, int]] = []
    slot_index = 0
    between_gaps = between_row_gaps(layout_view)
    for row_index, row in enumerate(layout_view.rows):
        slot_index += max(0, len(row.chip_indices) - 1)
        if row_index < len(between_gaps):
            gap_slot_indices.append((between_gaps[row_index], slot_index))
            slot_index += 1
    return tuple(gap_slot_indices)


def _log_reorder_serialization(
    operation: str,
    *,
    started_at: float,
    text_length: int,
    chip_count: int,
    gap_count: int,
    include_edge_gaps: bool | None = None,
) -> None:
    """Log one prompt-safe reorder serialization event."""

    context: dict[str, object] = {
        "operation": operation,
        "elapsed_ms": f"{elapsed_ms_since(started_at):.3f}",
        "text_length": text_length,
        "chip_count": chip_count,
        "gap_count": gap_count,
    }
    if include_edge_gaps is not None:
        context["include_edge_gaps"] = include_edge_gaps
    log_debug(
        _LOGGER,
        "Prompt reorder serialization resolved",
        **context,
    )


__all__ = [
    "PromptReorderSerializationService",
    "append_after_last_row_gap_text",
    "append_edge_gap_text",
    "blank_line_drop_offsets",
    "gap_slot_indices_from_layout_view",
    "preview_snapshot_from_serialization",
]
