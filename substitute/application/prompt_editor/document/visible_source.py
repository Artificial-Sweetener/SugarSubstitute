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

"""Map stored prompt source to visible text and its exact source boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from bisect import bisect_left, bisect_right
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptVisibleSource:
    """Keep a display string paired with its source-boundary positions."""

    display_text: str
    source_positions: Sequence[int]


def visible_indices_for_source_range(
    source_positions: Sequence[int], start: int, end: int
) -> tuple[int, int]:
    """Include each visible glyph touched by a half-open source range."""

    if not source_positions or end <= start:
        return (0, 0)
    first = max(0, bisect_right(source_positions, start) - 1)
    last = min(len(source_positions) - 1, bisect_left(source_positions, end))
    return (first, max(first, last))


def map_prompt_source_for_display(
    source_text: str,
    *,
    source_start: int = 0,
) -> PromptVisibleSource:
    """Hide storage-only parenthesis escapes without losing source identity."""

    if "\\(" not in source_text and "\\)" not in source_text:
        return PromptVisibleSource(
            display_text=source_text,
            source_positions=range(source_start, source_start + len(source_text) + 1),
        )

    display_characters: list[str] = []
    source_positions: list[int] = [source_start]
    relative_index = 0
    while relative_index < len(source_text):
        character = source_text[relative_index]
        if (
            character == "\\"
            and relative_index + 1 < len(source_text)
            and source_text[relative_index + 1] in "()"
        ):
            display_characters.append(source_text[relative_index + 1])
            relative_index += 2
        else:
            display_characters.append(character)
            relative_index += 1
        source_positions.append(source_start + relative_index)
    return PromptVisibleSource(
        display_text="".join(display_characters),
        source_positions=tuple(source_positions),
    )


__all__ = [
    "PromptVisibleSource",
    "map_prompt_source_for_display",
    "visible_indices_for_source_range",
]
