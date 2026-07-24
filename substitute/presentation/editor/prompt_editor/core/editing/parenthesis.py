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

"""Own durable user parenthesis-escape intent for prompt source segments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptParenthesisIntent:
    """Protect one user-overridden comma-delimited segment from reclassification."""

    segment_start: int
    segment_end: int

    def contains_edit(self, start: int, end: int) -> bool:
        """Return whether one edit stays within this protected segment."""

        return self.segment_start <= start and end <= self.segment_end


def segment_bounds_at(text: str, position: int) -> tuple[int, int]:
    """Return comma-delimited segment bounds containing one source position."""

    clamped = min(max(position, 0), len(text))
    start = text.rfind(",", 0, clamped) + 1
    next_comma = text.find(",", clamped)
    end = len(text) if next_comma < 0 else next_comma
    return start, end


__all__ = ["PromptParenthesisIntent", "segment_bounds_at"]
