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

"""Define source-backed cursor state for the prompt editing session."""

from __future__ import annotations

from dataclasses import dataclass

from .selection_state import PromptSelection


@dataclass(frozen=True, slots=True)
class PromptCursorState:
    """Track cursor and anchor source positions without projection placement."""

    cursor_position: int = 0
    anchor_position: int = 0

    def __post_init__(self) -> None:
        """Reject negative source positions before projection adapters consume them."""

        if self.cursor_position < 0:
            raise ValueError("Cursor position must be non-negative.")
        if self.anchor_position < 0:
            raise ValueError("Anchor position must be non-negative.")

    def clamped(self, source_length: int) -> "PromptCursorState":
        """Return this state constrained to one source text length."""

        if source_length < 0:
            raise ValueError("Source length must be non-negative.")
        return PromptCursorState(
            cursor_position=min(self.cursor_position, source_length),
            anchor_position=min(self.anchor_position, source_length),
        )

    def collapsed(self) -> "PromptCursorState":
        """Return a state whose anchor is collapsed to the cursor position."""

        return PromptCursorState(
            cursor_position=self.cursor_position,
            anchor_position=self.cursor_position,
        )

    def selection(self) -> PromptSelection:
        """Return the source-backed selection implied by this cursor state."""

        return PromptSelection(
            anchor_position=self.anchor_position,
            cursor_position=self.cursor_position,
        )


__all__ = ["PromptCursorState"]
