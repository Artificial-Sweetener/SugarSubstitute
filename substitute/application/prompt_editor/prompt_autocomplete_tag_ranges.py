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

"""Resolve plain prompt-tag autocomplete ranges around the caret."""

from __future__ import annotations

from dataclasses import dataclass

from .prompt_autocomplete_queries import PromptAutocompleteFallbackQuery
from .prompt_document_selection_service import emphasis_span_at_cursor
from .prompt_document_views import PromptDocumentView, PromptSegmentView
from .prompt_text_ranges import (
    line_end_within_bounds,
    line_start_within_bounds,
    trim_horizontal_end,
    trim_horizontal_start,
)


@dataclass(frozen=True, slots=True)
class PromptAutocompleteTagRange:
    """Carry the authoritative plain-tag query and replacement range."""

    prefix: str
    replacement_start: int
    cursor_position: int
    active_tag_end: int
    fallback_query: PromptAutocompleteFallbackQuery | None


def autocomplete_tag_range_at_cursor(
    *,
    text: str,
    document_view: PromptDocumentView,
    segment: PromptSegmentView,
    cursor_position: int,
    minimum_prefix_length: int,
) -> PromptAutocompleteTagRange | None:
    """Return a bounded plain-tag autocomplete range for the caret position."""

    line_start = line_start_within_bounds(
        text,
        lower_bound=segment.selection_start,
        position=cursor_position,
    )
    line_end = line_end_within_bounds(
        text,
        position=cursor_position,
        upper_bound=segment.selection_end,
    )
    emphasis_span = emphasis_span_at_cursor(
        document_view,
        segment=segment,
        cursor_position=cursor_position,
    )
    if emphasis_span is None:
        tag_start = trim_horizontal_start(text, line_start, line_end)
        active_tag_end = max(
            cursor_position,
            trim_horizontal_end(text, tag_start, line_end),
        )
    else:
        if cursor_position < emphasis_span.content_start:
            return None
        if cursor_position > emphasis_span.content_end:
            return None
        tag_start = emphasis_span.content_start
        active_tag_end = emphasis_span.content_end

    if cursor_position < tag_start:
        return None

    prefix = text[tag_start:cursor_position]
    if len(prefix) < minimum_prefix_length:
        return None

    fallback_query = _autocomplete_suffix_fallback_query(
        text=text,
        prefix=prefix,
        prefix_start=tag_start,
        cursor_position=cursor_position,
        active_tag_end=active_tag_end,
        minimum_prefix_length=minimum_prefix_length,
    )
    return PromptAutocompleteTagRange(
        prefix=prefix,
        replacement_start=tag_start,
        cursor_position=cursor_position,
        active_tag_end=active_tag_end,
        fallback_query=fallback_query,
    )


def _autocomplete_suffix_fallback_query(
    *,
    text: str,
    prefix: str,
    prefix_start: int,
    cursor_position: int,
    active_tag_end: int,
    minimum_prefix_length: int,
) -> PromptAutocompleteFallbackQuery | None:
    """Return a last-token fallback query for no-comma prose-like prefixes."""

    suffix_start = max(prefix.rfind(" "), prefix.rfind("\t")) + 1
    if suffix_start <= 0:
        return None
    suffix = prefix[suffix_start:]
    if len(suffix) < minimum_prefix_length:
        return None
    return PromptAutocompleteFallbackQuery(
        prefix=suffix,
        word_start=prefix_start + suffix_start,
        word_end=cursor_position,
        active_tag_end=_autocomplete_local_token_end(
            text,
            cursor_position=cursor_position,
            upper_bound=active_tag_end,
        ),
    )


def _autocomplete_local_token_end(
    text: str,
    *,
    cursor_position: int,
    upper_bound: int,
) -> int:
    """Return the right edge of one whitespace-delimited local fallback token."""

    index = cursor_position
    while index < upper_bound and text[index] not in " \t,\r\n":
        index += 1
    return index


__all__ = [
    "PromptAutocompleteTagRange",
    "autocomplete_tag_range_at_cursor",
]
