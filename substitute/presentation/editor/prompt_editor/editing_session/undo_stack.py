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

"""Own prompt undo, redo, and grouped key-edit stack state."""

from __future__ import annotations

from typing import Generic, TypeVar

from .edit_transaction import (
    PromptEditTransaction,
    PromptUndoAvailability,
    PromptUndoAvailabilityChange,
    PromptUndoRestoreResult,
    PromptUndoSnapshot,
)

TPayload = TypeVar("TPayload")


class PromptUndoStack(Generic[TPayload]):
    """Manage bounded prompt undo/redo history and edit grouping state."""

    def __init__(
        self,
        *,
        max_undo_states: int,
        max_redo_states: int,
    ) -> None:
        """Create an empty bounded undo owner."""

        if max_undo_states < 1:
            raise ValueError("Undo stack size must be positive.")
        if max_redo_states < 1:
            raise ValueError("Redo stack size must be positive.")
        self._max_undo_states = max_undo_states
        self._max_redo_states = max_redo_states
        self._undo_stack: list[PromptUndoSnapshot[TPayload]] = []
        self._redo_stack: list[PromptUndoSnapshot[TPayload]] = []
        self._edit_block_depth = 0
        self._pending_undo_state: PromptUndoSnapshot[TPayload] | None = None
        self._delete_group_active = False
        self._delete_group_key: int | None = None
        self._typing_group_active = False
        self._typing_group_last_cursor_position: int | None = None

    @property
    def undo_depth(self) -> int:
        """Return the number of stored undo snapshots."""

        return len(self._undo_stack)

    @property
    def redo_depth(self) -> int:
        """Return the number of stored redo snapshots."""

        return len(self._redo_stack)

    @property
    def edit_block_depth(self) -> int:
        """Return the current nested edit-block depth."""

        return self._edit_block_depth

    @property
    def typing_group_active(self) -> bool:
        """Return whether a typed-word undo group is currently open."""

        return self._typing_group_active

    @property
    def delete_group_active(self) -> bool:
        """Return whether a delete-key undo group is currently open."""

        return self._delete_group_active

    def can_undo(self) -> bool:
        """Return whether an undo snapshot is available."""

        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        """Return whether a redo snapshot is available."""

        return bool(self._redo_stack)

    def availability(self) -> PromptUndoAvailability:
        """Return current undo and redo availability."""

        return PromptUndoAvailability(
            can_undo=self.can_undo(),
            can_redo=self.can_redo(),
        )

    def begin_edit_block(self, snapshot: PromptUndoSnapshot[TPayload]) -> None:
        """Start or nest one grouped edit transaction."""

        if self._edit_block_depth == 0:
            self._pending_undo_state = snapshot
        self._edit_block_depth += 1

    def end_edit_block(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Finish one grouped edit transaction and commit it if changed."""

        if self._edit_block_depth == 0:
            return None
        self._edit_block_depth -= 1
        if self._edit_block_depth > 0:
            return None
        return self._commit_pending_undo_state(current_snapshot)

    def record_snapshot(
        self,
        snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Record one pre-edit snapshot or defer it into the active edit block."""

        if self._edit_block_depth > 0:
            if self._pending_undo_state is None:
                self._pending_undo_state = snapshot
            return None
        previous = self.availability()
        self._push_undo_state(snapshot)
        self._redo_stack.clear()
        return self._availability_change_since(previous)

    def undo(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoRestoreResult[TPayload] | None:
        """Move one undo snapshot to restore and store current state for redo."""

        if not self._undo_stack:
            return None
        previous = self.availability()
        restore_snapshot = self._undo_stack.pop()
        self._push_redo_state(current_snapshot)
        return PromptUndoRestoreResult(
            snapshot=restore_snapshot,
            availability_change=self._availability_change_since(previous),
        )

    def redo(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoRestoreResult[TPayload] | None:
        """Move one redo snapshot to restore and store current state for undo."""

        if not self._redo_stack:
            return None
        previous = self.availability()
        restore_snapshot = self._redo_stack.pop()
        self._push_undo_state(current_snapshot)
        return PromptUndoRestoreResult(
            snapshot=restore_snapshot,
            availability_change=self._availability_change_since(previous),
        )

    def clear(self) -> PromptUndoAvailabilityChange:
        """Clear undo history, redo history, pending blocks, and key groups."""

        previous = self.availability()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._edit_block_depth = 0
        self._pending_undo_state = None
        self._delete_group_active = False
        self._delete_group_key = None
        self._typing_group_active = False
        self._typing_group_last_cursor_position = None
        return self._availability_change_since(previous)

    def discard_trailing_undo_state(
        self,
        expected_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Remove one expected trailing undo snapshot without disturbing history."""

        if not self._undo_stack:
            return None
        if self._undo_stack[-1] != expected_snapshot:
            return None
        previous = self.availability()
        self._undo_stack.pop()
        return self._availability_change_since(previous)

    def can_group_typed_text(self, text: str, *, selection_empty: bool) -> bool:
        """Return whether typed text can join a contiguous word undo group."""

        if len(text) != 1:
            return False
        if not selection_empty:
            return False
        return text.isalnum() or text in {"_", "-"}

    def begin_or_extend_typing_group(
        self,
        text: str,
        *,
        cursor_position: int,
        snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Open or extend one contiguous typed-word undo group."""

        if (
            self._typing_group_active
            and self._typing_group_last_cursor_position == cursor_position
        ):
            self._typing_group_last_cursor_position = cursor_position + len(text)
            return None

        availability_change = self.finish_typing_group(snapshot)
        self.begin_edit_block(snapshot)
        self._typing_group_active = True
        self._typing_group_last_cursor_position = cursor_position + len(text)
        return availability_change

    def finish_typing_group(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Commit any open typed-word undo group."""

        if not self._typing_group_active:
            return None
        self._typing_group_active = False
        self._typing_group_last_cursor_position = None
        return self.end_edit_block(current_snapshot)

    def begin_delete_group(
        self,
        *,
        key: int,
        snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Open or extend one key-specific delete undo group."""

        if self._delete_group_active and self._delete_group_key == key:
            return None

        availability_change = self.finish_delete_group(snapshot)
        self.begin_edit_block(snapshot)
        self._delete_group_active = True
        self._delete_group_key = key
        return availability_change

    def finish_delete_group(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Commit any open Backspace/Delete undo group."""

        if not self._delete_group_active:
            return None
        self._delete_group_active = False
        self._delete_group_key = None
        return self.end_edit_block(current_snapshot)

    def _commit_pending_undo_state(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Commit a pending grouped transaction if it changed state."""

        pending_snapshot = self._pending_undo_state
        self._pending_undo_state = None
        if pending_snapshot is None:
            return None
        transaction = PromptEditTransaction(
            before_snapshot=pending_snapshot,
            after_snapshot=current_snapshot,
        )
        if not transaction.has_changes:
            return None
        previous = self.availability()
        self._push_undo_state(pending_snapshot)
        self._redo_stack.clear()
        return self._availability_change_since(previous)

    def _push_undo_state(self, snapshot: PromptUndoSnapshot[TPayload]) -> None:
        """Push one undo snapshot and trim old history."""

        self._undo_stack.append(snapshot)
        overflow = max(0, len(self._undo_stack) - self._max_undo_states)
        del self._undo_stack[:overflow]

    def _push_redo_state(self, snapshot: PromptUndoSnapshot[TPayload]) -> None:
        """Push one redo snapshot and trim old history."""

        self._redo_stack.append(snapshot)
        overflow = max(0, len(self._redo_stack) - self._max_redo_states)
        del self._redo_stack[:overflow]

    def _availability_change_since(
        self,
        previous: PromptUndoAvailability,
    ) -> PromptUndoAvailabilityChange:
        """Return the transition from a previous availability state."""

        return PromptUndoAvailabilityChange(
            previous=previous,
            current=self.availability(),
        )


__all__ = ["PromptUndoStack"]
