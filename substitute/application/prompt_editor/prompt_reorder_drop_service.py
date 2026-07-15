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

"""Apply prompt reorder drag and drop transforms to reorder views."""

from __future__ import annotations

import time

from substitute.domain.prompt import (
    PromptReorderState,
    apply_drop_target_to_state,
    build_base_drag_state,
    build_reorder_chips,
    build_reorder_state_from_chips,
    split_gap_for_blank_line_insert,
)
from substitute.shared.logging.logger import elapsed_ms_since, get_logger, log_debug

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_views import PromptDocumentView
from .prompt_reorder_gap_layout import (
    between_row_gaps,
    gap_by_index,
    layout_view_from_rows_and_gaps,
    split_after_last_row_gap_for_insert,
    trailing_edge_separator_text,
    trailing_edge_separator_text_for_hidden_chip,
    with_edge_gaps_from_layout,
    with_trailing_edge_gap,
)
from .prompt_reorder_projection_service import (
    domain_state_from_view,
    domain_target_from_view,
    layout_view_from_state,
    state_from_layout_view,
    state_view_from_domain,
)
from .prompt_reorder_views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderStateView,
)

_LOGGER = get_logger("application.prompt_editor.prompt_reorder_drop_service")


class PromptReorderDropService:
    """Own base-drag and preview-drop transforms for prompt reorder."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
    ) -> None:
        """Store the prompt document projector used for domain reorder state."""

        self._document_projector = document_projector or PromptDocumentProjector()

    def build_base_drag_layout_view(
        self,
        document_view: PromptDocumentView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Build the derived layout view shown while the dragged chip is hidden."""

        started_at = time.perf_counter()
        document = self._document_projector.parse_document(document_view.source_text)
        base_drag_state = build_base_drag_state(
            build_reorder_state_from_chips(document, build_reorder_chips(document)),
            dragged_segment_index=dragged_segment_index,
        )
        layout_view = layout_view_from_state(base_drag_state)
        _log_reorder_drop(
            "build_base_drag_layout_view",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_index=dragged_segment_index,
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
        )
        return layout_view

    def build_base_drag_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Build the hidden-drag layout from the supplied in-session reorder layout."""

        started_at = time.perf_counter()
        base_drag_state = build_base_drag_state(
            state_from_layout_view(
                layout_view,
                has_trailing_comma=document_view.has_trailing_comma,
            ),
            dragged_segment_index=dragged_segment_index,
        )
        base_drag_layout = layout_view_from_state(base_drag_state)
        updated_layout = with_trailing_edge_gap(
            base_drag_layout,
            separator_text=trailing_edge_separator_text_for_hidden_chip(
                layout_view,
                dragged_segment_index=dragged_segment_index,
                has_trailing_comma=document_view.has_trailing_comma,
            ),
        )
        _log_reorder_drop(
            "build_base_drag_layout_view_from_layout",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_index=dragged_segment_index,
            row_count=len(updated_layout.rows),
            gap_count=len(updated_layout.gaps),
        )
        return updated_layout

    def build_base_drag_reorder_state_from_state(
        self,
        state_view: PromptReorderStateView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderStateView:
        """Return authoritative source state while one chip is lifted."""

        started_at = time.perf_counter()
        updated_state = state_view_from_domain(
            build_base_drag_state(
                domain_state_from_view(state_view),
                dragged_segment_index=dragged_segment_index,
            )
        )
        _log_reorder_drop(
            "build_base_drag_reorder_state_from_state",
            started_at=started_at,
            chip_index=dragged_segment_index,
            chip_count=len(updated_state.ordered_chip_indices),
        )
        return updated_state

    def build_preview_drop_layout_view(
        self,
        document_view: PromptDocumentView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Build the derived layout view previewed for the supplied drop target."""

        started_at = time.perf_counter()
        document = self._document_projector.parse_document(document_view.source_text)
        preview_state = apply_drop_target_to_state(
            build_base_drag_state(
                build_reorder_state_from_chips(document, build_reorder_chips(document)),
                dragged_segment_index=dragged_segment_index,
            ),
            dragged_segment_index=dragged_segment_index,
            target=domain_target_from_view(drop_target),
        )
        layout_view = layout_view_from_state(preview_state)
        _log_reorder_drop(
            "build_preview_drop_layout_view",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_index=dragged_segment_index,
            drop_target_kind=_drop_target_kind(drop_target),
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
        )
        return layout_view

    def build_preview_drop_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Build one preview layout from the current in-session reorder layout."""

        started_at = time.perf_counter()
        base_drag_layout = self.build_base_drag_layout_view_from_layout(
            document_view,
            layout_view,
            dragged_segment_index=dragged_segment_index,
        )
        preview_layout = apply_drop_target_to_layout_view(
            base_drag_layout,
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
            has_trailing_comma=document_view.has_trailing_comma,
        )
        _log_reorder_drop(
            "build_preview_drop_layout_view_from_layout",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_index=dragged_segment_index,
            drop_target_kind=_drop_target_kind(drop_target),
            row_count=len(preview_layout.rows),
            gap_count=len(preview_layout.gaps),
        )
        return preview_layout

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
        """Apply a drop target to authoritative source state for commit/preview."""

        started_at = time.perf_counter()
        base_drag_state = build_base_drag_state(
            domain_state_from_view(state_view),
            dragged_segment_index=dragged_segment_index,
        )
        if isinstance(drop_target, PromptGapBlankLineDropTarget):
            target_gap = (
                None
                if base_drag_layout_view is None
                else gap_by_index(base_drag_layout_view, drop_target.gap_index)
            )
            if (
                target_gap is not None
                and target_gap.placement is PromptReorderGapPlacement.AFTER_LAST_ROW
            ):
                updated_state = state_view_from_domain(
                    append_chip_to_after_last_gap_state(
                        base_drag_state,
                        target_gap=target_gap,
                        dragged_segment_index=dragged_segment_index,
                        blank_line_index=drop_target.blank_line_index,
                    )
                )
                _log_reorder_drop(
                    "build_preview_drop_reorder_state_from_state",
                    started_at=started_at,
                    text_length=len(document_view.source_text),
                    chip_index=dragged_segment_index,
                    gap_index=drop_target.gap_index,
                    drop_target_kind=_drop_target_kind(drop_target),
                    chip_count=len(updated_state.ordered_chip_indices),
                )
                return updated_state

        _ = current_layout_view
        updated_state = state_view_from_domain(
            apply_drop_target_to_state(
                base_drag_state,
                dragged_segment_index=dragged_segment_index,
                target=domain_target_from_view(drop_target),
            )
        )
        _log_reorder_drop(
            "build_preview_drop_reorder_state_from_state",
            started_at=started_at,
            text_length=len(document_view.source_text),
            chip_index=dragged_segment_index,
            drop_target_kind=_drop_target_kind(drop_target),
            chip_count=len(updated_state.ordered_chip_indices),
        )
        return updated_state


def append_chip_to_after_last_gap_state(
    base_drag_state: PromptReorderState,
    *,
    target_gap: PromptReorderGapView,
    dragged_segment_index: int,
    blank_line_index: int,
) -> PromptReorderState:
    """Return source state for a drop into a transient after-last-row gap."""

    prefix_separator, _suffix_separator = split_after_last_row_gap_for_insert(
        target_gap.separator_text,
        blank_line_index=blank_line_index,
    )
    ordered_segment_indices = list(base_drag_state.ordered_segment_indices)
    separator_slots = list(base_drag_state.separator_slots)
    if ordered_segment_indices:
        separator_slots.append(prefix_separator)
    ordered_segment_indices.append(dragged_segment_index)
    return PromptReorderState(
        ordered_segment_indices=tuple(ordered_segment_indices),
        separator_slots=tuple(separator_slots),
        has_trailing_comma=base_drag_state.has_trailing_comma,
    )


def apply_drop_target_to_layout_view(
    base_drag_layout: PromptReorderLayoutView,
    *,
    dragged_segment_index: int,
    drop_target: PromptReorderDropTarget,
    has_trailing_comma: bool,
) -> PromptReorderLayoutView:
    """Apply one drop target to an in-session layout, including edge gaps."""

    if isinstance(drop_target, PromptLineDropTarget):
        preview_state = apply_drop_target_to_state(
            state_from_layout_view(
                base_drag_layout,
                has_trailing_comma=has_trailing_comma,
            ),
            dragged_segment_index=dragged_segment_index,
            target=domain_target_from_view(drop_target),
        )
        return with_edge_gaps_from_layout(
            layout_view_from_state(preview_state),
            source_layout=base_drag_layout,
        )

    return apply_blank_line_drop_target_to_layout_view(
        base_drag_layout,
        dragged_segment_index=dragged_segment_index,
        drop_target=drop_target,
    )


def apply_blank_line_drop_target_to_layout_view(
    base_drag_layout: PromptReorderLayoutView,
    *,
    dragged_segment_index: int,
    drop_target: PromptGapBlankLineDropTarget,
) -> PromptReorderLayoutView:
    """Insert the dragged chip into any visible blank-line gap."""

    target_gap = gap_by_index(base_drag_layout, drop_target.gap_index)
    if target_gap is None:
        raise ValueError("gap_index must reference an available reorder gap.")

    if target_gap.placement is PromptReorderGapPlacement.AFTER_LAST_ROW:
        return apply_after_last_row_gap_drop(
            base_drag_layout,
            target_gap=target_gap,
            dragged_segment_index=dragged_segment_index,
            blank_line_index=drop_target.blank_line_index,
        )

    return apply_between_row_gap_drop(
        base_drag_layout,
        target_gap=target_gap,
        dragged_segment_index=dragged_segment_index,
        blank_line_index=drop_target.blank_line_index,
    )


def apply_between_row_gap_drop(
    base_drag_layout: PromptReorderLayoutView,
    *,
    target_gap: PromptReorderGapView,
    dragged_segment_index: int,
    blank_line_index: int,
) -> PromptReorderLayoutView:
    """Insert the dragged chip into a blank line between two populated rows."""

    gaps_between_rows = list(between_row_gaps(base_drag_layout))
    gap_offset = gaps_between_rows.index(target_gap)
    prefix_separator, suffix_separator = split_gap_for_blank_line_insert(
        target_gap.separator_text,
        blank_line_index=blank_line_index,
    )
    row_indices = [row.chip_indices for row in base_drag_layout.rows]
    row_indices.insert(gap_offset + 1, (dragged_segment_index,))

    between_separator_texts = [gap.separator_text for gap in gaps_between_rows]
    between_separator_texts[gap_offset] = prefix_separator
    between_separator_texts.insert(gap_offset + 1, suffix_separator)
    return layout_view_from_rows_and_gaps(
        row_indices,
        between_separator_texts=tuple(between_separator_texts),
        trailing_edge_separator_text=trailing_edge_separator_text(base_drag_layout),
    )


def apply_after_last_row_gap_drop(
    base_drag_layout: PromptReorderLayoutView,
    *,
    target_gap: PromptReorderGapView,
    dragged_segment_index: int,
    blank_line_index: int,
) -> PromptReorderLayoutView:
    """Insert the dragged chip into a blank line after the final populated row."""

    prefix_separator, suffix_separator = split_after_last_row_gap_for_insert(
        target_gap.separator_text,
        blank_line_index=blank_line_index,
    )
    row_indices = [row.chip_indices for row in base_drag_layout.rows]
    row_indices.append((dragged_segment_index,))
    between_separator_texts = tuple(
        gap.separator_text for gap in between_row_gaps(base_drag_layout)
    ) + (prefix_separator,)
    return layout_view_from_rows_and_gaps(
        row_indices,
        between_separator_texts=between_separator_texts,
        trailing_edge_separator_text=suffix_separator,
    )


def _drop_target_kind(drop_target: PromptReorderDropTarget) -> str:
    """Return a prompt-safe drop target discriminator."""

    if isinstance(drop_target, PromptLineDropTarget):
        return "line"
    return "blank_line_gap"


def _log_reorder_drop(
    operation: str,
    *,
    started_at: float,
    text_length: int | None = None,
    chip_index: int | None = None,
    chip_count: int | None = None,
    gap_index: int | None = None,
    drop_target_kind: str | None = None,
    row_count: int | None = None,
    gap_count: int | None = None,
) -> None:
    """Log one prompt-safe reorder drop event."""

    context: dict[str, object] = {
        "operation": operation,
        "elapsed_ms": f"{elapsed_ms_since(started_at):.3f}",
    }
    if text_length is not None:
        context["text_length"] = text_length
    if chip_index is not None:
        context["chip_index"] = chip_index
    if chip_count is not None:
        context["chip_count"] = chip_count
    if gap_index is not None:
        context["gap_index"] = gap_index
    if drop_target_kind is not None:
        context["drop_target_kind"] = drop_target_kind
    if row_count is not None:
        context["row_count"] = row_count
    if gap_count is not None:
        context["gap_count"] = gap_count
    log_debug(
        _LOGGER,
        "Prompt reorder drop resolved",
        **context,
    )


__all__ = [
    "PromptReorderDropService",
    "append_chip_to_after_last_gap_state",
    "apply_after_last_row_gap_drop",
    "apply_between_row_gap_drop",
    "apply_blank_line_drop_target_to_layout_view",
    "apply_drop_target_to_layout_view",
]
