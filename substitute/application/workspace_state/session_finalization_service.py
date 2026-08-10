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

"""Coordinate terminal session saves for shutdown and GUI reload."""

from __future__ import annotations

from enum import Enum
from itertools import count

from substitute.application.execution import (
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.workspace_state.session_persistence import (
    SessionPersistenceParticipant,
)
from substitute.application.workspace_state.session_save_service import (
    PreparedSessionSave,
    SessionSaveResult,
    SessionSaveService,
)
from substitute.application.workspace_state.snapshot_capture_service import (
    SnapshotCapturePort,
)


class SessionFinalizationReason(str, Enum):
    """Name the terminal workflow requiring a durable session save."""

    SHUTDOWN = "shutdown"
    GUI_RELOAD = "gui_reload"


class SessionFinalizationService:
    """Prepare terminal state on its owner and persist it on an execution lane."""

    def __init__(
        self,
        *,
        save_service: SessionSaveService,
        submitter: TaskSubmitter,
    ) -> None:
        """Store the authoritative save service and detached execution boundary."""

        self._save_service = save_service
        self._scope = TaskScope(
            submitter=submitter,
            scope_id="session_finalization",
        )
        self._request_ids = count(1)

    def prepare(
        self,
        port: SnapshotCapturePort,
        *,
        participants: tuple[SessionPersistenceParticipant, ...],
        reason: SessionFinalizationReason,
    ) -> PreparedSessionSave:
        """Capture one terminal save without performing file I/O."""

        return self._save_service.prepare(
            port,
            participants=participants,
            reason=reason.value,
            terminal=True,
        )

    def persist(self, prepared: PreparedSessionSave) -> SessionSaveResult:
        """Persist one prepared terminal save through the shared ordering owner."""

        return self._save_service.persist(prepared)

    def begin(
        self,
        port: SnapshotCapturePort,
        *,
        participants: tuple[SessionPersistenceParticipant, ...],
        reason: SessionFinalizationReason,
    ) -> TaskHandle[SessionSaveResult]:
        """Prepare immediately and submit detached terminal persistence."""

        prepared = self.prepare(
            port,
            participants=participants,
            reason=reason,
        )
        try:
            handle = self._scope.submit(
                TaskRequest(
                    identity=TaskIdentity(
                        request_id=next(self._request_ids),
                        domain="session_finalization",
                        parts=(("reason", reason.value),),
                    ),
                    context=ExecutionContext(
                        operation="session_finalization",
                        reason=reason.value,
                        lane="disk_io_low_priority",
                    ),
                    work=lambda _token: self.persist(prepared),
                )
            )
        except Exception:
            self._save_service.release_terminal(prepared.sequence)
            raise
        if reason is SessionFinalizationReason.GUI_RELOAD:
            handle.add_done_callback(
                lambda _outcome: self._save_service.release_terminal(prepared.sequence),
                reason="session_finalization_terminal_released",
            )
        return handle


__all__ = [
    "SessionFinalizationReason",
    "SessionFinalizationService",
]
