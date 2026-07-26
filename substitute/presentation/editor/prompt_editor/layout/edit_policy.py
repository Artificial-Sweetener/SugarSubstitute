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

"""Classify bounded layout edits and decide when canonical policy is required."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.application.prompt_editor.document.views import PromptDocumentView

from .tag_keep_policy import (
    tag_keep_source_range_at_position,
    tag_keep_source_ranges_in_source_line,
)
from .models import PromptProjectionLineSnapshot


def line_index_for_plain_edit(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> int | None:
    """Return the visual line that owns one plain source edit."""

    if replacement_text:
        candidate_index: int | None = None
        for line_index, line in enumerate(lines):
            if line.source_start <= edit_start <= line.source_end:
                candidate_index = line_index
                if edit_start < line.source_end:
                    break
        return candidate_index
    for line_index, line in enumerate(lines):
        if line.source_start <= edit_start and edit_end <= line.source_end:
            return line_index
    return None


def line_index_for_hard_line_insert(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    edit_start: int,
) -> int | None:
    """Return the visual line that can be split by an inserted hard break."""

    candidate_index: int | None = None
    for line_index, line in enumerate(lines):
        if line.source_content_start <= edit_start <= line.source_content_end:
            candidate_index = line_index
            if edit_start < line.source_content_end:
                break
    return candidate_index


def line_index_for_hard_line_delete(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    edit_start: int,
) -> int | None:
    """Return the line whose hard break is being deleted."""

    for line_index, line in enumerate(lines):
        if (
            line.line_break_start == edit_start
            and line.line_break_end == edit_start + 1
        ):
            return line_index
    return None


def plain_edit_requires_tag_keep_reflow(
    prompt_document_view: PromptDocumentView,
    *,
    previous_source_text: str,
    lines: Sequence[PromptProjectionLineSnapshot],
    line: PromptProjectionLineSnapshot,
    line_index: int,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    source_delta: int,
    width_delta: float,
    content_right: float,
    tag_keep_ranges_changed: bool | None = None,
) -> bool:
    """Return whether a kept tag edit needs authoritative line-group layout."""

    expected_next_text = (
        previous_source_text[:edit_start]
        + replacement_text
        + previous_source_text[edit_end:]
    )
    if expected_next_text != prompt_document_view.source_text:
        return True

    next_line_content_end = line.source_content_end + source_delta
    if tag_keep_ranges_changed is None:
        tag_keep_ranges_changed = plain_edit_changes_local_tag_keep_ranges(
            previous_source_text,
            prompt_document_view.source_text,
            edit_start=edit_start,
            edit_end=edit_end,
            replacement_text=replacement_text,
        )
    if tag_keep_ranges_changed and not changed_tag_keep_ranges_are_local_to_line(
        previous_source_text,
        prompt_document_view.source_text,
        line=line,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
        source_delta=source_delta,
    ):
        return True
    touched_range = tag_keep_range_for_plain_edit(
        prompt_document_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    )
    if touched_range is None:
        return tag_keep_ranges_changed
    range_start, range_end = touched_range
    if range_start < line.source_content_start or range_end > next_line_content_end:
        return True
    if (
        line_index > 0
        and not replacement_text
        and range_start == line.source_start
        and edit_start <= range_start
    ):
        return True
    if line.rect.right() + width_delta > content_right + 0.01:
        return True
    return False


def changed_tag_keep_ranges_are_local_to_line(
    previous_source_text: str,
    next_source_text: str,
    *,
    line: PromptProjectionLineSnapshot,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    source_delta: int,
) -> bool:
    """Return whether changed comma keep groups stay within one visual line."""

    previous_line_start, previous_line_end = hard_line_bounds_for_source_edit(
        previous_source_text,
        edit_start=edit_start,
        edit_end=edit_end,
    )
    next_line_start, next_line_end = hard_line_bounds_for_source_edit(
        next_source_text,
        edit_start=edit_start,
        edit_end=edit_start + len(replacement_text),
    )
    previous_ranges = tag_keep_source_ranges_in_source_line(
        previous_source_text,
        line_start=previous_line_start,
        line_end=previous_line_end,
    )
    remapped_previous_ranges = tuple(
        remap_tag_keep_range_for_plain_edit(
            source_start,
            source_end,
            edit_start=edit_start,
            edit_end=edit_end,
            source_delta=source_delta,
        )
        for source_start, source_end in previous_ranges
    )
    next_ranges = tag_keep_source_ranges_in_source_line(
        next_source_text,
        line_start=next_line_start,
        line_end=next_line_end,
    )
    if remapped_previous_ranges == next_ranges:
        return True
    changed_ranges = frozenset(remapped_previous_ranges) ^ frozenset(next_ranges)
    if not changed_ranges:
        return True
    next_line_content_start = line.source_content_start
    next_line_content_end = line.source_content_end + source_delta
    return all(
        next_line_content_start <= range_start <= range_end <= next_line_content_end
        for range_start, range_end in changed_ranges
    )


def plain_edit_changes_local_tag_keep_ranges(
    previous_source_text: str,
    next_source_text: str,
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> bool:
    """Return whether a plain edit changes its local tag keep range."""

    deleted_text = previous_source_text[edit_start:edit_end]
    if (
        edit_start < 0
        or edit_end < edit_start
        or edit_end > len(previous_source_text)
        or previous_source_text[:edit_start]
        + replacement_text
        + previous_source_text[edit_end:]
        != next_source_text
    ):
        return True

    source_delta = len(replacement_text) - (edit_end - edit_start)
    previous_line_start, previous_line_end = hard_line_bounds_for_source_edit(
        previous_source_text,
        edit_start=edit_start,
        edit_end=edit_end,
    )
    next_line_start, next_line_end = hard_line_bounds_for_source_edit(
        next_source_text,
        edit_start=edit_start,
        edit_end=edit_start + len(replacement_text),
    )
    previous_line_has_comma = (
        previous_source_text.find(",", previous_line_start, previous_line_end) >= 0
    )
    next_line_has_comma = (
        next_source_text.find(",", next_line_start, next_line_end) >= 0
    )
    if not previous_line_has_comma and not next_line_has_comma:
        return False

    if "," not in replacement_text and "," not in deleted_text:
        previous_anchor = min(edit_start, len(previous_source_text))
        next_anchor = min(
            edit_start + len(replacement_text),
            len(next_source_text),
        )
        previous_range = tag_keep_source_range_at_position(
            previous_source_text,
            previous_anchor,
        )
        next_range = tag_keep_source_range_at_position(
            next_source_text,
            next_anchor,
        )
        if previous_range is None and source_segment_is_empty_at_position(
            previous_source_text,
            previous_anchor,
        ):
            return False
        if next_range is None and source_segment_is_empty_at_position(
            next_source_text,
            next_anchor,
        ):
            return False
        return (previous_range is None) != (next_range is None)

    previous_ranges = tag_keep_source_ranges_in_source_line(
        previous_source_text,
        line_start=previous_line_start,
        line_end=previous_line_end,
    )
    remapped_previous_ranges = tuple(
        remap_tag_keep_range_for_plain_edit(
            source_start,
            source_end,
            edit_start=edit_start,
            edit_end=edit_end,
            source_delta=source_delta,
        )
        for source_start, source_end in previous_ranges
    )
    next_ranges = tag_keep_source_ranges_in_source_line(
        next_source_text,
        line_start=next_line_start,
        line_end=next_line_end,
    )
    return remapped_previous_ranges != next_ranges


def source_segment_is_empty_at_position(
    source_text: str,
    source_position: int,
) -> bool:
    """Return whether one position belongs to an empty comma-delimited segment."""

    bounded_position = max(0, min(source_position, len(source_text)))
    line_start = source_text.rfind("\n", 0, bounded_position) + 1
    line_end = source_text.find("\n", bounded_position)
    if line_end < 0:
        line_end = len(source_text)
    previous_comma = source_text.rfind(",", line_start, bounded_position)
    next_comma = source_text.find(",", bounded_position, line_end)
    segment_start = line_start if previous_comma < 0 else previous_comma + 1
    segment_end = line_end if next_comma < 0 else next_comma
    return not source_text[segment_start:segment_end].strip()


def hard_line_bounds_for_source_edit(
    source_text: str,
    *,
    edit_start: int,
    edit_end: int,
) -> tuple[int, int]:
    """Return the hard source-line bounds around one edit range."""

    anchor_start = max(0, min(edit_start, len(source_text)))
    anchor_end = max(anchor_start, min(edit_end, len(source_text)))
    line_start = source_text.rfind("\n", 0, anchor_start) + 1
    line_end_search_start = max(anchor_start, anchor_end - 1)
    line_end = source_text.find("\n", line_end_search_start)
    if line_end < 0:
        line_end = len(source_text)
    return line_start, line_end


def remap_tag_keep_range_for_plain_edit(
    source_start: int,
    source_end: int,
    *,
    edit_start: int,
    edit_end: int,
    source_delta: int,
) -> tuple[int, int]:
    """Return one old tag-keep range in post-edit source coordinates."""

    if source_end <= edit_start:
        return source_start, source_end
    if source_start >= edit_end:
        return source_start + source_delta, source_end + source_delta
    return source_start, max(source_start, source_end + source_delta)


def tag_keep_range_for_plain_edit(
    prompt_document_view: PromptDocumentView,
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> tuple[int, int] | None:
    """Return the edited kept-tag range using only local source context."""

    anchor = edit_start if replacement_text else max(0, edit_start - 1)
    candidate_range = tag_keep_source_range_at_position(
        prompt_document_view.source_text,
        anchor,
    )
    if candidate_range is None:
        return None
    range_start, range_end = candidate_range
    if not edit_touches_source_range(
        range_start=range_start,
        range_end=range_end,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    ):
        return None
    return candidate_range


def edit_touches_source_range(
    *,
    range_start: int,
    range_end: int,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> bool:
    """Return whether a source edit touches one half-open source range."""

    if replacement_text:
        return range_start <= edit_start <= range_end
    return edit_start < range_end and range_start < edit_end


def plain_edit_touches_visual_word_wrap_boundary(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    dirty_line_index: int,
    line: PromptProjectionLineSnapshot,
    next_source_text: str,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
    source_delta: int,
) -> bool:
    """Return whether an edit needs the full word-wrap policy to decide layout."""

    word_span = word_span_for_plain_source_edit(
        next_source_text,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    )
    if word_span is None:
        return False
    word_start, word_end = word_span
    next_line_content_start = line.source_content_start
    next_line_content_end = line.source_content_end + source_delta
    if word_start < next_line_content_start or word_end > next_line_content_end:
        return True
    del lines, dirty_line_index
    return False


def word_span_for_plain_source_edit(
    text: str,
    *,
    edit_start: int,
    edit_end: int,
    replacement_text: str,
) -> tuple[int, int] | None:
    """Return the source word affected by one plain edit when present."""

    if not text:
        return None
    if replacement_text:
        anchor = max(0, min(len(text) - 1, edit_start + len(replacement_text) - 1))
    else:
        anchor = max(0, min(len(text) - 1, edit_start))
        if not is_incremental_word_character(text[anchor]) and anchor > 0:
            anchor -= 1
    if not is_incremental_word_character(text[anchor]):
        return None
    word_start = anchor
    while word_start > 0 and is_incremental_word_character(text[word_start - 1]):
        word_start -= 1
    word_end = anchor + 1
    while word_end < len(text) and is_incremental_word_character(text[word_end]):
        word_end += 1
    return (word_start, word_end)


def is_incremental_word_character(character: str) -> bool:
    """Return whether a character participates in word-integrity wrapping."""

    return character.isalnum() or character in {"_", "-", "."}


__all__ = [
    "changed_tag_keep_ranges_are_local_to_line",
    "edit_touches_source_range",
    "hard_line_bounds_for_source_edit",
    "is_incremental_word_character",
    "line_index_for_hard_line_delete",
    "line_index_for_hard_line_insert",
    "line_index_for_plain_edit",
    "plain_edit_changes_local_tag_keep_ranges",
    "plain_edit_requires_tag_keep_reflow",
    "plain_edit_touches_visual_word_wrap_boundary",
    "remap_tag_keep_range_for_plain_edit",
    "source_segment_is_empty_at_position",
    "tag_keep_range_for_plain_edit",
    "word_span_for_plain_source_edit",
]
