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

"""Normalize authored regional separators with exact boundary remapping."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.prompt.regions.syntax import (
    PromptRegionSeparatorSyntax,
    region_separator_at,
    region_separator_ending_at,
    region_separators_in_range,
    separator_line_window,
)
from substitute.domain.prompt.document.structural_scan import (
    is_escaped_prompt_character,
)

_LINE_ENDING_CONTEXT_LIMIT = 512


@dataclass(frozen=True, slots=True)
class PromptRegionSeparatorNormalization:
    """Describe separator-normalized source and every original boundary mapping."""

    text: str
    boundary_positions: tuple[int, ...]


def normalize_typed_region_separator(
    text: str,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> PromptRegionSeparatorNormalization:
    """Normalize only the separator completed by one closing-bracket edit."""

    if replacement_text != "]" or end - start != 1:
        return _identity_normalization(text)
    match = region_separator_ending_at(text, end)
    if match is None:
        return _identity_normalization(text)
    if is_escaped_prompt_character(text, match.token_start):
        return _identity_normalization(text)
    normalization = _normalize_separators(
        text,
        (match,),
        ensure_trailing_line=True,
    )
    return _map_marker_completion_after_line_ending(
        normalization,
        original_text=text,
        marker_end=match.token_end,
    )


def normalize_typed_region_separator_after_deletion(
    text: str,
    *,
    position: int,
) -> PromptRegionSeparatorNormalization:
    """Restore line boundaries when one deletion leaves a complete marker inline."""

    window_start, window_end = separator_line_window(text, position, position)
    matches = tuple(
        match
        for match in region_separators_in_range(
            text,
            window_start,
            window_end,
            require_standalone=False,
        )
        if not is_escaped_prompt_character(text, match.token_start)
    )
    normalization = _normalize_separators(
        text,
        matches,
        ensure_trailing_line=False,
    )
    match_at_position = region_separator_at(text, position)
    if (
        match_at_position is not None
        and position > 0
        and text[position - 1] not in "\r\n"
    ):
        boundary_positions = list(normalization.boundary_positions)
        boundary_positions[position] = position
        return PromptRegionSeparatorNormalization(
            text=normalization.text,
            boundary_positions=tuple(boundary_positions),
        )
    return normalization


def normalize_empty_region_insertion(
    text: str,
    *,
    start: int,
    end: int,
) -> PromptRegionSeparatorNormalization:
    """Keep inserted content on its own line between adjacent separators."""

    if not 0 <= start < end <= len(text):
        return _identity_normalization(text)
    line_ending = _preceding_separator_line_ending(text, start)
    if line_ending is None or not _canonical_separator_starts_at(text, end):
        return _identity_normalization(text)
    normalized_text = f"{text[:end]}{line_ending}{text[end:]}"
    return PromptRegionSeparatorNormalization(
        text=normalized_text,
        boundary_positions=tuple(
            position if position <= end else position + len(line_ending)
            for position in range(len(text) + 1)
        ),
    )


def normalize_pasted_region_separators(
    text: str,
    *,
    start: int,
    end: int,
) -> PromptRegionSeparatorNormalization:
    """Normalize exact unescaped separators fully contained by one pasted range."""

    if start < 0 or end < start or end > len(text):
        raise ValueError("Prompt separator normalization range is outside source text.")
    matches = tuple(
        match
        for match in region_separators_in_range(
            text,
            start,
            end,
            require_standalone=False,
        )
        if not is_escaped_prompt_character(text, match.token_start)
    )
    return _normalize_separators(
        text,
        matches,
        ensure_trailing_line=False,
    )


def _preceding_separator_line_ending(text: str, position: int) -> str | None:
    """Return the line ending after a canonical separator before a position."""

    for line_ending in ("\r\n", "\n", "\r"):
        token_end = position - len(line_ending)
        if token_end < 0:
            continue
        line_start = _source_line_start(text, token_end)
        match = region_separator_at(text, line_start, require_standalone=True)
        if match is None or match.token_end != token_end:
            continue
        return line_ending
    return None


def _canonical_separator_starts_at(text: str, position: int) -> bool:
    """Return whether one canonical separator line starts at a source position."""

    match = region_separator_at(text, position)
    return (
        match is not None
        and (match.token_end == len(text) or text[match.token_end] in "\r\n")
        and not is_escaped_prompt_character(text, position)
    )


def _normalize_separators(
    text: str,
    matches: tuple[PromptRegionSeparatorSyntax, ...],
    *,
    ensure_trailing_line: bool,
) -> PromptRegionSeparatorNormalization:
    """Insert the minimum line endings needed around ordered exact markers."""

    insertions: dict[int, str] = {}
    leading_boundaries: set[int] = set()
    trailing_boundaries: set[int] = set()
    for match in matches:
        marker_start = match.token_start
        marker_end = match.token_end
        line_ending = _preferred_line_ending(text, marker_start, marker_end)
        if marker_start > 0 and text[marker_start - 1] not in "\r\n":
            insertions.setdefault(marker_start, line_ending)
            leading_boundaries.add(marker_start)
        if marker_end == len(text) and ensure_trailing_line:
            insertions.setdefault(marker_end, line_ending)
            trailing_boundaries.add(marker_end)
        elif marker_end < len(text) and text[marker_end] not in "\r\n":
            insertions.setdefault(marker_end, line_ending)
            trailing_boundaries.add(marker_end)
    if not insertions:
        return _identity_normalization(text)

    output: list[str] = []
    boundary_positions: list[int] = [0] * (len(text) + 1)
    target_position = 0
    for source_position in range(len(text) + 1):
        insertion = insertions.get(source_position)
        map_after_insertion = (
            source_position in leading_boundaries
            or source_position in trailing_boundaries
        )
        if insertion is not None and not map_after_insertion:
            boundary_positions[source_position] = target_position
        if insertion is not None:
            output.append(insertion)
            target_position += len(insertion)
        if insertion is None or map_after_insertion:
            boundary_positions[source_position] = target_position
        if source_position < len(text):
            output.append(text[source_position])
            target_position += 1
    return PromptRegionSeparatorNormalization(
        text="".join(output),
        boundary_positions=tuple(boundary_positions),
    )


def _map_marker_completion_after_line_ending(
    normalization: PromptRegionSeparatorNormalization,
    *,
    original_text: str,
    marker_end: int,
) -> PromptRegionSeparatorNormalization:
    """Place a completed marker's caret on its following regional input line."""

    line_end = marker_end
    if original_text.startswith("\r\n", marker_end):
        line_end += 2
    elif marker_end < len(original_text) and original_text[marker_end] in "\r\n":
        line_end += 1
    target_position = normalization.boundary_positions[line_end]
    boundary_positions = list(normalization.boundary_positions)
    for source_position in range(marker_end, line_end + 1):
        boundary_positions[source_position] = target_position
    return PromptRegionSeparatorNormalization(
        text=normalization.text,
        boundary_positions=tuple(boundary_positions),
    )


def _source_line_start(text: str, line_end: int) -> int:
    """Return the source-line start preceding one exclusive line end."""

    carriage = text.rfind("\r", 0, line_end)
    line_feed = text.rfind("\n", 0, line_end)
    return max(carriage, line_feed) + 1


def _preferred_line_ending(text: str, marker_start: int, marker_end: int) -> str:
    """Return the nearest line-ending convention from bounded marker context."""

    context_start = max(0, marker_start - _LINE_ENDING_CONTEXT_LIMIT)
    context_end = min(len(text), marker_end + _LINE_ENDING_CONTEXT_LIMIT)
    context = text[context_start:context_end]
    marker_offset = marker_start - context_start
    candidates: list[tuple[int, str]] = []
    offset = 0
    while offset < len(context):
        character = context[offset]
        if character == "\r":
            line_ending = (
                "\r\n"
                if offset + 1 < len(context) and context[offset + 1] == "\n"
                else "\r"
            )
            candidates.append((abs(offset - marker_offset), line_ending))
            offset += len(line_ending)
            continue
        if character == "\n":
            candidates.append((abs(offset - marker_offset), "\n"))
        offset += 1
    if not candidates:
        return "\n"
    return min(candidates, key=lambda candidate: candidate[0])[1]


def _identity_normalization(text: str) -> PromptRegionSeparatorNormalization:
    """Return unchanged source with its identity boundary mapping."""

    return PromptRegionSeparatorNormalization(
        text=text,
        boundary_positions=tuple(range(len(text) + 1)),
    )


__all__ = [
    "PromptRegionSeparatorNormalization",
    "normalize_empty_region_insertion",
    "normalize_pasted_region_separators",
    "normalize_typed_region_separator",
]
