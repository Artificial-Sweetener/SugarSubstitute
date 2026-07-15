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

"""Coordinate shell session autosave lifecycle and category policy."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QTimer

from substitute.presentation.shell.main_window_startup_trace import (
    mark_startup_milestone,
)
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveCoordinator,
    SessionAutosaveRequestCategory,
)
from substitute.presentation.shell.session_snapshot_capture_adapter import (
    snapshot_capture_adapter_for,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("presentation.shell.session_autosave_controller")
_RESIZE_AUTOSAVE_DEBOUNCE_MS = 400
_TAB_SELECTION_AUTOSAVE_DEBOUNCE_MS = 150
_MUTED_RESTORE_LIFECYCLES = {
    "constructing",
    "prehydrating",
    "restoring",
    "gui_reloading",
    "shutting_down",
}


class SessionAutosaveController:
    """Own shell autosave lifecycle policy above debounce timers."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose session state should be persisted."""

        self._shell = shell

    def force_save_session_snapshot(self) -> bool:
        """Capture and persist the current session immediately."""

        workflow_session_service = self._shell.workflow_session_service
        trace_mark(
            "main_window.force_save_session_snapshot.start",
            active_route=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_id=workflow_session_service.active_workflow_id,
            workflow_count=len(workflow_session_service.workflows),
        )
        self._log_editor_width_trace("force save session snapshot requested")
        log_info(
            _LOGGER,
            "mainwindow force save session snapshot",
            active_route=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_id=workflow_session_service.active_workflow_id,
            workflow_ids=tuple(workflow_session_service.workflows),
        )
        if self.session_autosave_muted():
            lifecycle = getattr(self._shell, "_shell_restore_lifecycle", "")
            trace_mark(
                "main_window.force_save_session_snapshot.skipped",
                reason="restore_lifecycle_muted",
                shell_restore_lifecycle=lifecycle,
            )
            log_warning(
                _LOGGER,
                "mainwindow skipped forced session snapshot while lifecycle is muted",
                active_route=getattr(self._shell, "_active_workspace_route", ""),
                active_workflow_id=workflow_session_service.active_workflow_id,
                shell_restore_lifecycle=lifecycle,
                workflow_ids=tuple(workflow_session_service.workflows),
            )
            return False
        capture_port = snapshot_capture_adapter_for(self._shell)
        with trace_span("main_window.force_save_session_snapshot.persist"):
            result = self._shell.session_autosave_service.force_save(capture_port)
        self._log_editor_width_trace(
            "force save session snapshot completed",
            save_result=result,
        )
        log_info(
            _LOGGER,
            "mainwindow force save session snapshot completed",
            result=result,
            active_route=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_id=workflow_session_service.active_workflow_id,
        )
        trace_mark("main_window.force_save_session_snapshot.end", result=result)
        return bool(result)

    def request_session_autosave(self) -> None:
        """Schedule a debounced save of the current session snapshot."""

        trace_mark(
            "main_window.session_autosave.requested",
            initial_workspace_hydrated=getattr(
                self._shell,
                "_initial_workspace_hydrated",
                False,
            ),
            shell_restore_lifecycle=getattr(
                self._shell,
                "_shell_restore_lifecycle",
                "",
            ),
        )
        self._log_editor_width_trace(
            "session autosave requested",
            initial_workspace_hydrated=getattr(
                self._shell,
                "_initial_workspace_hydrated",
                False,
            ),
        )
        if not getattr(self._shell, "_initial_workspace_hydrated", False):
            trace_mark(
                "main_window.session_autosave.skipped",
                reason="before_initial_hydration",
            )
            self._log_editor_width_trace(
                "session autosave skipped before initial hydration",
            )
            return
        if self.session_autosave_muted():
            lifecycle = getattr(self._shell, "_shell_restore_lifecycle", "")
            trace_mark(
                "main_window.session_autosave.skipped",
                reason="restore_lifecycle_muted",
                shell_restore_lifecycle=lifecycle,
            )
            self._log_editor_width_trace(
                "session autosave skipped while shell restore lifecycle is muted",
                shell_restore_lifecycle=lifecycle,
            )
            log_debug(
                _LOGGER,
                "mainwindow session autosave skipped while lifecycle muted",
                shell_restore_lifecycle=lifecycle,
            )
            return
        if not getattr(self._shell, "_startup_autosave_unmuted_marked", False):
            self._shell._startup_autosave_unmuted_marked = True
            mark_startup_milestone(
                getattr(self._shell, "_startup_timer", None),
                "first_autosave_unmuted",
            )
            trace_mark("main_window.session_autosave.first_unmuted")
        self._shell.session_autosave_service.request_save(
            snapshot_capture_adapter_for(self._shell)
        )
        self._log_editor_width_trace("session autosave enqueued")
        trace_mark("main_window.session_autosave.enqueued")

    def ensure_coordinator(self) -> SessionAutosaveCoordinator:
        """Create and expose the coordinator that owns debounce timers."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        if coordinator is None:
            coordinator = SessionAutosaveCoordinator(
                request_save=self.request_session_autosave_for_category,
                parent=self._shell if isinstance(self._shell, QObject) else None,
                timer_factory=QTimer,
                tab_selection_debounce_ms=_TAB_SELECTION_AUTOSAVE_DEBOUNCE_MS,
                resize_debounce_ms=_RESIZE_AUTOSAVE_DEBOUNCE_MS,
            )
            self._shell._session_autosave_coordinator = coordinator
        self._shell._resize_autosave_timer = coordinator.resize_timer
        self._shell._tab_selection_autosave_timer = coordinator.tab_selection_timer
        return coordinator

    def request_session_autosave_for_category(
        self,
        category: SessionAutosaveRequestCategory,
    ) -> None:
        """Run persistence policy for one settled autosave category."""

        del category
        self.request_session_autosave()

    def request_categorized_session_autosave(
        self,
        category: SessionAutosaveRequestCategory,
    ) -> None:
        """Request autosave through the coordinator when it is available."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        if coordinator is None:
            self.request_session_autosave()
            return
        coordinator.request(category)

    def connect_canvas_layout_autosave(self) -> None:
        """Connect durable floating-canvas layout changes to resize autosave."""

        layout_state_changed = getattr(
            getattr(self._shell, "canvas_tabs", None),
            "layout_state_changed",
            None,
        )
        connect_layout_state_changed = getattr(layout_state_changed, "connect", None)
        if not callable(connect_layout_state_changed):
            return
        connect_layout_state_changed(
            lambda: self.request_categorized_session_autosave(
                SessionAutosaveRequestCategory.LAYOUT_RESIZE,
            )
        )

    def request_tab_selection_autosave(self) -> None:
        """Request a debounced autosave for tab-selection intent."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        if coordinator is None:
            timer = getattr(self._shell, "_tab_selection_autosave_timer", None)
            if timer is not None:
                timer.start(_TAB_SELECTION_AUTOSAVE_DEBOUNCE_MS)
                return
            self.request_session_autosave()
            return
        coordinator.request(SessionAutosaveRequestCategory.TAB_SELECTION)

    def run_tab_selection_autosave(self) -> None:
        """Persist a session snapshot after tab selection settles."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        if coordinator is None:
            self.request_session_autosave()
            return
        coordinator.flush_tab_selection()

    def request_resize_autosave(self) -> None:
        """Request a debounced autosave for layout-resize intent."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        if coordinator is None:
            timer = getattr(self._shell, "_resize_autosave_timer", None)
            if timer is not None:
                timer.start(_RESIZE_AUTOSAVE_DEBOUNCE_MS)
                return
            self.request_session_autosave()
            return
        coordinator.request(SessionAutosaveRequestCategory.LAYOUT_RESIZE)

    def run_resize_autosave(self) -> None:
        """Persist a session snapshot after resize activity settles."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        if coordinator is None:
            self.request_session_autosave()
            return
        coordinator.flush_resize()

    def session_autosave_muted(self) -> bool:
        """Return whether programmatic restore should suppress autosave callbacks."""

        return (
            getattr(self._shell, "_shell_restore_lifecycle", "running")
            in _MUTED_RESTORE_LIFECYCLES
        )

    def _log_editor_width_trace(self, event: str, **context: object) -> None:
        """Log through the shell layout controller when it is present."""

        controller = getattr(self._shell, "shell_layout_controller", None)
        log_editor_width_trace = getattr(controller, "log_editor_width_trace", None)
        if callable(log_editor_width_trace):
            log_editor_width_trace(event, **context)


__all__ = [
    "SessionAutosaveController",
    "_RESIZE_AUTOSAVE_DEBOUNCE_MS",
    "_TAB_SELECTION_AUTOSAVE_DEBOUNCE_MS",
]
