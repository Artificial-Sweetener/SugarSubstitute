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

from typing import Generic, overload, TypeVar

from .commands import (
    PromptRedoEdit,
    PromptReplaceDocumentEdit,
    PromptReplaceRangeEdit,
    PromptSetCursorEdit,
    PromptSourceEditCommand,
    PromptUndoEdit,
)
from .commit import PromptEditCommit, PromptEditScope
from .clipboard import (
    PromptClipboardController,
    PromptClipboardCopyResult,
    PromptClipboardCutResult,
    PromptClipboardPasteResult,
)
from .cursor import PromptCursorSession
from .cursor_state import PromptCursorState
from .transactions import (
    PromptUndoAvailability,
    PromptUndoAvailabilityChange,
    PromptUndoRestoreResult,
    PromptUndoSnapshot,
)
from .selection import PromptSelection
from .source_buffer import PromptSourceBuffer, PromptSourceSnapshot
from .source_commands import (
    PromptSourceEditResult,
    PromptSourceEditOrigin,
    PromptSourceEditSession,
    source_text_edit_between,
)
from .undo import PromptUndoStack
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

TPayload = TypeVar("TPayload")


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
    def source_identity(self) -> PromptSourceIdentity:
        """Return the current source identity without copying source state."""

        return self._source_edits.source_identity

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

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_SELECTION)
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

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_SET_CURSOR_POSITIONS)
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

    @overload
    def execute(
        self,
        command: PromptReplaceRangeEdit[TPayload],
    ) -> PromptEditCommit[TPayload]: ...

    @overload
    def execute(
        self,
        command: PromptReplaceDocumentEdit[TPayload],
    ) -> PromptEditCommit[TPayload]: ...

    @overload
    def execute(
        self,
        command: PromptUndoEdit[TPayload] | PromptRedoEdit[TPayload],
    ) -> PromptEditCommit[TPayload] | None: ...

    @overload
    def execute(self, command: PromptSetCursorEdit) -> PromptCursorState: ...

    def execute(
        self,
        command: PromptSourceEditCommand[TPayload] | PromptSetCursorEdit,
    ) -> PromptEditCommit[TPayload] | PromptCursorState | None:
        """Execute one typed command through the sole editing-state owner."""

        if isinstance(command, PromptReplaceRangeEdit):
            return self._execute_range_edit(command)
        if isinstance(command, PromptReplaceDocumentEdit):
            return self._execute_document_edit(command)
        if isinstance(command, PromptUndoEdit):
            return self._execute_history_edit(command.current_snapshot, undo=True)
        if isinstance(command, PromptRedoEdit):
            return self._execute_history_edit(command.current_snapshot, undo=False)
        if isinstance(command, PromptSetCursorEdit):
            return self.set_cursor_state(command.cursor_state)
        raise TypeError(f"Unsupported prompt editing command: {type(command).__name__}")

    def begin_edit_block(self, snapshot: PromptUndoSnapshot[TPayload]) -> None:
        """Start or nest one grouped edit transaction."""

        self._undo_stack.begin_edit_block(snapshot)

    def end_edit_block(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptUndoAvailabilityChange | None:
        """Finish one grouped edit transaction."""

        return self._undo_stack.end_edit_block(current_snapshot)

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

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_PASTE)
    def paste(self, pasted_text: str) -> PromptClipboardPasteResult:
        """Return the source range that should receive pasted text."""

        return self._clipboard_controller.paste(
            pasted_text=pasted_text,
            source_text=self.source_text,
            selection=self.selection(),
        )

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_REPLACE_RANGE)
    def _execute_range_edit(
        self,
        command: PromptReplaceRangeEdit[TPayload],
    ) -> PromptEditCommit[TPayload]:
        """Commit one typed range replacement."""

        previous_cursor_state = self.cursor_state
        result = self._source_edits.replace_source_range(
            start=command.start,
            end=command.end,
            replacement_text=command.replacement_text,
            normalizer=command.normalizer,
            origin=command.origin,
            exact_source=command.exact_source,
            record_undo=command.record_undo,
            undo_snapshot=command.undo_snapshot,
        )
        cursor_state = self._cursor_session.set_state(
            result.cursor_state,
            source_length=result.next_snapshot.source_length,
        )
        if command.cursor_position is not None:
            cursor_state = self._cursor_session.set_positions(
                cursor_position=command.cursor_position,
                anchor_position=(
                    command.cursor_position
                    if command.anchor_position is None
                    else command.anchor_position
                ),
                source_length=result.next_snapshot.source_length,
            )
        return self._edit_commit_from_source_result(
            result,
            previous_cursor_state=previous_cursor_state,
            cursor_state=cursor_state,
            origin=command.origin,
            scope=PromptEditScope.RANGE,
        )

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_REPLACE_FULL_SOURCE)
    def _execute_document_edit(
        self,
        command: PromptReplaceDocumentEdit[TPayload],
    ) -> PromptEditCommit[TPayload]:
        """Commit one typed complete-source replacement."""

        previous_cursor_state = self.cursor_state
        result = self._source_edits.replace_full_source(
            command.text,
            cursor_position=command.cursor_position,
            anchor_position=command.anchor_position,
            normalizer=command.normalizer,
            exact_source=command.exact_source,
            record_undo=command.record_undo,
            clear_history=command.clear_history,
            undo_snapshot=command.undo_snapshot,
        )
        cursor_state = self._cursor_session.set_state(
            result.cursor_state,
            source_length=result.next_snapshot.source_length,
        )
        return self._edit_commit_from_source_result(
            result,
            previous_cursor_state=previous_cursor_state,
            cursor_state=cursor_state,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            scope=PromptEditScope.DOCUMENT,
        )

    def _execute_history_edit(
        self,
        current_snapshot: PromptUndoSnapshot[TPayload],
        *,
        undo: bool,
    ) -> PromptEditCommit[TPayload] | None:
        """Commit one undo or redo restoration as a normal editing result."""

        previous_snapshot = self.source_snapshot()
        previous_cursor_state = self.cursor_state
        restore_result = (
            self._undo_stack.undo(current_snapshot)
            if undo
            else self._undo_stack.redo(current_snapshot)
        )
        if restore_result is None:
            return None
        next_snapshot, cursor_state = self._restore_snapshot(restore_result)
        return PromptEditCommit(
            previous_snapshot=previous_snapshot,
            next_snapshot=next_snapshot,
            previous_cursor_state=previous_cursor_state,
            cursor_state=cursor_state,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            scope=PromptEditScope.HISTORY,
            source_edit=source_text_edit_between(
                previous_snapshot.source_text,
                next_snapshot.source_text,
            ),
            requested_start=0,
            requested_end=previous_snapshot.source_length,
            requested_replacement_text=next_snapshot.source_text,
            undo_availability_change=restore_result.availability_change,
            restored_undo_snapshot=restore_result.snapshot,
        )

    @staticmethod
    def _edit_commit_from_source_result(
        result: PromptSourceEditResult[TPayload],
        *,
        previous_cursor_state: PromptCursorState,
        cursor_state: PromptCursorState,
        origin: PromptSourceEditOrigin,
        scope: PromptEditScope,
    ) -> PromptEditCommit[TPayload]:
        """Convert the internal normalized mutation result into one public commit."""

        return PromptEditCommit(
            previous_snapshot=result.previous_snapshot,
            next_snapshot=result.next_snapshot,
            previous_cursor_state=previous_cursor_state,
            cursor_state=cursor_state,
            origin=origin,
            scope=scope,
            source_edit=result.source_edit,
            requested_start=result.requested_start,
            requested_end=result.requested_end,
            requested_replacement_text=result.requested_replacement_text,
            transitions=result.transitions,
            undo_availability_change=result.undo_availability_change,
        )

    def _restore_snapshot(
        self,
        restore_result: PromptUndoRestoreResult[TPayload],
    ) -> tuple[PromptSourceSnapshot, PromptCursorState]:
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
        return source_snapshot, cursor_state


__all__ = ["PromptEditingSession"]
