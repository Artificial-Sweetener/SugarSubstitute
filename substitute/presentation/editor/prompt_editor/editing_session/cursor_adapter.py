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

"""Expose a QTextCursor-like adapter backed by source cursor state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .cursor_state import PromptCursorState


class PromptCursorAdapterHost(Protocol):
    """Describe live editor operations needed by the public cursor adapter."""

    def cursor_adapter_source_text(self) -> str:
        """Return current prompt source text."""

    def cursor_adapter_state(self) -> PromptCursorState:
        """Return current source cursor state."""

    def cursor_adapter_commit_state(
        self,
        cursor_state: PromptCursorState,
        *,
        reason: str,
    ) -> PromptCursorState:
        """Apply a source cursor state to the live editor."""

    def cursor_adapter_is_keep_anchor_mode(self, mode: object | None) -> bool:
        """Return whether one opaque mode object means keep-anchor selection."""

    def cursor_adapter_finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Finish pending key edit grouping before explicit cursor commands."""

    def move_cursor_by_operation(
        self,
        operation: object,
        *,
        keep_anchor: bool,
    ) -> PromptCursorState:
        """Move the live cursor by one opaque QTextCursor operation."""

    def cursor_adapter_begin_edit_block(self, *, finish_typing: bool = True) -> None:
        """Begin a grouped edit block."""

    def cursor_adapter_end_edit_block(self) -> None:
        """End a grouped edit block."""

    def cursor_adapter_delete_selection(self) -> None:
        """Delete the current live source selection."""

    def cursor_adapter_insert_text(
        self,
        text: str,
    ) -> None:
        """Insert text at the current live cursor selection."""

    def select_by_mode(self, mode: object) -> PromptCursorState:
        """Select a logical range around the live cursor."""


@dataclass(frozen=True, slots=True)
class PromptCursorSelectionAdapter:
    """Expose the small Qt-like selection wrapper expected by callers."""

    cursor_state: PromptCursorState

    def isEmpty(self) -> bool:  # noqa: N802
        """Return whether the adapted cursor selection is empty."""

        return self.cursor_state.cursor_position == self.cursor_state.anchor_position


class PromptCursorAdapter:
    """Expose a source-backed QTextCursor-compatible adapter."""

    def __init__(
        self,
        host: PromptCursorAdapterHost,
        cursor_state: PromptCursorState | None = None,
    ) -> None:
        """Bind the adapter to a live editor host and source cursor state."""

        self._host = host
        self._cursor_state = cursor_state or host.cursor_adapter_state()

    def position(self) -> int:
        """Return the current raw source cursor position."""

        return self._cursor_state.cursor_position

    def selection(self) -> PromptCursorSelectionAdapter:
        """Return a lightweight wrapper exposing selection emptiness."""

        return PromptCursorSelectionAdapter(self._cursor_state)

    def selectionStart(self) -> int:  # noqa: N802
        """Return the inclusive raw source selection start."""

        return self._cursor_state.selection().start

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the exclusive raw source selection end."""

        return self._cursor_state.selection().end

    def selectedText(self) -> str:  # noqa: N802
        """Return the selected raw source text."""

        return self._cursor_state.selection().selected_text(
            self._host.cursor_adapter_source_text()
        )

    def setPosition(self, pos: int, mode: object | None = None) -> None:  # noqa: N802
        """Move or extend the raw source cursor position."""

        self._host.cursor_adapter_finish_pending_key_edit_block(
            reason="cursor_set_position"
        )
        keep_anchor = self._host.cursor_adapter_is_keep_anchor_mode(mode)
        anchor_position = self._cursor_state.anchor_position if keep_anchor else pos
        self._cursor_state = self._host.cursor_adapter_commit_state(
            PromptCursorState(
                cursor_position=pos,
                anchor_position=anchor_position,
            ),
            reason="cursor_set_position",
        )

    def movePosition(  # noqa: N802
        self,
        operation: object,
        mode: object | None = None,
        length: int = 1,
    ) -> None:
        """Move the cursor using the host's QTextCursor operation support."""

        self._host.cursor_adapter_finish_pending_key_edit_block(
            reason="cursor_move_position"
        )
        keep_anchor = self._host.cursor_adapter_is_keep_anchor_mode(mode)
        for _ in range(max(1, length)):
            self._cursor_state = self._host.move_cursor_by_operation(
                operation,
                keep_anchor=keep_anchor,
            )

    def beginEditBlock(self) -> None:  # noqa: N802
        """Start grouping edits into one undo snapshot."""

        self._host.cursor_adapter_begin_edit_block()

    def endEditBlock(self) -> None:  # noqa: N802
        """Finish grouping edits into one undo snapshot."""

        self._host.cursor_adapter_end_edit_block()

    def removeSelectedText(self) -> None:  # noqa: N802
        """Delete the selected raw source text."""

        self._commit_local_state(reason="cursor_remove_selected_text")
        self._host.cursor_adapter_delete_selection()
        self._cursor_state = self._host.cursor_adapter_state()

    def clearSelection(self) -> None:  # noqa: N802
        """Collapse the current selection to the active cursor position."""

        self._cursor_state = self._host.cursor_adapter_commit_state(
            self._cursor_state.collapsed(),
            reason="cursor_clear_selection",
        )

    def insertText(self, text: str) -> None:  # noqa: N802
        """Replace the current selection with plain text."""

        self._host.cursor_adapter_finish_pending_key_edit_block(
            reason="cursor_insert_text"
        )
        self._commit_local_state(reason="cursor_insert_text")
        self._host.cursor_adapter_insert_text(text)
        self._cursor_state = self._host.cursor_adapter_state()

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor currently has a selection."""

        return not self.selection().isEmpty()

    def select(self, mode: object) -> None:
        """Select one supported logical range around the current cursor."""

        self._commit_local_state(reason="cursor_select")
        self._cursor_state = self._host.select_by_mode(mode)

    def cursor_state(self) -> PromptCursorState:
        """Return the adapter's current source cursor state."""

        return self._cursor_state

    def _commit_local_state(self, *, reason: str) -> None:
        """Apply the adapter's local cursor state to the live host."""

        self._cursor_state = self._host.cursor_adapter_commit_state(
            self._cursor_state,
            reason=reason,
        )


__all__ = [
    "PromptCursorAdapter",
    "PromptCursorAdapterHost",
    "PromptCursorSelectionAdapter",
]
