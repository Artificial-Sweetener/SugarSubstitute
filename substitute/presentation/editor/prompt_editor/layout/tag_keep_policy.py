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

"""Own short comma-tag grouping policy for canonical and incremental layout."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import PromptDocumentView

_MAX_KEPT_SEGMENT_WORDS = 3


def tag_keep_source_ranges(
    prompt_document_view: PromptDocumentView,
    *,
    source_limit: int | None = None,
) -> tuple[tuple[int, int], ...]:
    """Return parsed source ranges for short comma-delimited tags kept as a unit."""

    segment_count = len(prompt_document_view.segments)
    ranges: list[tuple[int, int]] = []
    for segment in prompt_document_view.segments:
        if source_limit is not None and segment.selection_start > source_limit:
            break
        if not _segment_is_comma_delimited(segment, segment_count=segment_count):
            continue
        if _segment_word_count(segment.display_text) > _MAX_KEPT_SEGMENT_WORDS:
            continue
        source_start = segment.selection_start
        source_end = segment.selection_end
        if segment.has_separator_after and segment.separator_text_after.startswith(","):
            source_end += 1
        if source_end > source_start and (source_start, source_end) not in ranges:
            ranges.append((source_start, source_end))
    return tuple(ranges)


def tag_keep_source_ranges_for_layout(
    prompt_document_view: PromptDocumentView,
    *,
    source_start: int = 0,
    source_limit: int | None = None,
) -> tuple[tuple[int, int], ...]:
    """Return parsed and inferred kept-tag ranges for authoritative layout."""

    return _source_text_tag_keep_ranges(
        prompt_document_view.source_text,
        source_start=source_start,
        source_limit=source_limit,
    )


def tag_keep_source_ranges_in_source_line(
    source_text: str,
    *,
    line_start: int,
    line_end: int,
) -> tuple[tuple[int, int], ...]:
    """Return inferred kept-tag ranges in one hard source line."""

    bounded_line_start = max(0, min(line_start, len(source_text)))
    bounded_line_end = max(bounded_line_start, min(line_end, len(source_text)))
    return _source_text_line_tag_keep_ranges(
        source_text,
        line_start=bounded_line_start,
        line_end=bounded_line_end,
    )


def tag_keep_source_range_at_position(
    source_text: str,
    source_position: int,
) -> tuple[int, int] | None:
    """Return the short comma-tag range containing a source position."""

    if not source_text or "," not in source_text:
        return None
    anchor = max(0, min(source_position, len(source_text) - 1))
    line_start = source_text.rfind("\n", 0, anchor + 1) + 1
    line_end = source_text.find("\n", anchor)
    if line_end < 0:
        line_end = len(source_text)
    previous_comma = source_text.rfind(",", line_start, anchor + 1)
    next_comma = source_text.find(",", anchor, line_end)
    if previous_comma == anchor:
        next_comma = previous_comma
        previous_comma = source_text.rfind(",", line_start, previous_comma)
    if previous_comma < 0 and next_comma < 0:
        return None
    segment_start = line_start if previous_comma < 0 else previous_comma + 1
    segment_end = line_end if next_comma < 0 else next_comma
    selection_start = _skip_horizontal_whitespace_forward(
        source_text,
        segment_start,
        limit=segment_end,
    )
    selection_end = _skip_horizontal_whitespace_backward(
        source_text,
        segment_end,
        lower_limit=selection_start,
    )
    if selection_end <= selection_start:
        return None
    if _segment_word_count(source_text[selection_start:selection_end]) > 3:
        return None
    range_end = selection_end if next_comma < 0 else next_comma + 1
    return (selection_start, range_end)


def _source_text_tag_keep_ranges(
    source_text: str,
    *,
    source_start: int = 0,
    source_limit: int | None = None,
) -> tuple[tuple[int, int], ...]:
    """Infer short comma-delimited tag ranges directly from source text."""

    ranges: list[tuple[int, int]] = []
    bounded_source_start = max(0, min(source_start, len(source_text)))
    line_start = source_text.rfind("\n", 0, bounded_source_start) + 1
    scan_end = (
        len(source_text)
        if source_limit is None
        else min(len(source_text), max(0, source_limit))
    )
    while line_start <= scan_end:
        line_end = source_text.find("\n", line_start, scan_end)
        if line_end < 0:
            line_end = scan_end
        ranges.extend(
            _source_text_line_tag_keep_ranges(
                source_text,
                line_start=line_start,
                line_end=line_end,
                include_terminal_segment=(
                    line_end < scan_end
                    or scan_end == len(source_text)
                    or source_text[scan_end] == "\n"
                ),
            )
        )
        if line_end == scan_end:
            break
        line_start = line_end + 1
    return tuple(ranges)


def _source_text_line_tag_keep_ranges(
    source_text: str,
    *,
    line_start: int,
    line_end: int,
    include_terminal_segment: bool = True,
) -> tuple[tuple[int, int], ...]:
    """Infer short comma-tag ranges inside one hard source line."""

    line_text = source_text[line_start:line_end]
    if "," not in line_text:
        return ()

    ranges: list[tuple[int, int]] = []
    segment_start = line_start
    while segment_start <= line_end:
        comma_index = source_text.find(",", segment_start, line_end)
        segment_end = line_end if comma_index < 0 else comma_index
        selection_start = _skip_horizontal_whitespace_forward(
            source_text,
            segment_start,
            limit=segment_end,
        )
        selection_end = _skip_horizontal_whitespace_backward(
            source_text,
            segment_end,
            lower_limit=selection_start,
        )
        if (
            selection_end > selection_start
            and (comma_index >= 0 or include_terminal_segment)
            and _segment_word_count(source_text[selection_start:selection_end])
            <= _MAX_KEPT_SEGMENT_WORDS
        ):
            range_end = selection_end
            if comma_index >= 0:
                range_end = comma_index + 1
            ranges.append((selection_start, range_end))
        if comma_index < 0:
            break
        segment_start = comma_index + 1
    return tuple(ranges)


def _skip_horizontal_whitespace_forward(
    text: str,
    start: int,
    *,
    limit: int,
) -> int:
    """Return the first non-horizontal-whitespace position before limit."""

    index = start
    while index < limit and text[index] in {" ", "\t"}:
        index += 1
    return index


def _skip_horizontal_whitespace_backward(
    text: str,
    end: int,
    *,
    lower_limit: int,
) -> int:
    """Return the first non-horizontal-whitespace boundary after lower_limit."""

    index = end
    while index > lower_limit and text[index - 1] in {" ", "\t"}:
        index -= 1
    return index


def _segment_is_comma_delimited(
    segment: object,
    *,
    segment_count: int,
) -> bool:
    """Return whether one parsed segment participates in comma segmentation."""

    has_separator_after = bool(getattr(segment, "has_separator_after", False))
    return has_separator_after or segment_count > 1


def _segment_word_count(display_text: str) -> int:
    """Return the whitespace-delimited word count for one segment label."""

    return len(display_text.split())


__all__ = [
    "tag_keep_source_range_at_position",
    "tag_keep_source_ranges",
    "tag_keep_source_ranges_for_layout",
    "tag_keep_source_ranges_in_source_line",
]
