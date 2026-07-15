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

"""Define source-backed selection state for the prompt editing session."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptSelection:
    """Describe a half-open source selection while preserving anchor direction."""

    anchor_position: int = 0
    cursor_position: int = 0

    def __post_init__(self) -> None:
        """Reject negative source positions before selection ranges are consumed."""

        if self.anchor_position < 0:
            raise ValueError("Anchor position must be non-negative.")
        if self.cursor_position < 0:
            raise ValueError("Cursor position must be non-negative.")

    @property
    def start(self) -> int:
        """Return the inclusive normalized selection start."""

        return min(self.anchor_position, self.cursor_position)

    @property
    def end(self) -> int:
        """Return the exclusive normalized selection end."""

        return max(self.anchor_position, self.cursor_position)

    @property
    def is_empty(self) -> bool:
        """Return whether this selection covers no source text."""

        return self.anchor_position == self.cursor_position

    def clamped(self, source_length: int) -> "PromptSelection":
        """Return this selection constrained to one source text length."""

        if source_length < 0:
            raise ValueError("Source length must be non-negative.")
        return PromptSelection(
            anchor_position=min(self.anchor_position, source_length),
            cursor_position=min(self.cursor_position, source_length),
        )

    def selected_text(self, source_text: str) -> str:
        """Return the raw source text covered by this selection."""

        selection = self.clamped(len(source_text))
        return source_text[selection.start : selection.end]


__all__ = ["PromptSelection"]
