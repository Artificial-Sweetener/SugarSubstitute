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

"""Apply reorder cursor facts and close transitions at the Qt boundary."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtGui import QTextCursor

from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCloseTransition,
)


class PromptReorderSelection(Protocol):
    """Describe the selection query needed to prepare a reorder entry request."""

    def isEmpty(self) -> bool:
        """Return whether the selection has no source span."""


class PromptReorderCursor(Protocol):
    """Describe the Qt cursor operations used at reorder lifecycle boundaries."""

    def position(self) -> int:
        """Return the cursor position."""

    def selection(self) -> PromptReorderSelection:
        """Return the current selection query."""

    def selectionStart(self) -> int:
        """Return the inclusive selection start."""

    def selectionEnd(self) -> int:
        """Return the exclusive selection end."""

    def setPosition(self, pos: int, mode: object | None = None) -> None:
        """Move or extend the cursor selection."""


class PromptReorderCursorSurface(Protocol):
    """Expose the Qt cursor boundary consumed by reorder session teardown."""

    def textCursor(self) -> PromptReorderCursor:
        """Return the editor's live cursor object."""

    def setTextCursor(self, cursor: PromptReorderCursor) -> None:
        """Persist the supplied cursor selection back to the editor."""


class PromptReorderCursorSelectionAdapter:
    """Apply source selection effects emitted by the application lifecycle owner."""

    def restore(
        self,
        surface: PromptReorderCursorSurface,
        transition: PromptReorderCloseTransition,
    ) -> None:
        """Restore the optional half-open selection carried by one close transition."""

        selection_start = transition.selection_start
        selection_end = transition.selection_end
        if selection_start is None or selection_end is None:
            return
        cursor = surface.textCursor()
        cursor.setPosition(selection_start, QTextCursor.MoveMode.MoveAnchor)
        cursor.setPosition(selection_end, QTextCursor.MoveMode.KeepAnchor)
        surface.setTextCursor(cursor)


__all__ = [
    "PromptReorderCursor",
    "PromptReorderCursorSelectionAdapter",
    "PromptReorderCursorSurface",
]
