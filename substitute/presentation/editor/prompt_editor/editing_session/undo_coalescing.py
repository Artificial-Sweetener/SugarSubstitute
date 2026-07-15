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

"""Own key-driven undo coalescing for prompt editing sessions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .edit_controller import PromptEditController, PromptPendingKeyEditBlockFlusher

TPayload = TypeVar("TPayload")

DELETE_UNDO_COALESCE_IDLE_MS = 750
TYPING_UNDO_COALESCE_IDLE_MS = 900


class PromptUndoCoalescingTimer(Protocol):
    """Represent one single-shot timer used by undo coalescing policy."""

    def set_timeout_handler(self, handler: Callable[[], None]) -> None:
        """Set the callback invoked when the timer expires."""

    def start(self) -> None:
        """Start or restart the timer."""

    def stop(self) -> None:
        """Stop the timer if it is currently active."""


class PromptUndoCoalescingActions(PromptPendingKeyEditBlockFlusher, Protocol):
    """Expose keymap-facing undo coalescing actions."""

    def finish_delete_group(self, *, reason: str) -> None:
        """Commit any active delete-key undo group."""

    def finish_typing_group(self, *, reason: str) -> None:
        """Commit any active typing undo group."""

    def begin_delete_group(self, *, key: int, autorepeat: bool) -> None:
        """Open or extend a delete-key undo group."""

    def can_group_typed_text(self, text: str) -> bool:
        """Return whether typed text can join the current typing group."""

    def begin_or_extend_typing_group(self, text: str) -> None:
        """Open or extend a typing undo group."""


@dataclass(slots=True)
class PromptUndoCoalescingController(Generic[TPayload]):
    """Coordinate typing and delete undo groups with deterministic timers."""

    edit_controller: PromptEditController[TPayload]
    typing_timer: PromptUndoCoalescingTimer
    delete_timer: PromptUndoCoalescingTimer
    cursor_position: Callable[[], int]
    selection_empty: Callable[[], bool]

    def __post_init__(self) -> None:
        """Bind timer expiry callbacks after construction."""

        self.typing_timer.set_timeout_handler(self._finish_idle_typing_edit_block)
        self.delete_timer.set_timeout_handler(self._finish_idle_delete_edit_block)

    def begin_delete_group(self, *, key: int, autorepeat: bool) -> None:
        """Open or extend one idle-coalesced Backspace/Delete undo group."""

        _ = autorepeat
        self.finish_typing_group(reason="delete_group")
        if self.edit_controller.session.delete_group_active:
            self.delete_timer.stop()
        self.edit_controller.begin_delete_group(key=key)
        self.delete_timer.start()

    def finish_delete_group(self, *, reason: str) -> None:
        """Commit any open Backspace/Delete undo group."""

        _ = reason
        if self.edit_controller.session.delete_group_active:
            self.delete_timer.stop()
        self.edit_controller.finish_delete_group()

    def can_group_typed_text(self, text: str) -> bool:
        """Return whether one typed character may join a word-level undo group."""

        return self.edit_controller.session.can_group_typed_text(
            text,
            selection_empty=self.selection_empty(),
        )

    def begin_or_extend_typing_group(self, text: str) -> None:
        """Open or extend one contiguous typed-word undo group."""

        if self.edit_controller.session.typing_group_active:
            self.typing_timer.stop()
        self.edit_controller.begin_or_extend_typing_group(
            text,
            cursor_position=self.cursor_position(),
        )
        self.typing_timer.start()

    def finish_typing_group(self, *, reason: str) -> None:
        """Commit any open typed-word undo group."""

        _ = reason
        if self.edit_controller.session.typing_group_active:
            self.typing_timer.stop()
        self.edit_controller.finish_typing_group()

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Commit a pending typing edit block for edit-controller edit blocks."""

        self.finish_typing_group(reason=reason)

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Commit pending key-driven typing and delete edit blocks."""

        self.finish_typing_group(reason=reason)
        self.finish_delete_group(reason=reason)

    def _finish_idle_delete_edit_block(self) -> None:
        """Commit a delete undo group after the idle window expires."""

        self.finish_delete_group(reason="idle")

    def _finish_idle_typing_edit_block(self) -> None:
        """Commit a typing undo group after the idle window expires."""

        self.finish_typing_group(reason="idle")


__all__ = [
    "DELETE_UNDO_COALESCE_IDLE_MS",
    "PromptUndoCoalescingActions",
    "PromptUndoCoalescingController",
    "PromptUndoCoalescingTimer",
    "TYPING_UNDO_COALESCE_IDLE_MS",
]
