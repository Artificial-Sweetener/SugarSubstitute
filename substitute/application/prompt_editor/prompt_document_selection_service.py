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

"""Resolve prompt document selections from application prompt view models."""

from __future__ import annotations

import time

from substitute.shared.logging.logger import elapsed_ms_since, get_logger, log_debug

from .prompt_document_views import (
    PromptDocumentView,
    PromptEmphasisView,
    PromptReorderChipView,
    PromptSegmentView,
)

_LOGGER = get_logger("application.prompt_editor.prompt_document_selection_service")


class PromptDocumentSelectionService:
    """Own cursor and source-range lookups over prompt document views."""

    def segment_at_position(
        self,
        document_view: PromptDocumentView,
        position: int,
    ) -> PromptSegmentView | None:
        """Return the visible prompt segment at one cursor position."""

        started_at = time.perf_counter()
        for segment in document_view.segments:
            if _contains_position(
                start=segment.selection_start,
                end=segment.selection_end,
                position=position,
                inclusive_end=True,
            ):
                _log_selection_lookup(
                    "segment_at_position",
                    started_at=started_at,
                    text_length=len(document_view.source_text),
                    cursor_position=position,
                    segment_index=segment.index,
                    matched=True,
                )
                return segment
        _log_selection_lookup(
            "segment_at_position",
            started_at=started_at,
            text_length=len(document_view.source_text),
            cursor_position=position,
            matched=False,
        )
        return None

    def reorder_chip_at_position(
        self,
        reorder_chips: tuple[PromptReorderChipView, ...],
        position: int,
    ) -> PromptReorderChipView | None:
        """Return the reorder chip selected by one cursor position."""

        started_at = time.perf_counter()
        for chip in reorder_chips:
            if _contains_position(
                start=chip.selection_start,
                end=chip.selection_end,
                position=position,
                inclusive_end=True,
            ):
                _log_selection_lookup(
                    "reorder_chip_at_position",
                    started_at=started_at,
                    cursor_position=position,
                    chip_index=chip.index,
                    matched=True,
                )
                return chip
        _log_selection_lookup(
            "reorder_chip_at_position",
            started_at=started_at,
            cursor_position=position,
            matched=False,
        )
        return None

    def emphasis_at_position(
        self,
        document_view: PromptDocumentView,
        position: int,
    ) -> PromptEmphasisView | None:
        """Return the innermost emphasis span selected by one cursor position."""

        started_at = time.perf_counter()
        for span in reversed(document_view.emphasis_spans):
            if _contains_position(
                start=span.content_start,
                end=span.content_end,
                position=position,
                inclusive_end=True,
            ):
                _log_selection_lookup(
                    "emphasis_at_position",
                    started_at=started_at,
                    text_length=len(document_view.source_text),
                    cursor_position=position,
                    matched=True,
                )
                return span
        for span in reversed(document_view.emphasis_spans):
            if span.outer_start < position < span.outer_end:
                _log_selection_lookup(
                    "emphasis_at_position",
                    started_at=started_at,
                    text_length=len(document_view.source_text),
                    cursor_position=position,
                    matched=True,
                )
                return span
        _log_selection_lookup(
            "emphasis_at_position",
            started_at=started_at,
            text_length=len(document_view.source_text),
            cursor_position=position,
            matched=False,
        )
        return None

    def emphasis_for_content_range(
        self,
        document_view: PromptDocumentView,
        *,
        content_start: int,
        content_end: int,
    ) -> PromptEmphasisView | None:
        """Return the emphasis span matching or containing one visible content range."""

        started_at = time.perf_counter()
        for span in document_view.emphasis_spans:
            if span.content_start == content_start and span.content_end == content_end:
                _log_selection_lookup(
                    "emphasis_for_content_range",
                    started_at=started_at,
                    text_length=len(document_view.source_text),
                    selection_start=content_start,
                    selection_end=content_end,
                    matched=True,
                )
                return span
        for span in reversed(document_view.emphasis_spans):
            if span.content_start <= content_start and content_end <= span.content_end:
                _log_selection_lookup(
                    "emphasis_for_content_range",
                    started_at=started_at,
                    text_length=len(document_view.source_text),
                    selection_start=content_start,
                    selection_end=content_end,
                    matched=True,
                )
                return span
        _log_selection_lookup(
            "emphasis_for_content_range",
            started_at=started_at,
            text_length=len(document_view.source_text),
            selection_start=content_start,
            selection_end=content_end,
            matched=False,
        )
        return None

    def emphasis_for_outer_range(
        self,
        document_view: PromptDocumentView,
        *,
        outer_start: int,
        outer_end: int,
    ) -> PromptEmphasisView | None:
        """Return the emphasis span whose full shell matches one outer source range."""

        started_at = time.perf_counter()
        for span in document_view.emphasis_spans:
            if span.outer_start == outer_start and span.outer_end == outer_end:
                _log_selection_lookup(
                    "emphasis_for_outer_range",
                    started_at=started_at,
                    text_length=len(document_view.source_text),
                    selection_start=outer_start,
                    selection_end=outer_end,
                    matched=True,
                )
                return span
        _log_selection_lookup(
            "emphasis_for_outer_range",
            started_at=started_at,
            text_length=len(document_view.source_text),
            selection_start=outer_start,
            selection_end=outer_end,
            matched=False,
        )
        return None


def emphasis_span_at_cursor(
    document_view: PromptDocumentView,
    *,
    segment: PromptSegmentView,
    cursor_position: int,
) -> PromptEmphasisView | None:
    """Return the innermost weighted emphasis span containing the cursor."""

    started_at = time.perf_counter()
    for span in reversed(document_view.emphasis_spans):
        if not (
            segment.selection_start <= span.outer_start
            and span.outer_end <= segment.selection_end
            and span.outer_start <= cursor_position <= span.outer_end
        ):
            continue
        _log_selection_lookup(
            "emphasis_span_at_cursor",
            started_at=started_at,
            text_length=len(document_view.source_text),
            cursor_position=cursor_position,
            segment_index=segment.index,
            matched=True,
        )
        return span
    _log_selection_lookup(
        "emphasis_span_at_cursor",
        started_at=started_at,
        text_length=len(document_view.source_text),
        cursor_position=cursor_position,
        segment_index=segment.index,
        matched=False,
    )
    return None


def _contains_position(
    *,
    start: int,
    end: int,
    position: int,
    inclusive_end: bool,
) -> bool:
    """Return whether one half-open source range contains the supplied position."""

    if inclusive_end:
        return start <= position <= end
    return start <= position < end


def _log_selection_lookup(
    operation: str,
    *,
    started_at: float,
    matched: bool,
    text_length: int | None = None,
    cursor_position: int | None = None,
    selection_start: int | None = None,
    selection_end: int | None = None,
    segment_index: int | None = None,
    chip_index: int | None = None,
) -> None:
    """Log one prompt-safe selection lookup result."""

    context: dict[str, object] = {
        "operation": operation,
        "matched": matched,
    }
    if text_length is not None:
        context["text_length"] = text_length
    if cursor_position is not None:
        context["cursor_position"] = cursor_position
    if selection_start is not None:
        context["selection_start"] = selection_start
    if selection_end is not None:
        context["selection_end"] = selection_end
    if segment_index is not None:
        context["segment_index"] = segment_index
    if chip_index is not None:
        context["chip_index"] = chip_index
    context["elapsed_ms"] = f"{elapsed_ms_since(started_at):.3f}"
    log_debug(
        _LOGGER,
        "Prompt document selection lookup resolved",
        **context,
    )


__all__ = [
    "PromptDocumentSelectionService",
    "emphasis_span_at_cursor",
]
