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

"""Own ordered preparation and persistence of complete session saves."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from time import monotonic
from typing import Protocol

from substitute.application.ports import SessionSnapshotRepository
from substitute.application.workspace_state.session_persistence import (
    PreparedSessionPersistence,
    SessionPersistenceParticipant,
)
from substitute.application.workspace_state.snapshot_capture_service import (
    SnapshotCapturePort,
)
from substitute.domain.session import SessionSnapshot
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("application.workspace_state.session_save_service")


class SessionCaptureServiceProtocol(Protocol):
    """Describe the live session capture boundary."""

    def capture(self, port: SnapshotCapturePort) -> SessionSnapshot:
        """Capture one immutable session snapshot."""


@dataclass(frozen=True, slots=True)
class PreparedSessionSave:
    """Carry owner-thread captures into detached ordered persistence."""

    snapshot: SessionSnapshot
    prerequisites: tuple[PreparedSessionPersistence, ...]
    reason: str
    sequence: int
    suppressed: bool


@dataclass(frozen=True, slots=True)
class SessionSaveResult:
    """Describe one successfully completed durable session save."""

    reason: str
    elapsed_ms: float
    prerequisite_count: int
    workflow_count: int
    persisted: bool
    sequence: int


class SessionSaveService:
    """Prepare live state and order writes submitted on one serial persistence lane."""

    def __init__(
        self,
        *,
        capture_service: SessionCaptureServiceProtocol,
        repository: SessionSnapshotRepository,
    ) -> None:
        """Store capture and repository owners used on one serialized lane."""

        self._capture_service = capture_service
        self._repository = repository
        self._next_sequence = count(1)
        self._persisted_sequence = 0
        self._terminal_sequence: int | None = None

    @property
    def accepts_autosave(self) -> bool:
        """Return whether normal autosaves may be prepared."""

        return self._terminal_sequence is None

    def prepare(
        self,
        port: SnapshotCapturePort,
        *,
        participants: tuple[SessionPersistenceParticipant, ...] = (),
        reason: str,
        terminal: bool = False,
    ) -> PreparedSessionSave:
        """Capture every owner-thread value needed by detached persistence."""

        _require_reason(reason)
        started_at = monotonic()
        sequence = next(self._next_sequence)
        if terminal:
            self._terminal_sequence = sequence
        suppressed = not terminal and not self.accepts_autosave
        try:
            prerequisites = tuple(
                participant.prepare_session_persistence()
                for participant in participants
            )
            snapshot = self._capture_service.capture(port)
        except Exception:
            if terminal:
                self.release_terminal(sequence)
            raise
        log_info(
            _LOGGER,
            "Session save prepared",
            reason=reason,
            elapsed_ms=_elapsed_ms(started_at),
            prerequisite_count=len(prerequisites),
            workflow_count=len(snapshot.workspace.workflows),
            sequence=sequence,
            suppressed=suppressed,
        )
        return PreparedSessionSave(
            snapshot=snapshot,
            prerequisites=prerequisites,
            reason=reason,
            sequence=sequence,
            suppressed=suppressed,
        )

    def release_terminal(self, sequence: int) -> None:
        """Resume autosaves after the matching GUI finalization settles."""

        if self._terminal_sequence == sequence:
            self._terminal_sequence = None

    def persist(self, prepared: PreparedSessionSave) -> SessionSaveResult:
        """Persist prerequisites then session JSON under one serialized boundary."""

        started_at = monotonic()
        if prepared.suppressed:
            result = self._result(
                prepared,
                started_at=started_at,
                persisted=False,
            )
            log_info(
                _LOGGER,
                "Skipped autosave prepared during terminal session finalization",
                reason=result.reason,
                sequence=result.sequence,
            )
            return result
        is_stale = prepared.sequence <= self._persisted_sequence
        if is_stale:
            result = self._result(
                prepared,
                started_at=started_at,
                persisted=False,
            )
            log_info(
                _LOGGER,
                "Skipped stale prepared session save",
                reason=result.reason,
                elapsed_ms=result.elapsed_ms,
                sequence=result.sequence,
            )
            return result
        for prerequisite in prepared.prerequisites:
            try:
                prerequisite.persist()
            except Exception as error:
                log_exception(
                    _LOGGER,
                    "Session save prerequisite persistence failed",
                    reason=prepared.reason,
                    persistence_name=prerequisite.name,
                    sequence=prepared.sequence,
                    error=error,
                )
                raise
        try:
            self._repository.save(prepared.snapshot)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Session snapshot publication failed",
                reason=prepared.reason,
                sequence=prepared.sequence,
                error=error,
            )
            raise
        self._persisted_sequence = prepared.sequence
        result = self._result(prepared, started_at=started_at, persisted=True)
        log_info(
            _LOGGER,
            "Session save persisted",
            reason=result.reason,
            elapsed_ms=result.elapsed_ms,
            prerequisite_count=result.prerequisite_count,
            workflow_count=result.workflow_count,
            sequence=result.sequence,
        )
        return result

    @staticmethod
    def _result(
        prepared: PreparedSessionSave,
        *,
        started_at: float,
        persisted: bool,
    ) -> SessionSaveResult:
        """Describe the outcome of one ordered persistence attempt."""

        return SessionSaveResult(
            reason=prepared.reason,
            elapsed_ms=_elapsed_ms(started_at),
            prerequisite_count=len(prepared.prerequisites),
            workflow_count=len(prepared.snapshot.workspace.workflows),
            persisted=persisted,
            sequence=prepared.sequence,
        )


def _elapsed_ms(started_at: float) -> float:
    """Return elapsed monotonic milliseconds."""

    return max(0.0, (monotonic() - started_at) * 1000.0)


def _require_reason(reason: str) -> None:
    """Reject anonymous persistence work."""

    if not reason.strip():
        raise ValueError("session save reason must not be blank")


__all__ = [
    "PreparedSessionSave",
    "SessionSaveResult",
    "SessionSaveService",
]
