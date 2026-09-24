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

"""Define shared contracts for semantic projection collapse planning."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)


@dataclass(frozen=True, slots=True)
class PromptProjectionCollapseCandidate:
    """Describe one source span replaced by a semantic projection token."""

    start: int
    end: int
    token: PromptProjectionToken


def contains_nested_supported_range(
    token_range: tuple[int, int],
    supported_ranges: tuple[tuple[int, int], ...],
) -> bool:
    """Return whether one syntax span contains another supported span."""

    token_start, token_end = token_range
    candidate_index = bisect_left(supported_ranges, (token_start, -1))
    for other_start, other_end in supported_ranges[candidate_index:]:
        if other_start >= token_end:
            return False
        if other_end <= token_end and (other_start, other_end) != token_range:
            return True
    return False


__all__ = ["PromptProjectionCollapseCandidate", "contains_nested_supported_range"]
