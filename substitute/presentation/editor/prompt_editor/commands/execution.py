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

"""Execute typed editing commands and publish each resulting commit once."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Generic, Protocol, TypeVar

from ..core.editing.commands import (
    PromptRedoEdit,
    PromptReplaceDocumentEdit,
    PromptReplaceRangeEdit,
    PromptUndoEdit,
)
from ..core.editing.commit import PromptEditCommit
from ..core.editing.session import PromptEditingSession
from ..core.editing.source_commands import (
    PromptSourceEditOrigin,
    PromptSourceNormalizer,
)
from ..core.editing.transactions import (
    PromptUndoAvailabilityChange,
    PromptUndoSnapshot,
)
from .contracts import PromptCommandResult, PromptEditorCommand

TPayload = TypeVar("TPayload")
TPayload_co = TypeVar("TPayload_co", covariant=True)
TResult = TypeVar("TResult", bound=PromptCommandResult[object])


class PromptEditCommitSink(Protocol[TPayload]):
    """Consume the sole committed input to projection state."""

    def apply_edit_commit(self, commit: PromptEditCommit[TPayload]) -> None:
        """Apply one editing commit to projection and viewport state."""


class PromptUndoPayloadProvider(Protocol[TPayload_co]):
    """Provide passive projection values captured in undo snapshots."""

    def undo_restoration_payload(self) -> TPayload_co | None:
        """Return passive state needed to restore projection history."""

    def undo_comparison_payload(self) -> Hashable | None:
        """Return passive state that participates in undo equality."""


class PromptUndoAvailabilitySignalSink(Protocol):
    """Publish undo and redo availability transitions."""

    def emit_undo_available_changed(self, available: bool) -> None:
        """Emit one undo-availability transition."""

    def emit_redo_available_changed(self, available: bool) -> None:
        """Emit one redo-availability transition."""


class PromptPendingKeyEditBlockFlusher(Protocol):
    """Flush timer-owned key edit groups at transaction boundaries."""

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Commit any pending typing group."""

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Commit any pending typing or deletion group."""


class _NoPendingKeyEditBlockFlusher:
    """Provide inert startup behavior until composition installs coalescing."""

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Ignore a typing flush before timer composition completes."""

        _ = reason

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Ignore a key-edit flush before timer composition completes."""

        _ = reason


class PromptEditExecution(Generic[TPayload]):
    """Own edit snapshots, command execution, publication, and history lifecycle."""

    _NO_PENDING_KEY_FLUSHER = _NoPendingKeyEditBlockFlusher()

    def __init__(
        self,
        *,
        session: PromptEditingSession[TPayload],
        undo_payload_provider: PromptUndoPayloadProvider[TPayload],
        availability_signal_sink: PromptUndoAvailabilitySignalSink,
        commit_sink: PromptEditCommitSink[TPayload],
    ) -> None:
        """Bind one editing session to its passive payload and commit sinks."""

        self._session = session
        self._undo_payload_provider = undo_payload_provider
        self._availability_signal_sink = availability_signal_sink
        self._commit_sink = commit_sink
        self._pending_key_flusher: PromptPendingKeyEditBlockFlusher = (
            self._NO_PENDING_KEY_FLUSHER
        )

    @property
    def session(self) -> PromptEditingSession[TPayload]:
        """Return the authoritative editing session."""

        return self._session

    def set_pending_key_flusher(
        self,
        pending_key_flusher: PromptPendingKeyEditBlockFlusher,
    ) -> None:
        """Install timer-backed key-edit coalescing after composition."""

        self._pending_key_flusher = pending_key_flusher

    def current_undo_snapshot(self) -> PromptUndoSnapshot[TPayload]:
        """Capture source, cursor, and passive projection state exactly once."""

        source_snapshot = self._session.source_snapshot()
        return PromptUndoSnapshot(
            source_text=source_snapshot.source_text,
            cursor_state=self._session.cursor_state,
            source_revision=source_snapshot.source_revision,
            comparison_payload=self._undo_payload_provider.undo_comparison_payload(),
            restoration_payload=self._undo_payload_provider.undo_restoration_payload(),
            parenthesis_intents=source_snapshot.parenthesis_intents,
            generated_emphases=source_snapshot.generated_emphases,
        )

    def execute(
        self,
        command: PromptEditorCommand[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Execute one prepared feature command and publish its commit once."""

        result = command.execute(self._session)
        if result.edit_commit is not None:
            self.publish(result.edit_commit)
        return result

    def replace_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        normalizer: PromptSourceNormalizer,
        origin: PromptSourceEditOrigin,
        exact_source: bool,
        record_undo: bool = True,
        cursor_position: int | None = None,
        anchor_position: int | None = None,
    ) -> PromptEditCommit[TPayload]:
        """Commit and publish one source-coordinate range replacement."""

        commit = self._session.execute(
            PromptReplaceRangeEdit(
                start=start,
                end=end,
                replacement_text=replacement_text,
                normalizer=normalizer,
                origin=origin,
                exact_source=exact_source,
                record_undo=record_undo,
                undo_snapshot=self.current_undo_snapshot(),
                cursor_position=cursor_position,
                anchor_position=anchor_position,
            )
        )
        self.publish(commit)
        return commit

    def replace_document(
        self,
        *,
        text: str,
        cursor_position: int,
        anchor_position: int,
        normalizer: PromptSourceNormalizer,
        exact_source: bool,
        record_undo: bool,
        clear_history: bool,
        prepared_state: object | None = None,
    ) -> PromptEditCommit[TPayload]:
        """Commit and publish one complete prompt-source replacement."""

        commit = self._session.execute(
            PromptReplaceDocumentEdit(
                text=text,
                cursor_position=cursor_position,
                anchor_position=anchor_position,
                normalizer=normalizer,
                exact_source=exact_source,
                record_undo=record_undo,
                clear_history=clear_history,
                undo_snapshot=self.current_undo_snapshot(),
            )
        )
        if prepared_state is not None:
            commit = commit.with_prepared_state(prepared_state)
        self.publish(commit)
        return commit

    def begin_edit_block(self, *, finish_typing: bool = True) -> None:
        """Start one grouped edit transaction."""

        if finish_typing:
            self._pending_key_flusher.finish_typing_edit_block(
                reason="begin_edit_block"
            )
        self._session.begin_edit_block(self.current_undo_snapshot())

    def end_edit_block(self) -> None:
        """Finish one grouped edit transaction."""

        self._emit_availability_change(
            self._session.end_edit_block(self.current_undo_snapshot())
        )

    def finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Flush key-owned typing and deletion groups."""

        self._pending_key_flusher.finish_pending_key_edit_blocks(reason=reason)

    def begin_or_extend_typing_group(self, text: str, *, cursor_position: int) -> None:
        """Open or extend one contiguous typed-word undo group."""

        self._emit_availability_change(
            self._session.begin_or_extend_typing_group(
                text,
                cursor_position=cursor_position,
                snapshot=self.current_undo_snapshot(),
            )
        )

    def finish_typing_group(self) -> None:
        """Commit an open typed-word undo group."""

        self._emit_availability_change(
            self._session.finish_typing_group(self.current_undo_snapshot())
        )

    def begin_delete_group(self, *, key: int) -> None:
        """Open or extend one key-specific deletion undo group."""

        self._emit_availability_change(
            self._session.begin_delete_group(
                key=key,
                snapshot=self.current_undo_snapshot(),
            )
        )

    def finish_delete_group(self) -> None:
        """Commit an open Backspace/Delete undo group."""

        self._emit_availability_change(
            self._session.finish_delete_group(self.current_undo_snapshot())
        )

    def discard_trailing_undo_state(
        self,
        expected_snapshot: PromptUndoSnapshot[TPayload],
    ) -> None:
        """Discard one expected intermediate undo state."""

        self._emit_availability_change(
            self._session.discard_trailing_undo_state(expected_snapshot)
        )

    def undo(self) -> PromptEditCommit[TPayload] | None:
        """Commit and publish one undo restoration."""

        commit = self._session.execute(PromptUndoEdit(self.current_undo_snapshot()))
        if commit is not None:
            self.publish(commit)
        return commit

    def redo(self) -> PromptEditCommit[TPayload] | None:
        """Commit and publish one redo restoration."""

        commit = self._session.execute(PromptRedoEdit(self.current_undo_snapshot()))
        if commit is not None:
            self.publish(commit)
        return commit

    def publish(self, commit: PromptEditCommit[TPayload]) -> None:
        """Publish one commit and its availability transition exactly once."""

        self._emit_availability_change(commit.undo_availability_change)
        self._commit_sink.apply_edit_commit(commit)

    def _emit_availability_change(
        self,
        availability_change: PromptUndoAvailabilityChange | None,
    ) -> None:
        """Emit each undo/redo transition at the editing boundary."""

        if availability_change is None:
            return
        if availability_change.undo_changed:
            self._availability_signal_sink.emit_undo_available_changed(
                availability_change.current.can_undo
            )
        if availability_change.redo_changed:
            self._availability_signal_sink.emit_redo_available_changed(
                availability_change.current.can_redo
            )


__all__ = [
    "PromptEditCommitSink",
    "PromptEditExecution",
    "PromptPendingKeyEditBlockFlusher",
    "PromptUndoAvailabilitySignalSink",
    "PromptUndoPayloadProvider",
]
