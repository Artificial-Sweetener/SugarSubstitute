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

"""Define validated source coordinate values shared by prompt domains."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceRange:
    """Represent one half-open source range inside prompt text."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Reject inverted source ranges."""

        if self.start < 0:
            raise ValueError("SourceRange.start must be non-negative.")
        if self.end < self.start:
            raise ValueError("SourceRange.end must be greater than or equal to start.")

    @property
    def length(self) -> int:
        """Return the number of covered source characters."""

        return self.end - self.start

    def contains(self, position: int, *, inclusive_end: bool = False) -> bool:
        """Return whether the supplied position falls inside this range."""

        if inclusive_end:
            return self.start <= position <= self.end
        return self.start <= position < self.end

    def encloses(self, other: "SourceRange") -> bool:
        """Return whether this range fully contains another range."""

        return self.start <= other.start and self.end >= other.end

    def slice(self, text: str) -> str:
        """Return the covered substring from one source string."""

        return text[self.start : self.end]


__all__ = ["SourceRange"]
