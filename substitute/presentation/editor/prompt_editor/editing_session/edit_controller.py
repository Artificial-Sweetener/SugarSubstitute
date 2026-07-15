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

"""Own prompt edit command dispatch and projection mutation result contracts."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Protocol, TypeVar

from ..commands import (
    PromptCommandDispatcher,
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptEditorCommand,
)
from .cursor_state import PromptCursorState
from .edit_transaction import PromptUndoAvailabilityChange
from .source_edit_commands import PromptSourceEditOrigin
from .session import (
    PromptEditingSession,
    PromptEditingSessionRestoreResult,
    PromptEditingSessionSourceChange,
)
from .edit_transaction import PromptUndoSnapshot

TPayload = TypeVar("TPayload")
TPayload_co = TypeVar("TPayload_co", covariant=True)
TResult = TypeVar("TResult", covariant=True)


@dataclass(frozen=True, slots=True)
class PromptOptimisticPromptState:
    """Carry prepared semantic state that may be adopted with a source edit."""

    document_view: object
    render_plan: object


@dataclass(frozen=True, slots=True)
class PromptMutationSignalIntent:
    """Describe public signal transitions produced by an edit-controller result."""

    undo_availability_change: PromptUndoAvailabilityChange | None = None
    emit_text_changed: bool = False
    emit_cursor_position_changed: bool = False


class PromptProjectionSourceApplicationMode(Enum):
    """Identify how a committed source change should enter projection state."""

    SOURCE_REPLACEMENT = "source_replacement"
    FULL_SOURCE = "full_source"


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceChangeApplication(Generic[TPayload]):
    """Describe one committed source edit for a projection mutation sink."""

    source_change: PromptEditingSessionSourceChange[TPayload]
    previous_source_text: str
    origin: PromptSourceEditOrigin
    mode: PromptProjectionSourceApplicationMode = (
        PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT
    )
    optimistic_prompt_state: PromptOptimisticPromptState | None = None
    source_edit_start: int | None = None
    source_edit_end: int | None = None
    source_edit_replacement_text: str | None = None
    reset_scroll_to_top: bool = False
    schedule_geometry_reuse_warm_reason: str | None = None
    signal_intent: PromptMutationSignalIntent = field(
        default_factory=PromptMutationSignalIntent
    )


@dataclass(frozen=True, slots=True)
class PromptProjectionRestoreApplication(Generic[TPayload]):
    """Describe one undo/redo restore for a projection mutation sink."""

    restore_result: PromptEditingSessionRestoreResult[TPayload]
    signal_intent: PromptMutationSignalIntent = field(
        default_factory=PromptMutationSignalIntent
    )


@dataclass(frozen=True, slots=True)
class PromptEditControllerResult(Generic[TPayload, TResult]):
    """Carry command output plus projection applications without command details."""

    outcome: TResult
    source_applications: tuple[
        PromptProjectionSourceChangeApplication[TPayload]
        | PromptProjectionRestoreApplication[TPayload],
        ...,
    ] = ()


class PromptProjectionMutationSink(Protocol[TPayload]):
    """Apply committed edit-controller results without seeing command requests."""

    def apply_edit_controller_result(
        self,
        result: PromptEditControllerResult[TPayload, object],
    ) -> None:
        """Apply committed projection mutations produced by an edit controller."""


class PromptUndoPayloadProvider(Protocol[TPayload_co]):
    """Provide projection-specific payload data for controller-owned undo snapshots."""

    def undo_restoration_payload(self) -> TPayload_co | None:
        """Return passive state needed to restore the projection for undo/redo."""

    def undo_comparison_payload(self) -> Hashable | None:
        """Return passive state that participates in undo equality checks."""


class PromptUndoAvailabilitySignalSink(Protocol):
    """Emit undo/redo availability booleans without owning transition policy."""

    def emit_undo_available_changed(self, available: bool) -> None:
        """Emit an undo availability transition."""

    def emit_redo_available_changed(self, available: bool) -> None:
        """Emit a redo availability transition."""


class PromptPendingKeyEditBlockFlusher(Protocol):
    """Flush key-driven undo groups while timer ownership remains external."""

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Commit any pending typing undo group."""

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Commit any pending typing or delete undo group."""


class _NoPendingKeyEditBlockFlusher:
    """Provide inert pending-key flushing before composition wires coalescing."""

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Ignore typing flushes when no coalescing owner exists."""

        _ = reason

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Ignore pending-key flushes when no coalescing owner exists."""

        _ = reason


class PromptEditController(Generic[TPayload]):
    """Coordinate live prompt mutations around the editing-session owner."""

    _NO_PENDING_KEY_FLUSHER = _NoPendingKeyEditBlockFlusher()

    def __init__(
        self,
        *,
        session: PromptEditingSession[TPayload],
        undo_payload_provider: PromptUndoPayloadProvider[TPayload],
        availability_signal_sink: PromptUndoAvailabilitySignalSink,
        pending_key_flusher: PromptPendingKeyEditBlockFlusher | None = None,
        projection_mutation_sink: PromptProjectionMutationSink[TPayload] | None = None,
    ) -> None:
        """Create a controller for one editing session and projection sink."""

        self._session = session
        self._dispatcher = PromptCommandDispatcher(session)
        self._undo_payload_provider = undo_payload_provider
        self._availability_signal_sink = availability_signal_sink
        self._pending_key_flusher: PromptPendingKeyEditBlockFlusher | None = (
            pending_key_flusher
        )
        self._projection_mutation_sink = projection_mutation_sink

    @property
    def session(self) -> PromptEditingSession[TPayload]:
        """Return the editing session owned by this controller boundary."""

        return self._session

    def set_pending_key_flusher(
        self,
        pending_key_flusher: PromptPendingKeyEditBlockFlusher,
    ) -> None:
        """Replace pending-key flushing after composition wires its owner."""

        self._pending_key_flusher = pending_key_flusher

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the source identity used by prepared prompt commands."""

        return PromptCommandSourceIdentity(
            source_revision=self._session.source_revision,
            source_length=len(self._session.source_text),
        )

    def current_undo_snapshot(self) -> PromptUndoSnapshot[TPayload]:
        """Capture the current source, cursor, and passive projection state."""

        return PromptUndoSnapshot(
            source_text=self._session.source_text,
            cursor_state=self._session.cursor_state,
            source_revision=self._session.source_revision,
            comparison_payload=self._undo_payload_provider.undo_comparison_payload(),
            restoration_payload=self._undo_payload_provider.undo_restoration_payload(),
            parenthesis_intents=(self._session.source_snapshot().parenthesis_intents),
            generated_emphases=(self._session.source_snapshot().generated_emphases),
        )

    def execute_command(
        self,
        command: PromptEditorCommand[TPayload],
    ) -> PromptEditControllerResult[
        TPayload,
        PromptCommandResult[TPayload],
    ]:
        """Execute one command through the controller-owned dispatcher."""

        command_result = self._dispatcher.execute(command)
        source_change = command_result.source_change
        applications: tuple[PromptProjectionSourceChangeApplication[TPayload], ...] = ()
        if source_change is not None:
            applications = (
                PromptProjectionSourceChangeApplication(
                    source_change=source_change,
                    previous_source_text=source_change.previous_snapshot.source_text,
                    origin=PromptSourceEditOrigin.PROGRAMMATIC,
                    signal_intent=PromptMutationSignalIntent(
                        undo_availability_change=(
                            command_result.undo_availability_change
                        ),
                        emit_text_changed=source_change.source_changed,
                        emit_cursor_position_changed=True,
                    ),
                ),
            )
        self.emit_undo_availability_change(command_result.undo_availability_change)
        result = PromptEditControllerResult(
            outcome=command_result,
            source_applications=applications,
        )
        if self._projection_mutation_sink is not None and applications:
            self._projection_mutation_sink.apply_edit_controller_result(result)
        return result

    def dispatch_command(
        self,
        command: PromptEditorCommand[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Execute one command and return the command result for legacy callers."""

        return self._dispatcher.execute(command)

    def begin_edit_block(self, *, finish_typing: bool = True) -> None:
        """Start a grouped edit transaction with a controller-owned snapshot."""

        if finish_typing:
            self._pending_key_flushing_owner().finish_typing_edit_block(
                reason="begin_edit_block"
            )
        self._session.begin_edit_block(self.current_undo_snapshot())

    def end_edit_block(self) -> None:
        """Finish a grouped edit transaction and emit availability transitions."""

        availability_change = self._session.end_edit_block(self.current_undo_snapshot())
        self.emit_undo_availability_change(availability_change)

    def finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Flush key-driven edit groups through the current coalescing owner."""

        self._pending_key_flushing_owner().finish_pending_key_edit_blocks(reason=reason)

    def emit_undo_availability_change(
        self,
        availability_change: PromptUndoAvailabilityChange | None,
    ) -> None:
        """Emit undo/redo availability transitions exactly once per change."""

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

    def begin_or_extend_typing_group(self, text: str, *, cursor_position: int) -> None:
        """Open or extend one typed-word undo group using controller snapshots."""

        availability_change = self._session.begin_or_extend_typing_group(
            text,
            cursor_position=cursor_position,
            snapshot=self.current_undo_snapshot(),
        )
        self.emit_undo_availability_change(availability_change)

    def finish_typing_group(self) -> None:
        """Commit any open typed-word undo group."""

        availability_change = self._session.finish_typing_group(
            self.current_undo_snapshot()
        )
        self.emit_undo_availability_change(availability_change)

    def begin_delete_group(self, *, key: int) -> None:
        """Open or extend one delete-key undo group using controller snapshots."""

        availability_change = self._session.begin_delete_group(
            key=key,
            snapshot=self.current_undo_snapshot(),
        )
        self.emit_undo_availability_change(availability_change)

    def finish_delete_group(self) -> None:
        """Commit any open Backspace/Delete undo group."""

        availability_change = self._session.finish_delete_group(
            self.current_undo_snapshot()
        )
        self.emit_undo_availability_change(availability_change)

    def discard_trailing_undo_state(
        self,
        expected_snapshot: PromptUndoSnapshot[TPayload],
    ) -> None:
        """Discard one trailing undo state and emit resulting availability changes."""

        availability_change = self._session.discard_trailing_undo_state(
            expected_snapshot
        )
        self.emit_undo_availability_change(availability_change)

    def undo(self) -> PromptEditingSessionRestoreResult[TPayload] | None:
        """Restore the previous snapshot through the editing session."""

        restore_result = self._session.undo(self.current_undo_snapshot())
        if restore_result is not None:
            self.emit_undo_availability_change(restore_result.availability_change)
        return restore_result

    def redo(self) -> PromptEditingSessionRestoreResult[TPayload] | None:
        """Restore the next snapshot through the editing session."""

        restore_result = self._session.redo(self.current_undo_snapshot())
        if restore_result is not None:
            self.emit_undo_availability_change(restore_result.availability_change)
        return restore_result

    def restore_snapshot(
        self,
        snapshot: PromptUndoSnapshot[TPayload],
        *,
        cursor_state: PromptCursorState,
    ) -> None:
        """Retain a typed cursor import for future controller restore routing."""

        _ = snapshot
        _ = cursor_state

    def _pending_key_flushing_owner(self) -> PromptPendingKeyEditBlockFlusher:
        """Return the configured pending-key flusher or inert direct-surface fallback."""

        if self._pending_key_flusher is None:
            return self._NO_PENDING_KEY_FLUSHER
        return self._pending_key_flusher


__all__ = [
    "PromptEditController",
    "PromptEditControllerResult",
    "PromptMutationSignalIntent",
    "PromptOptimisticPromptState",
    "PromptPendingKeyEditBlockFlusher",
    "PromptProjectionMutationSink",
    "PromptProjectionRestoreApplication",
    "PromptProjectionSourceApplicationMode",
    "PromptProjectionSourceChangeApplication",
    "PromptUndoAvailabilitySignalSink",
    "PromptUndoPayloadProvider",
]
