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

"""Coordinate debounced session snapshot persistence."""

from __future__ import annotations

from collections.abc import Callable
from threading import Condition, Lock

from substitute.application.workspace_state.session_persistence import (
    SessionPersistenceParticipant,
)
from substitute.application.workspace_state.session_save_service import (
    PreparedSessionSave,
    SessionSaveService,
)
from substitute.application.workspace_state.snapshot_capture_service import (
    SnapshotCapturePort,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
)

_LOGGER = get_logger("application.workspace_state.session_autosave_service")


class SessionAutosaveService:
    """Capture and persist workspace sessions without crashing interaction."""

    def __init__(
        self,
        *,
        save_service: SessionSaveService,
        schedule_debounced: Callable[[Callable[[], None]], None] | None = None,
        schedule_persistence: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        """Store capture and persistence dependencies."""

        self._save_service = save_service
        self._schedule_debounced = schedule_debounced or (lambda callback: callback())
        self._schedule_persistence = schedule_persistence or (
            lambda callback: callback()
        )
        self._state_lock = Lock()
        self._save_condition = Condition(self._state_lock)
        self._save_pending = False
        self._save_running = False
        self._request_generation = 0

    def save_durably(
        self,
        port: SnapshotCapturePort,
        *,
        participants: tuple[SessionPersistenceParticipant, ...] = (),
        reason: str,
        timeout_seconds: float = 30.0,
    ) -> bool:
        """Capture and persist synchronously before a destructive or remote action."""

        with self._save_condition:
            available = self._save_condition.wait_for(
                lambda: not self._save_running,
                timeout=timeout_seconds,
            )
            if not available or not self._save_service.accepts_autosave:
                return False
            self._save_running = True
        try:
            prepared = self._save_service.prepare(
                port,
                participants=participants,
                reason=reason,
            )
            self._save_service.persist(prepared)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to persist required session snapshot",
                reason=reason,
                error=error,
            )
            return False
        finally:
            self._finish_save()
        return True

    def request_save(
        self,
        port: SnapshotCapturePort,
        *,
        participants: tuple[SessionPersistenceParticipant, ...] = (),
    ) -> None:
        """Schedule a debounced save when no save is already pending."""

        if not self._save_service.accepts_autosave:
            log_debug(_LOGGER, "session autosave ignored during finalization")
            return

        with self._state_lock:
            self._request_generation += 1
            request_generation = self._request_generation
            save_pending = self._save_pending
            save_running = self._save_running
            if not save_pending:
                self._save_pending = True
        log_debug(
            _LOGGER,
            "session autosave requested",
            save_pending=save_pending,
            save_running=save_running,
            port_type=type(port).__name__,
        )
        if save_pending:
            return
        self._schedule_debounced(
            lambda: self._run_scheduled_save(
                port,
                participants=participants,
                request_generation=request_generation,
            )
        )

    def _run_scheduled_save(
        self,
        port: SnapshotCapturePort,
        *,
        participants: tuple[SessionPersistenceParticipant, ...],
        request_generation: int,
    ) -> None:
        """Run one previously scheduled autosave."""

        with self._state_lock:
            save_running = self._save_running
            latest_generation = self._request_generation
            request_is_current = request_generation == latest_generation
            if not save_running and request_is_current:
                self._save_pending = False
        if save_running or not request_is_current:
            self._schedule_debounced(
                lambda: self._run_scheduled_save(
                    port,
                    participants=participants,
                    request_generation=latest_generation,
                )
            )
            return
        self._save_now(port, participants=participants)

    def _save_now(
        self,
        port: SnapshotCapturePort,
        *,
        participants: tuple[SessionPersistenceParticipant, ...],
    ) -> bool:
        """Capture and save once while suppressing overlapping writes."""

        if not self._save_service.accepts_autosave:
            with self._state_lock:
                self._save_pending = False
            log_debug(_LOGGER, "session autosave skipped during finalization")
            return False

        with self._state_lock:
            save_running = self._save_running
            if not save_running:
                self._save_running = True
        if save_running:
            log_debug(
                _LOGGER,
                "session autosave skipped overlapping save",
            )
            return False
        try:
            log_debug(
                _LOGGER,
                "session autosave capture starting",
                port_type=type(port).__name__,
            )
            prepared = self._save_service.prepare(
                port,
                participants=participants,
                reason="autosave",
            )
            snapshot = prepared.snapshot
            shell_layout = snapshot.workspace.shell_layout
            log_debug(
                _LOGGER,
                "session autosave captured shell layout",
                active_route=snapshot.workspace.active_route,
                active_workflow_id=snapshot.workspace.active_workflow_id,
                shell_layout_present=shell_layout is not None,
                captured_main_splitter_sizes=tuple(shell_layout.main_splitter_sizes)
                if shell_layout is not None
                else (),
                captured_editor_output_splitter_sizes=tuple(
                    shell_layout.editor_output_splitter_sizes
                )
                if shell_layout is not None
                else (),
                captured_cube_stack_compact=shell_layout.cube_stack_compact
                if shell_layout is not None
                else None,
                captured_cube_stack_width=shell_layout.cube_stack_width
                if shell_layout is not None
                else None,
                captured_editor_panel_width=shell_layout.editor_panel_width
                if shell_layout is not None
                else None,
                captured_canvas_panel_width=shell_layout.canvas_panel_width
                if shell_layout is not None
                else None,
            )
            log_debug(
                _LOGGER,
                "session autosave captured snapshot",
                active_route=snapshot.workspace.active_route,
                active_workflow_id=snapshot.workspace.active_workflow_id,
                tab_order=snapshot.workspace.tab_order,
                workflow_count=len(snapshot.workspace.workflows),
            )
            log_debug(
                _LOGGER,
                "session autosave repository save starting",
            )

            def persist_captured_snapshot() -> None:
                """Persist the captured snapshot outside the UI-critical path."""

                self._persist_snapshot(prepared)

            self._schedule_persistence(persist_captured_snapshot)
        except Exception as error:
            self._finish_save()
            log_exception(
                _LOGGER,
                "Failed to save session snapshot",
                error=error,
            )
            return False
        log_debug(
            _LOGGER,
            "Queued session snapshot persistence",
            captured_at=snapshot.captured_at.isoformat(),
            workflow_count=len(snapshot.workspace.workflows),
        )
        return True

    def _persist_snapshot(
        self,
        prepared: PreparedSessionSave,
    ) -> bool:
        """Persist a captured snapshot and report complete write success."""

        succeeded = False
        try:
            result = self._save_service.persist(prepared)
            succeeded = True
            log_debug(
                _LOGGER,
                "session autosave repository save completed",
                elapsed_ms=result.elapsed_ms,
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to persist session snapshot",
                reason=prepared.reason,
                error=error,
            )
        finally:
            self._finish_save()
        if not succeeded:
            return False
        if result.persisted:
            log_debug(
                _LOGGER,
                "Saved session snapshot",
                captured_at=prepared.snapshot.captured_at.isoformat(),
                workflow_count=len(prepared.snapshot.workspace.workflows),
                sequence=result.sequence,
            )
        else:
            log_debug(
                _LOGGER,
                "Skipped stale session autosave",
                sequence=result.sequence,
            )
        return True

    def _finish_save(self) -> None:
        """Release the cross-thread persistence guard atomically."""
        with self._save_condition:
            self._save_running = False
            self._save_condition.notify_all()


__all__ = ["SessionAutosaveService"]
