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

"""Own source-backed cursor and selection state for prompt editing."""

from __future__ import annotations

from .cursor_state import PromptCursorState
from .selection_state import PromptSelection


class PromptCursorSession:
    """Maintain the active source cursor and anchor positions."""

    def __init__(self, cursor_state: PromptCursorState | None = None) -> None:
        """Create a cursor session with an optional initial state."""

        self._cursor_state = cursor_state or PromptCursorState()

    @property
    def cursor_state(self) -> PromptCursorState:
        """Return the current source cursor state."""

        return self._cursor_state

    @property
    def cursor_position(self) -> int:
        """Return the active source cursor position."""

        return self._cursor_state.cursor_position

    @property
    def anchor_position(self) -> int:
        """Return the source selection anchor position."""

        return self._cursor_state.anchor_position

    def selection(self) -> PromptSelection:
        """Return the source selection implied by the cursor state."""

        return self._cursor_state.selection()

    def set_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
        source_length: int,
    ) -> PromptCursorState:
        """Store source cursor positions clamped to the current source length."""

        return self.set_state(
            PromptCursorState(
                cursor_position=cursor_position,
                anchor_position=anchor_position,
            ),
            source_length=source_length,
        )

    def set_state(
        self,
        cursor_state: PromptCursorState,
        *,
        source_length: int,
    ) -> PromptCursorState:
        """Store one cursor state clamped to the current source length."""

        self._cursor_state = cursor_state.clamped(source_length)
        return self._cursor_state

    def collapse_selection(self, *, source_length: int) -> PromptCursorState:
        """Collapse the current selection to the active cursor position."""

        return self.set_state(
            self._cursor_state.collapsed(),
            source_length=source_length,
        )

    def select_all(self, *, source_length: int) -> PromptCursorState:
        """Select the full source text with the cursor at the document end."""

        return self.set_positions(
            cursor_position=source_length,
            anchor_position=0,
            source_length=source_length,
        )


__all__ = ["PromptCursorSession"]
