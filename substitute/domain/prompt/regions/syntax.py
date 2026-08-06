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

"""Own the canonical plain and named regional-separator grammar."""

from __future__ import annotations

from dataclasses import dataclass

REGION_SEPARATOR_TOKEN = "[SEP]"
REGION_SEPARATOR_PREFIX = "[SEP"


@dataclass(frozen=True, slots=True)
class PromptRegionSeparatorSyntax:
    """Describe one valid separator token independently from line placement."""

    token_start: int
    token_end: int
    name_start: int | None = None
    name_end: int | None = None
    name: str | None = None

    @property
    def token_length(self) -> int:
        """Return the complete authored token length."""

        return self.token_end - self.token_start


def region_separator_at(
    text: str,
    index: int,
    *,
    require_standalone: bool = False,
) -> PromptRegionSeparatorSyntax | None:
    """Parse a plain or named separator beginning at one source position."""

    if index < 0 or not text.startswith(REGION_SEPARATOR_PREFIX, index):
        return None
    suffix_start = index + len(REGION_SEPARATOR_PREFIX)
    if suffix_start >= len(text):
        return None
    suffix = text[suffix_start]
    if suffix == "]":
        match = PromptRegionSeparatorSyntax(index, suffix_start + 1)
    elif suffix == "|":
        name_start = suffix_start + 1
        token_end = _named_separator_end(text, name_start)
        if token_end is None or token_end == name_start + 1:
            return None
        name_end = token_end - 1
        match = PromptRegionSeparatorSyntax(
            token_start=index,
            token_end=token_end,
            name_start=name_start,
            name_end=name_end,
            name=text[name_start:name_end],
        )
    else:
        return None
    if require_standalone and not _is_standalone(text, match):
        return None
    return match


def region_separator_ending_at(
    text: str,
    token_end: int,
) -> PromptRegionSeparatorSyntax | None:
    """Return a valid separator ending at one boundary on its current line."""

    if token_end <= 0 or token_end > len(text) or text[token_end - 1] != "]":
        return None
    line_start = _line_start(text, token_end - 1)
    marker_start = text.rfind(REGION_SEPARATOR_PREFIX, line_start, token_end)
    if marker_start < 0:
        return None
    match = region_separator_at(text, marker_start)
    return match if match is not None and match.token_end == token_end else None


def region_separators_in_range(
    text: str,
    start: int,
    end: int,
    *,
    require_standalone: bool,
) -> tuple[PromptRegionSeparatorSyntax, ...]:
    """Return valid separators beginning inside one bounded source range."""

    matches: list[PromptRegionSeparatorSyntax] = []
    search_start = max(0, start)
    search_end = min(len(text), end)
    while search_start < search_end:
        marker_start = text.find(REGION_SEPARATOR_PREFIX, search_start, search_end)
        if marker_start < 0:
            break
        match = region_separator_at(
            text,
            marker_start,
            require_standalone=require_standalone,
        )
        if match is not None and match.token_end <= end:
            matches.append(match)
            search_start = match.token_end
        else:
            search_start = marker_start + len(REGION_SEPARATOR_PREFIX)
    return tuple(matches)


def separator_line_window(text: str, start: int, end: int) -> tuple[int, int]:
    """Return complete source lines surrounding an edited range."""

    bounded_start = min(max(0, start), len(text))
    bounded_end = min(max(bounded_start, end), len(text))
    window_start = _line_start(text, bounded_start)
    line_break = _next_line_break(text, bounded_end)
    if line_break is None:
        return window_start, len(text)
    window_end = line_break + (2 if text.startswith("\r\n", line_break) else 1)
    next_break = _next_line_break(text, window_end)
    return window_start, len(text) if next_break is None else next_break


def _named_separator_end(text: str, name_start: int) -> int | None:
    """Return the closing-bracket boundary without crossing a source line."""

    index = name_start
    while index < len(text):
        character = text[index]
        if character == "]":
            return index + 1
        if character in "\r\n":
            return None
        index += 1
    return None


def _is_standalone(text: str, match: PromptRegionSeparatorSyntax) -> bool:
    """Return whether a token occupies its complete source line."""

    return (match.token_start == 0 or text[match.token_start - 1] in "\r\n") and (
        match.token_end == len(text) or text[match.token_end] in "\r\n"
    )


def _line_start(text: str, position: int) -> int:
    """Return the start of the source line containing one position."""

    carriage = text.rfind("\r", 0, position)
    line_feed = text.rfind("\n", 0, position)
    return max(carriage, line_feed) + 1


def _next_line_break(text: str, position: int) -> int | None:
    """Return the next CR or LF boundary after one position."""

    candidates = tuple(
        boundary
        for boundary in (text.find("\r", position), text.find("\n", position))
        if boundary >= 0
    )
    return min(candidates) if candidates else None


__all__ = [
    "PromptRegionSeparatorSyntax",
    "REGION_SEPARATOR_PREFIX",
    "REGION_SEPARATOR_TOKEN",
    "region_separator_at",
    "region_separator_ending_at",
    "region_separators_in_range",
    "separator_line_window",
]
