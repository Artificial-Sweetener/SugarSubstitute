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

"""Coordinate debounced and forced session snapshot persistence."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Protocol

from substitute.application.ports import SessionSnapshotRepository
from substitute.application.workspace_state.snapshot_capture_service import (
    SnapshotCapturePort,
)
from substitute.domain.session import SessionSnapshot
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
)

_LOGGER = get_logger("application.workspace_state.session_autosave_service")


class SessionCaptureServiceProtocol(Protocol):
    """Describe the capture surface consumed by autosave."""

    def capture(self, port: SnapshotCapturePort) -> SessionSnapshot:
        """Capture one session snapshot from a live port."""


class SessionAutosaveService:
    """Capture and persist workspace sessions without crashing interaction."""

    def __init__(
        self,
        *,
        capture_service: SessionCaptureServiceProtocol,
        repository: SessionSnapshotRepository,
        schedule_debounced: Callable[[Callable[[], None]], None] | None = None,
        schedule_persistence: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        """Store capture and persistence dependencies."""

        self._capture_service = capture_service
        self._repository = repository
        self._schedule_debounced = schedule_debounced or (lambda callback: callback())
        self._schedule_persistence = schedule_persistence or (
            lambda callback: callback()
        )
        self._save_pending = False
        self._save_running = False

    def request_save(self, port: SnapshotCapturePort) -> None:
        """Schedule a debounced save when no save is already pending."""

        log_debug(
            _LOGGER,
            "session autosave requested",
            save_pending=self._save_pending,
            save_running=self._save_running,
            port_type=type(port).__name__,
        )
        if self._save_pending:
            return
        self._save_pending = True
        scheduled_at = perf_counter()
        self._schedule_debounced(
            lambda: self._run_scheduled_save(port, scheduled_at=scheduled_at)
        )

    def force_save(self, port: SnapshotCapturePort) -> bool:
        """Capture and persist immediately, returning whether save succeeded."""

        log_info(
            _LOGGER,
            "session autosave force save requested",
            save_pending=self._save_pending,
            save_running=self._save_running,
            port_type=type(port).__name__,
        )
        return self._save_now(port, forced=True)

    def _run_scheduled_save(
        self,
        port: SnapshotCapturePort,
        *,
        scheduled_at: float,
    ) -> None:
        """Run one previously scheduled autosave."""

        self._save_pending = False
        self._save_now(port, forced=False)

    def _save_now(self, port: SnapshotCapturePort, *, forced: bool) -> bool:
        """Capture and save once while suppressing overlapping writes."""

        if self._save_running:
            log_debug(
                _LOGGER,
                "session autosave skipped overlapping save",
                forced=forced,
            )
            return False
        self._save_running = True
        try:
            log_debug(
                _LOGGER,
                "session autosave capture starting",
                forced=forced,
                port_type=type(port).__name__,
            )
            snapshot = self._capture_service.capture(port)
            shell_layout = snapshot.workspace.shell_layout
            log_debug(
                _LOGGER,
                "session autosave captured shell layout",
                forced=forced,
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
                forced=forced,
                active_route=snapshot.workspace.active_route,
                active_workflow_id=snapshot.workspace.active_workflow_id,
                tab_order=snapshot.workspace.tab_order,
                workflow_count=len(snapshot.workspace.workflows),
            )
            log_debug(
                _LOGGER,
                "session autosave repository save starting",
                forced=forced,
            )
            if forced:
                self._persist_snapshot(snapshot, forced=forced)
            else:

                def persist_captured_snapshot() -> None:
                    """Persist the captured snapshot outside the UI-critical path."""

                    self._persist_snapshot(snapshot, forced=forced)

                self._schedule_persistence(persist_captured_snapshot)
        except Exception as error:
            self._save_running = False
            log_exception(
                _LOGGER,
                "Failed to save session snapshot",
                forced=forced,
                error=error,
            )
            return False
        log_debug(
            _LOGGER,
            "Queued session snapshot persistence",
            forced=forced,
            captured_at=snapshot.captured_at.isoformat(),
            workflow_count=len(snapshot.workspace.workflows),
        )
        return True

    def _persist_snapshot(self, snapshot: SessionSnapshot, *, forced: bool) -> None:
        """Persist a captured snapshot and release the save-running guard."""

        try:
            self._repository.save(snapshot)
            log_debug(
                _LOGGER,
                "session autosave repository save completed",
                forced=forced,
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to persist session snapshot",
                forced=forced,
                error=error,
            )
        finally:
            self._save_running = False
        log_debug(
            _LOGGER,
            "Saved session snapshot",
            forced=forced,
            captured_at=snapshot.captured_at.isoformat(),
            workflow_count=len(snapshot.workspace.workflows),
        )


__all__ = ["SessionAutosaveService"]
