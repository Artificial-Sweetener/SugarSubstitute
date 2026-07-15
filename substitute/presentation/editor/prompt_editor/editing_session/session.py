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

"""Coordinate source, cursor, clipboard, and undo state for one prompt editor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .clipboard_controller import (
    PromptClipboardController,
    PromptClipboardCopyResult,
    PromptClipboardCutResult,
    PromptClipboardPasteResult,
)
from .cursor_session import PromptCursorSession
from .cursor_state import PromptCursorState
from .edit_transaction import (
    PromptUndoAvailability,
    PromptUndoAvailabilityChange,
    PromptUndoRestoreResult,
    PromptUndoSnapshot,
)
from .selection_state import PromptSelection
from .source_buffer import PromptSourceBuffer, PromptSourceSnapshot
from .source_edit_commands import (
    PromptSourceEditResult,
    PromptSourceEditOrigin,
    PromptSourceEditSession,
    PromptSourceNormalizer,
    PromptSourceTextEdit,
)
from .undo_stack import PromptUndoStack
from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
    PromptParenthesisTransition,
)

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptEditingSessionSourceChange(Generic[TPayload]):
    """Report one source edit after editing-session state has been updated."""

    source_result: PromptSourceEditResult[TPayload]
    cursor_state: PromptCursorState

    @property
    def previous_snapshot(self) -> PromptSourceSnapshot:
        """Return the source snapshot before the edit."""

        return self.source_result.previous_snapshot

    @property
    def next_snapshot(self) -> PromptSourceSnapshot:
        """Return the source snapshot after the edit."""

        return self.source_result.next_snapshot

    @property
    def source_changed(self) -> bool:
        """Return whether this transaction changed source text."""

        return self.source_result.source_changed

    @property
    def undo_availability_change(self) -> PromptUndoAvailabilityChange | None:
        """Return any undo/redo availability transition from this edit."""

        return self.source_result.undo_availability_change

    @property
    def source_edit(self) -> PromptSourceTextEdit | None:
        """Return the bounded source edit, if the source text changed."""

        return self.source_result.source_edit

    @property
    def transitions(self) -> tuple[PromptParenthesisTransition, ...]:
        """Return semantic parenthesis transitions emitted by normalization."""

        return self.source_result.transitions


@dataclass(frozen=True, slots=True)
class PromptEditingSessionRestoreResult(Generic[TPayload]):
    """Report an undo/redo snapshot restored into the editing session."""

    restore_result: PromptUndoRestoreResult[TPayload]
    source_snapshot: PromptSourceSnapshot
    cursor_state: PromptCursorState

    @property
    def snapshot(self) -> PromptUndoSnapshot[TPayload]:
        """Return the undo snapshot restored by the session."""

        return self.restore_result.snapshot

    @property
    def availability_change(self) -> PromptUndoAvailabilityChange:
        """Return the undo/redo availability transition."""

        return self.restore_result.availability_change


class PromptEditingSession(Generic[TPayload]):
    """Own source text, cursor, selection, clipboard intent, and undo/redo state."""

    def __init__(
        self,
        *,
        source_text: str,
        source_revision: int,
        cursor_state: PromptCursorState,
        max_undo_states: int,
        max_redo_states: int,
    ) -> None:
        """Create one editor-session owner from initial source and cursor state."""

        self._undo_stack = PromptUndoStack[TPayload](
            max_undo_states=max_undo_states,
            max_redo_states=max_redo_states,
        )
        self._source_edits = PromptSourceEditSession[TPayload](
            source_buffer=PromptSourceBuffer(
                source_text=source_text,
                source_revision=source_revision,
            ),
            undo_stack=self._undo_stack,
        )
        self._cursor_session = PromptCursorSession(
            cursor_state.clamped(len(source_text))
        )
        self._clipboard_controller = PromptClipboardController()

    @property
    def source_text(self) -> str:
        """Return the current source text."""

        return self._source_edits.source_text

    @property
    def source_revision(self) -> int:
        """Return the current source revision."""

        return self._source_edits.source_revision

    @property
    def cursor_state(self) -> PromptCursorState:
        """Return the active source cursor state."""

        return self._cursor_session.cursor_state

    @property
    def cursor_position(self) -> int:
        """Return the active source cursor position."""

        return self._cursor_session.cursor_position

    @property
    def anchor_position(self) -> int:
        """Return the active source anchor position."""

        return self._cursor_session.anchor_position

    @property
    def typing_group_active(self) -> bool:
        """Return whether a typed-word undo group is open."""

        return self._undo_stack.typing_group_active

    @property
    def delete_group_active(self) -> bool:
        """Return whether a delete-key undo group is open."""

        return self._undo_stack.delete_group_active

    def source_snapshot(self) -> PromptSourceSnapshot:
        """Return a snapshot of the current source text and revision."""

        return self._source_edits.snapshot()

    def selection(self) -> PromptSelection:
        """Return the active source selection."""

        return self._cursor_session.selection()

    def can_undo(self) -> bool:
        """Return whether undo is currently available."""

        return self._undo_stack.can_undo()

    def can_redo(self) -> bool:
        """Return whether redo is currently available."""

        return self._undo_stack.can_redo()

    def availability(self) -> PromptUndoAvailability:
        """Return current undo and redo availability."""

        return self._undo_stack.availability()

    def set_cursor_state(self, cursor_state: PromptCursorState) -> PromptCursorState:
        """Commit one source cursor state into the editing session."""

        return self._cursor_session.set_state(
            cursor_state,
            source_length=len(self.source_text),
        )

    def set_cursor_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
    ) -> PromptCursorState:
        """Commit source cursor positions into the editing session."""

        return self._cursor_session.set_positions(
            cursor_position=cursor_position,
            anchor_position=anchor_position,
            source_length=len(self.source_text),
        )

    def select_all(self) -> PromptCursorState:
        """Select the full source text."""

        return self._cursor_session.select_all(source_length=len(self.source_text))

    def replace_full_source(
        self,
        text: str,
        *,
        cursor_position: int,
        anchor_position: int,
        normalizer: PromptSourceNormalizer,
        exact_source: bool,
        record_undo: bool,
        clear_history: bool,
        undo_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptEditingSessionSourceChange[TPayload]:
        """Replace all source text and update session cursor ownership."""

        result = self._source_edits.replace_full_source(
            text,
            cursor_position=cursor_position,
            anchor_position=anchor_position,
            normalizer=normalizer,
            exact_source=exact_source,
            record_undo=record_undo,
            clear_history=clear_history,
            undo_snapshot=undo_snapshot,
        )
        return self._commit_source_edit_result(result)

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        normalizer: PromptSourceNormalizer,
        origin: PromptSourceEditOrigin,
        exact_source: bool,
        record_undo: bool,
        undo_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptEditingSessionSourceChange[TPayload]:
        """Replace one source range and update session cursor ownership."""

        result = self._source_edits.replace_source_range(
            start=start,
            end=end,
            replacement_text=replacement_text,
            normalizer=normalizer,
            origin=origin,
            exact_source=exact_source,
            record_undo=record_undo,
            undo_snapshot=undo_snapshot,
        )
        return self._commit_source_edit_result(result)

    def begin_edit_block(self, snapshot: PromptUndoSnapshot[TPayload]) -> None:
        """Start or nest one grouped edit transaction."""

        self._undo_stack.begin_edit_block(snapshot)

    def end_edit_block(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Finish one grouped edit transaction."""

        return self._undo_stack.end_edit_block(current_snapshot)

    def undo(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptEditingSessionRestoreResult[TPayload] | None:
        """Restore the previous undo snapshot into the editing session."""

        restore_result = self._undo_stack.undo(current_snapshot)
        if restore_result is None:
            return None
        return self._restore_snapshot(restore_result)

    def redo(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptEditingSessionRestoreResult[TPayload] | None:
        """Restore the next redo snapshot into the editing session."""

        restore_result = self._undo_stack.redo(current_snapshot)
        if restore_result is None:
            return None
        return self._restore_snapshot(restore_result)

    def discard_trailing_undo_state(
        self,
        expected_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Remove one expected trailing undo snapshot from history."""

        return self._undo_stack.discard_trailing_undo_state(expected_snapshot)

    def can_group_typed_text(self, text: str, *, selection_empty: bool) -> bool:
        """Return whether typed text can join a contiguous word undo group."""

        return self._undo_stack.can_group_typed_text(
            text,
            selection_empty=selection_empty,
        )

    def begin_or_extend_typing_group(
        self,
        text: str,
        *,
        cursor_position: int,
        snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Open or extend one contiguous typed-word undo group."""

        return self._undo_stack.begin_or_extend_typing_group(
            text,
            cursor_position=cursor_position,
            snapshot=snapshot,
        )

    def finish_typing_group(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Commit any open typed-word undo group."""

        return self._undo_stack.finish_typing_group(current_snapshot)

    def begin_delete_group(
        self,
        *,
        key: int,
        snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Open or extend one key-specific delete undo group."""

        return self._undo_stack.begin_delete_group(key=key, snapshot=snapshot)

    def finish_delete_group(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Commit any open Backspace/Delete undo group."""

        return self._undo_stack.finish_delete_group(current_snapshot)

    def copy(self) -> PromptClipboardCopyResult:
        """Return source text covered by the active selection."""

        return self._clipboard_controller.copy(
            source_text=self.source_text,
            selection=self.selection(),
        )

    def cut(self) -> PromptClipboardCutResult | None:
        """Return the active selection as a cut intent."""

        return self._clipboard_controller.cut(
            source_text=self.source_text,
            selection=self.selection(),
        )

    def paste(self, pasted_text: str) -> PromptClipboardPasteResult:
        """Return the source range that should receive pasted text."""

        return self._clipboard_controller.paste(
            pasted_text=pasted_text,
            source_text=self.source_text,
            selection=self.selection(),
        )

    def _commit_source_edit_result(
        self,
        result: PromptSourceEditResult[TPayload],
    ) -> PromptEditingSessionSourceChange[TPayload]:
        """Commit source-edit cursor output into source cursor ownership."""

        cursor_state = self._cursor_session.set_state(
            result.cursor_state,
            source_length=result.next_snapshot.source_length,
        )
        return PromptEditingSessionSourceChange(
            source_result=result,
            cursor_state=cursor_state,
        )

    def _restore_snapshot(
        self,
        restore_result: PromptUndoRestoreResult[TPayload],
    ) -> PromptEditingSessionRestoreResult[TPayload]:
        """Synchronize source and cursor ownership to one undo snapshot."""

        snapshot = restore_result.snapshot
        source_snapshot = self._source_edits.synchronize_source_text(
            snapshot.source_text,
            parenthesis_intents=snapshot.parenthesis_intents,
            generated_emphases=snapshot.generated_emphases,
        )
        cursor_state = self._cursor_session.set_state(
            snapshot.cursor_state,
            source_length=source_snapshot.source_length,
        )
        return PromptEditingSessionRestoreResult(
            restore_result=restore_result,
            source_snapshot=source_snapshot,
            cursor_state=cursor_state,
        )


__all__ = [
    "PromptEditingSession",
    "PromptEditingSessionRestoreResult",
    "PromptEditingSessionSourceChange",
]
