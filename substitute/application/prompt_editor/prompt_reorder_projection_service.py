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

"""Project prompt reorder domain state into application reorder views."""

from __future__ import annotations

import time

from substitute.domain.prompt import (
    PromptGapBlankLineDropTarget as DomainPromptGapBlankLineDropTarget,
    PromptLineDropTarget as DomainPromptLineDropTarget,
    PromptReorderState,
    build_reorder_chips,
    build_reorder_state_from_chips,
    derive_rows_and_gaps,
)
from substitute.shared.logging.logger import elapsed_ms_since, get_logger, log_debug

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_view_mapper import prompt_reorder_chip_view_from_domain
from .prompt_document_views import PromptDocumentView, PromptReorderChipView
from .prompt_reorder_views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderSessionView,
    PromptReorderStateView,
)

_LOGGER = get_logger("application.prompt_editor.prompt_reorder_projection_service")


class PromptReorderProjectionService:
    """Own reorder chip, state, and layout projection from prompt documents."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
    ) -> None:
        """Store the prompt document projector used for domain reorder state."""

        self._document_projector = document_projector or PromptDocumentProjector()

    def reorder_chips(
        self,
        document_view: PromptDocumentView,
    ) -> tuple[PromptReorderChipView, ...]:
        """Return typed reorder chips with explicit separator metadata."""

        started_at = time.perf_counter()
        document = self._document_projector.parse_document(document_view.source_text)
        chip_views = tuple(
            prompt_reorder_chip_view_from_domain(document, chip)
            for chip in build_reorder_chips(document)
        )
        _log_reorder_projection(
            "reorder_chips",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_count=len(chip_views),
        )
        return chip_views

    def build_reorder_session_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderSessionView:
        """Build reorder chips and layout from one shared parsed document."""

        started_at = time.perf_counter()
        document = self._document_projector.parse_document(document_view.source_text)
        chips = build_reorder_chips(document)
        reorder_state = build_reorder_state_from_chips(document, chips)
        session_view = PromptReorderSessionView(
            chips=tuple(
                prompt_reorder_chip_view_from_domain(document, chip) for chip in chips
            ),
            reorder_state=state_view_from_domain(reorder_state),
            layout_view=layout_view_from_state(reorder_state),
        )
        _log_reorder_projection(
            "build_reorder_session_view",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_count=len(session_view.chips),
            row_count=len(session_view.layout_view.rows),
            gap_count=len(session_view.layout_view.gaps),
        )
        return session_view

    def build_reorder_state_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderStateView:
        """Build authoritative reorder source state from the current prompt snapshot."""

        started_at = time.perf_counter()
        document = self._document_projector.parse_document(document_view.source_text)
        state_view = state_view_from_domain(
            build_reorder_state_from_chips(document, build_reorder_chips(document))
        )
        _log_reorder_projection(
            "build_reorder_state_view",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_count=len(state_view.ordered_chip_indices),
        )
        return state_view

    def build_reorder_layout_view_from_state(
        self,
        state_view: PromptReorderStateView,
    ) -> PromptReorderLayoutView:
        """Derive display rows and gaps from authoritative reorder state."""

        started_at = time.perf_counter()
        layout_view = layout_view_from_state(domain_state_from_view(state_view))
        _log_reorder_projection(
            "build_reorder_layout_view_from_state",
            started_at=started_at,
            chip_count=len(state_view.ordered_chip_indices),
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
        )
        return layout_view

    def build_reorder_layout_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderLayoutView:
        """Build one derived reorder layout view from the current prompt snapshot."""

        started_at = time.perf_counter()
        document = self._document_projector.parse_document(document_view.source_text)
        layout_view = layout_view_from_state(
            build_reorder_state_from_chips(document, build_reorder_chips(document))
        )
        _log_reorder_projection(
            "build_reorder_layout_view",
            started_at=started_at,
            text_length=len(document_view.source_text),
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
        )
        return layout_view

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return chip indices in the current visual order."""

        return ordered_chip_indices_from_layout_view(layout_view)


def state_view_from_domain(
    reorder_state: PromptReorderState,
) -> PromptReorderStateView:
    """Return the application-facing view of authoritative reorder source state."""

    return PromptReorderStateView(
        ordered_chip_indices=reorder_state.ordered_segment_indices,
        separator_slots=reorder_state.separator_slots,
        has_trailing_comma=reorder_state.has_trailing_comma,
    )


def domain_state_from_view(state_view: PromptReorderStateView) -> PromptReorderState:
    """Return the domain reorder state represented by an application view."""

    return PromptReorderState(
        ordered_segment_indices=state_view.ordered_chip_indices,
        separator_slots=state_view.separator_slots,
        has_trailing_comma=state_view.has_trailing_comma,
    )


def layout_view_from_state(
    reorder_state: PromptReorderState,
) -> PromptReorderLayoutView:
    """Project one canonical reorder state into application-facing derived view types."""

    rows, gaps = derive_rows_and_gaps(reorder_state)
    return PromptReorderLayoutView(
        rows=tuple(
            PromptReorderRowView(
                row_index=row.row_index,
                chip_indices=row.segment_indices,
                separator_slots=reorder_state.separator_slots[
                    row.start_segment_offset : row.start_segment_offset
                    + max(0, len(row.segment_indices) - 1)
                ],
            )
            for row in rows
        ),
        gaps=tuple(
            PromptReorderGapView(
                gap_index=gap.gap_index,
                separator_text=gap.separator_text,
                blank_line_count=len(gap.blank_line_offsets),
                placement=PromptReorderGapPlacement.BETWEEN_ROWS,
            )
            for gap in gaps
        ),
    )


def state_from_layout_view(
    layout_view: PromptReorderLayoutView,
    *,
    has_trailing_comma: bool,
) -> PromptReorderState:
    """Rebuild one canonical reorder state from a derived application layout view."""

    ordered_segment_indices = ordered_chip_indices_from_layout_view(layout_view)
    separator_slots: list[str] = []
    between_gaps = _between_row_gaps(layout_view)
    for row_index, row in enumerate(layout_view.rows):
        if len(row.chip_indices) > 1:
            row_separator_slots = (
                row.separator_slots
                if len(row.separator_slots) == len(row.chip_indices) - 1
                else tuple(", " for _ in row.chip_indices[:-1])
            )
            separator_slots.extend(row_separator_slots)
        if row_index < len(between_gaps):
            separator_slots.append(between_gaps[row_index].separator_text)

    return PromptReorderState(
        ordered_segment_indices=ordered_segment_indices,
        separator_slots=tuple(separator_slots),
        has_trailing_comma=has_trailing_comma,
    )


def ordered_chip_indices_from_layout_view(
    layout_view: PromptReorderLayoutView,
) -> tuple[int, ...]:
    """Return the flattened chip order represented by one derived layout view."""

    return tuple(
        chip_index for row in layout_view.rows for chip_index in row.chip_indices
    )


def domain_target_from_view(
    drop_target: PromptReorderDropTarget,
) -> DomainPromptLineDropTarget | DomainPromptGapBlankLineDropTarget:
    """Convert one application drop target into the domain reorder target type."""

    if isinstance(drop_target, PromptLineDropTarget):
        return DomainPromptLineDropTarget(
            row_index=drop_target.row_index,
            insertion_index=drop_target.insertion_index,
        )
    return DomainPromptGapBlankLineDropTarget(
        gap_index=drop_target.gap_index,
        blank_line_index=drop_target.blank_line_index,
    )


def _between_row_gaps(
    layout_view: PromptReorderLayoutView,
) -> tuple[PromptReorderGapView, ...]:
    """Return layout gaps that separate two populated rows."""

    return tuple(
        gap
        for gap in layout_view.gaps
        if gap.placement is PromptReorderGapPlacement.BETWEEN_ROWS
    )


def _log_reorder_projection(
    operation: str,
    *,
    started_at: float,
    text_length: int | None = None,
    chip_count: int | None = None,
    row_count: int | None = None,
    gap_count: int | None = None,
) -> None:
    """Log one prompt-safe reorder projection event."""

    context: dict[str, object] = {
        "operation": operation,
        "elapsed_ms": f"{elapsed_ms_since(started_at):.3f}",
    }
    if text_length is not None:
        context["text_length"] = text_length
    if chip_count is not None:
        context["chip_count"] = chip_count
    if row_count is not None:
        context["row_count"] = row_count
    if gap_count is not None:
        context["gap_count"] = gap_count
    log_debug(
        _LOGGER,
        "Prompt reorder projection resolved",
        **context,
    )


__all__ = [
    "PromptReorderProjectionService",
    "domain_state_from_view",
    "domain_target_from_view",
    "layout_view_from_state",
    "ordered_chip_indices_from_layout_view",
    "state_from_layout_view",
    "state_view_from_domain",
]
