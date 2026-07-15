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

"""Map domain prompt documents into application prompt document views."""

from __future__ import annotations

from substitute.domain.prompt import (
    EmphasisSpan,
    LoraSpan,
    PromptDocument,
    PromptReorderChip,
    PromptSegment,
    serialize_reorder_chip,
    SyntaxSpan,
    WildcardSpan,
    normalize_reorder_separator_text,
)

from .prompt_document_views import (
    PromptDocumentView,
    PromptEmphasisView,
    PromptLoraView,
    PromptReorderChipView,
    PromptSegmentView,
    PromptSyntaxSpanView,
    PromptWildcardView,
)


def prompt_document_view_from_domain(document: PromptDocument) -> PromptDocumentView:
    """Project one domain prompt document into the application snapshot."""

    return PromptDocumentView(
        source_text=document.source_text,
        segments=tuple(
            prompt_segment_view_from_domain(document, segment)
            for segment in document.segments
        ),
        emphasis_spans=tuple(
            _emphasis_view_from_domain(document, span)
            for span in document.emphasis_spans
        ),
        wildcard_spans=tuple(
            _wildcard_view_from_domain(span) for span in document.wildcard_spans
        ),
        lora_spans=tuple(
            _lora_view_from_domain(document, span) for span in document.lora_spans
        ),
        syntax_spans=tuple(
            _syntax_span_view_from_domain(span) for span in document.syntax_spans
        ),
        has_trailing_comma=document.has_trailing_comma,
    )


def prompt_segment_view_from_domain(
    document: PromptDocument,
    segment: PromptSegment,
) -> PromptSegmentView:
    """Convert one domain segment into the application-facing segment view."""

    separator_text_after = segment.separator_text(document.source_text)
    display_source_start, display_source_end = _display_source_bounds(segment)

    return PromptSegmentView(
        index=segment.index,
        text=segment.text,
        display_text=unescape_literal_parentheses_for_display(segment.display_text),
        display_source_start=display_source_start,
        display_source_end=display_source_end,
        selection_start=segment.visible_range.start,
        selection_end=segment.visible_range.end,
        separator_text_after=normalize_reorder_separator_text(separator_text_after),
        has_separator_after=segment.separator_range is not None,
    )


def prompt_reorder_chip_view_from_domain(
    document: PromptDocument,
    chip: PromptReorderChip,
) -> PromptReorderChipView:
    """Convert one domain reorder chip into the application-facing reorder view."""

    separator_text_after = chip.separator_text(document.source_text)
    display_source_start, display_source_end = _display_source_bounds_for_reorder_chip(
        chip
    )
    return PromptReorderChipView(
        index=chip.index,
        text=chip.text,
        serialized_text=serialize_reorder_chip(chip),
        display_text=unescape_literal_parentheses_for_display(chip.display_text),
        display_source_start=display_source_start,
        display_source_end=display_source_end,
        selection_start=chip.visible_range.start,
        selection_end=chip.visible_range.end,
        separator_text_after=normalize_reorder_separator_text(separator_text_after),
        has_separator_after=chip.separator_range is not None,
    )


def unescape_literal_parentheses_for_display(text: str) -> str:
    """Hide storage-only literal parenthesis escapes for user-facing display text."""

    return text.replace(r"\(", "(").replace(r"\)", ")")


def _display_source_bounds(segment: PromptSegment) -> tuple[int, int]:
    """Return the absolute source bounds for the stripped visible segment label."""

    leading_whitespace = len(segment.text) - len(segment.text.lstrip(" \t"))
    trailing_whitespace = len(segment.text) - len(segment.text.rstrip(" \t"))
    display_start = min(
        segment.content_range.end,
        segment.content_range.start + leading_whitespace,
    )
    display_end = max(display_start, segment.content_range.end - trailing_whitespace)
    return display_start, display_end


def _display_source_bounds_for_reorder_chip(
    chip: PromptReorderChip,
) -> tuple[int, int]:
    """Return the absolute source bounds for the stripped reorder chip label."""

    leading_whitespace = len(chip.text) - len(chip.text.lstrip(" \t"))
    trailing_whitespace = len(chip.text) - len(chip.text.rstrip(" \t"))
    display_start = min(
        chip.content_range.end,
        chip.content_range.start + leading_whitespace,
    )
    display_end = max(display_start, chip.content_range.end - trailing_whitespace)
    return display_start, display_end


def _emphasis_view_from_domain(
    document: PromptDocument,
    span: EmphasisSpan,
) -> PromptEmphasisView:
    """Convert one domain emphasis span into the application-facing span view."""

    return PromptEmphasisView(
        outer_start=span.outer_range.start,
        outer_end=span.outer_range.end,
        content_start=span.content_range.start,
        content_end=span.content_range.end,
        weight_start=span.weight_range.start,
        weight_end=span.weight_range.end,
        weight=span.weight,
        weight_text=span.weight_range.slice(document.source_text),
        depth=span.depth,
    )


def _syntax_span_view_from_domain(span: SyntaxSpan) -> PromptSyntaxSpanView:
    """Convert one domain syntax span into the application-facing span view."""

    return PromptSyntaxSpanView(
        kind=span.kind.value,
        start=span.source_range.start,
        end=span.source_range.end,
        depth=span.depth,
    )


def _wildcard_view_from_domain(span: WildcardSpan) -> PromptWildcardView:
    """Convert one domain wildcard span into the application-facing span view."""

    return PromptWildcardView(
        outer_start=span.outer_range.start,
        outer_end=span.outer_range.end,
        content_start=span.content_range.start,
        content_end=span.content_range.end,
        wildcard_form=span.wildcard_form.value,
        identifier=span.identifier,
        csv_column=span.csv_column,
        tag=span.tag,
        depth=span.depth,
    )


def _lora_view_from_domain(
    document: PromptDocument,
    span: LoraSpan,
) -> PromptLoraView:
    """Convert one domain LoRA span into an application-facing span view."""

    return PromptLoraView(
        outer_start=span.outer_range.start,
        outer_end=span.outer_range.end,
        name_start=span.name_range.start,
        name_end=span.name_range.end,
        first_weight_start=span.first_weight_range.start,
        first_weight_end=span.first_weight_range.end,
        first_weight=span.first_weight,
        first_weight_text=span.first_weight_range.slice(document.source_text),
        second_weight_start=(
            None if span.second_weight_range is None else span.second_weight_range.start
        ),
        second_weight_end=(
            None if span.second_weight_range is None else span.second_weight_range.end
        ),
        second_weight=span.second_weight,
        second_weight_text=(
            None
            if span.second_weight_range is None
            else span.second_weight_range.slice(document.source_text)
        ),
        block_weights_start=(
            None if span.block_weights_range is None else span.block_weights_range.start
        ),
        block_weights_end=(
            None if span.block_weights_range is None else span.block_weights_range.end
        ),
        prompt_name=span.name_range.slice(document.source_text),
        depth=span.depth,
    )


__all__ = [
    "prompt_document_view_from_domain",
    "prompt_reorder_chip_view_from_domain",
    "prompt_segment_view_from_domain",
    "unescape_literal_parentheses_for_display",
]
