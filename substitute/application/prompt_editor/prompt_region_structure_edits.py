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

"""Classify and remap bounded edits against committed regional structure."""

from __future__ import annotations

from substitute.domain.prompt.region_structure_parser import REGION_SEPARATOR_TOKEN

from .prompt_document_views import (
    PromptRegionPartitionView,
    PromptRegionSeparatorView,
    PromptRegionStructureView,
)


def region_structure_edit_requires_rebuild(
    previous_text: str,
    next_text: str,
    structure: PromptRegionStructureView,
    *,
    start: int,
    end: int,
) -> bool:
    """Return whether one edit can change separator identity or line ownership."""

    if not 0 <= start <= end <= len(previous_text):
        return True
    replacement_length = len(next_text) - (len(previous_text) - (end - start))
    if replacement_length < 0:
        return True
    next_edit_end = start + replacement_length
    replacement_text = next_text[start:next_edit_end]

    for separator in structure.separators:
        protected_start = _line_break_start_before_separator(
            previous_text,
            separator.line_start,
        )
        protected_end = separator.line_end
        if _edit_touches_range(start, end, protected_start, protected_end):
            if _extends_content_line_before_separator(
                previous_text,
                separator,
                start=start,
                end=end,
                replacement_text=replacement_text,
            ):
                continue
            return True

    previous_candidates = _local_separator_starts(previous_text, start, end)
    next_candidates = _local_separator_starts(next_text, start, next_edit_end)
    remapped_previous_candidates = tuple(
        candidate
        if candidate < start
        else candidate + replacement_length - (end - start)
        for candidate in previous_candidates
    )
    return remapped_previous_candidates != next_candidates


def _extends_content_line_before_separator(
    previous_text: str,
    separator: PromptRegionSeparatorView,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> bool:
    """Return whether an insertion only extends content before the marker newline."""

    line_break_position = _line_break_start_before_separator(
        previous_text,
        separator.line_start,
    )
    return (
        start == end == line_break_position
        and line_break_position < separator.line_start
        and previous_text[line_break_position] in "\r\n"
        and "\r" not in replacement_text
        and "\n" not in replacement_text
    )


def _line_break_start_before_separator(text: str, line_start: int) -> int:
    """Return the start of the line ending immediately before a separator."""

    if line_start >= 2 and text[line_start - 2 : line_start] == "\r\n":
        return line_start - 2
    if line_start >= 1 and text[line_start - 1] in "\r\n":
        return line_start - 1
    return line_start


def remap_region_structure_after_edit(
    structure: PromptRegionStructureView,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> PromptRegionStructureView:
    """Shift committed regional structure after a topology-preserving edit."""

    delta = len(replacement_text) - (end - start)
    return PromptRegionStructureView(
        separators=tuple(
            PromptRegionSeparatorView(
                token_start=_shift_position(separator.token_start, start, end, delta),
                token_end=_shift_position(separator.token_end, start, end, delta),
                line_start=_shift_position(separator.line_start, start, end, delta),
                line_end=_shift_separator_line_end(
                    separator.line_end,
                    start,
                    end,
                    delta,
                ),
            )
            for separator in structure.separators
        ),
        partitions=tuple(
            PromptRegionPartitionView(
                index=partition.index,
                source_start=_shift_partition_start(
                    partition.source_start,
                    start,
                    end,
                    delta,
                ),
                source_end=_shift_partition_end(
                    partition.source_end,
                    start,
                    end,
                    delta,
                ),
                is_global=partition.is_global,
            )
            for partition in structure.partitions
        ),
    )


def rebuild_region_structure_after_edit(
    previous_text: str,
    next_text: str,
    structure: PromptRegionStructureView,
    *,
    start: int,
    end: int,
) -> PromptRegionStructureView:
    """Rebuild edit-local separator topology while shifting untouched separators."""

    replacement_length = _validated_replacement_length(
        previous_text,
        next_text,
        start=start,
        end=end,
    )
    delta = replacement_length - (end - start)
    separators: dict[int, PromptRegionSeparatorView] = {}
    for separator in structure.separators:
        protected_start = _line_break_start_before_separator(
            previous_text,
            separator.line_start,
        )
        protected_end = separator.line_end
        if _edit_touches_range(start, end, protected_start, protected_end):
            continue
        shifted = PromptRegionSeparatorView(
            token_start=_shift_position(separator.token_start, start, end, delta),
            token_end=_shift_position(separator.token_end, start, end, delta),
            line_start=_shift_position(separator.line_start, start, end, delta),
            line_end=_shift_position(separator.line_end, start, end, delta),
        )
        separators[shifted.token_start] = shifted

    next_edit_end = start + replacement_length
    for token_start in _local_separator_starts(next_text, start, next_edit_end):
        token_end = token_start + len(REGION_SEPARATOR_TOKEN)
        separators[token_start] = PromptRegionSeparatorView(
            token_start=token_start,
            token_end=token_end,
            line_start=token_start,
            line_end=_separator_line_end(next_text, token_end),
        )

    ordered_separators = tuple(
        separators[token_start] for token_start in sorted(separators)
    )
    return PromptRegionStructureView(
        separators=ordered_separators,
        partitions=_partitions_for_separators(
            ordered_separators,
            source_length=len(next_text),
        ),
    )


def _validated_replacement_length(
    previous_text: str,
    next_text: str,
    *,
    start: int,
    end: int,
) -> int:
    """Return replacement length after validating one exact contiguous edit."""

    if not 0 <= start <= end <= len(previous_text):
        raise ValueError("Source edit range is outside the previous prompt.")
    replacement_length = len(next_text) - (len(previous_text) - (end - start))
    if replacement_length < 0:
        raise ValueError("Next prompt cannot be produced by the supplied edit range.")
    next_edit_end = start + replacement_length
    if (
        previous_text[:start] != next_text[:start]
        or previous_text[end:] != next_text[next_edit_end:]
    ):
        raise ValueError("Prompt texts do not describe one contiguous source edit.")
    return replacement_length


def _separator_line_end(text: str, token_end: int) -> int:
    """Return the consumed source-line end for one canonical separator."""

    if text.startswith("\r\n", token_end):
        return token_end + 2
    if token_end < len(text) and text[token_end] in "\r\n":
        return token_end + 1
    return token_end


def _partitions_for_separators(
    separators: tuple[PromptRegionSeparatorView, ...],
    *,
    source_length: int,
) -> tuple[PromptRegionPartitionView, ...]:
    """Return global and regional partitions around ordered separators."""

    partitions: list[PromptRegionPartitionView] = []
    partition_start = 0
    for separator in separators:
        partitions.append(
            PromptRegionPartitionView(
                index=len(partitions),
                source_start=partition_start,
                source_end=separator.line_start,
                is_global=not partitions,
            )
        )
        partition_start = separator.line_end
    partitions.append(
        PromptRegionPartitionView(
            index=len(partitions),
            source_start=partition_start,
            source_end=source_length,
            is_global=not partitions,
        )
    )
    return tuple(partitions)


def _edit_touches_range(
    edit_start: int,
    edit_end: int,
    range_start: int,
    range_end: int,
) -> bool:
    """Return whether a replacement or insertion touches a protected range."""

    if edit_start == edit_end:
        return range_start <= edit_start < range_end
    return edit_start < range_end and edit_end > range_start


def _local_separator_starts(
    text: str, edit_start: int, edit_end: int
) -> tuple[int, ...]:
    """Find canonical separator candidates only within edit-adjacent context."""

    context_padding = len(REGION_SEPARATOR_TOKEN) + len("\r\n")
    context_start = max(0, edit_start - context_padding)
    context_end = min(len(text), edit_end + context_padding)
    candidates: list[int] = []
    search_start = context_start
    while search_start < context_end:
        marker_start = text.find(REGION_SEPARATOR_TOKEN, search_start, context_end)
        if marker_start < 0:
            break
        marker_end = marker_start + len(REGION_SEPARATOR_TOKEN)
        if (marker_start == 0 or text[marker_start - 1] in "\r\n") and (
            marker_end == len(text) or text[marker_end] in "\r\n"
        ):
            candidates.append(marker_start)
        search_start = marker_end
    return tuple(candidates)


def _shift_position(position: int, start: int, end: int, delta: int) -> int:
    """Shift a structural position known to sit outside the changed range."""

    if position < start:
        return position
    if position >= end:
        return position + delta
    raise ValueError("Topology-preserving edits must not overlap regional structure.")


def _shift_separator_line_end(
    position: int,
    start: int,
    end: int,
    delta: int,
) -> int:
    """Keep an insertion after a consumed separator line outside that line."""

    if start == end and position == start:
        return position
    return _shift_position(position, start, end, delta)


def _shift_partition_start(position: int, start: int, end: int, delta: int) -> int:
    """Keep an edited partition start stable while shifting later partitions."""

    if position <= start:
        return position
    if position >= end:
        return position + delta
    return start


def _shift_partition_end(position: int, start: int, end: int, delta: int) -> int:
    """Grow the edited partition end while shifting later partition ends."""

    if position < start:
        return position
    if position >= end:
        return position + delta
    raise ValueError("Topology-preserving edits must not cross a partition boundary.")


__all__ = [
    "rebuild_region_structure_after_edit",
    "region_structure_edit_requires_rebuild",
    "remap_region_structure_after_edit",
]
