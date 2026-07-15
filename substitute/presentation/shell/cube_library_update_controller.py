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

"""Coordinate shell-owned Cube Library update presentation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from substitute.application.execution import TaskSubmitter
from substitute.application.cube_library import (
    CubeLibraryUpdateCoordinator,
    CubeLibraryUpdateDetectionService,
    LoadedCubeUpdateCandidate,
    LoadedCubeUpdateSelection,
)
from substitute.presentation.cube_updates import CubeUpdateModal
from substitute.presentation.shell.main_window_dependencies import (
    MainWindowDependencies,
)
from substitute.presentation.shell.workspace_cube_update_actions import (
    WorkspaceCubeUpdateActions,
    WorkspaceCubeUpdateView,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.cube_library_update_controller")


class CubeLibraryUpdateController:
    """Own live Cube Library update detection and user presentation."""

    def __init__(
        self,
        shell: Any,
        dependencies: MainWindowDependencies,
        *,
        refresh_submitter: TaskSubmitter | None,
        close_refresh_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Create update coordination, listener lifecycle, and signal wiring."""

        self._shell = shell
        self._actions = WorkspaceCubeUpdateActions(cast(WorkspaceCubeUpdateView, shell))
        self._modal_open = False
        self._close_update_submitter = close_refresh_submitter
        self.coordinator = CubeLibraryUpdateCoordinator(
            catalog_client=dependencies.cube_library_client,
            workflow_provider=lambda: self._shell.workflow_session_service.workflows,
            workflow_name_provider=self._workflow_names,
            detection_service=CubeLibraryUpdateDetectionService(),
            pending_changed=lambda _pending: (
                self._shell.cube_library_updates_pending.emit()
            ),
            automatic_selections_requested=lambda selections: (
                self._shell.cube_library_follow_latest_updates_requested.emit(
                    selections
                )
            ),
            refresh_submitter=refresh_submitter,
        )
        self._listener = dependencies.create_cube_library_event_listener(
            self.on_library_changed
        )
        self._listener_started = False
        self._listener_start_scheduled = False
        self._shutdown_requested = False
        self._shell.cube_library_updates_pending.connect(self.on_updates_pending)
        self._shell.cube_library_follow_latest_updates_requested.connect(
            self.apply_follow_latest_updates
        )
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop_listener)
            app.installEventFilter(shell)
        self._start_when_backend_ready()

    def on_library_changed(self, update: object) -> None:
        """Invalidate cube caches and route a Cube Library change event."""

        log_info(
            _LOGGER,
            "Received Cube Library change event in shell",
            catalog_revision=getattr(update, "catalog_revision", ""),
            previous_catalog_revision=getattr(update, "previous_catalog_revision", ""),
            reason=getattr(update, "reason", ""),
        )
        self._shell.cube_load_service.invalidate_catalog_cache()
        log_info(
            _LOGGER,
            "Invalidated Cube Library caches after change event",
            catalog_revision=getattr(update, "catalog_revision", ""),
            previous_catalog_revision=getattr(update, "previous_catalog_revision", ""),
            reason=getattr(update, "reason", ""),
        )
        self.coordinator.on_library_changed(cast(Any, update))

    def start_listener(self) -> None:
        """Start live update listening after MainWindow construction returns."""

        self._listener_start_scheduled = False
        listener = self._listener
        if (
            not self._shutdown_requested
            and listener is not None
            and not self._listener_started
        ):
            listener.start()
            self._listener_started = True

    def stop_listener(self) -> None:
        """Stop the background Cube Library websocket listener."""

        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._listener_start_scheduled = False
        listener = self._listener
        if listener is not None:
            listener.stop()
            self._listener_started = False
        self.coordinator.shutdown()
        if self._close_update_submitter is not None:
            self._close_update_submitter()
            self._close_update_submitter = None

    def _start_when_backend_ready(self) -> None:
        """Start immediately or wait for the shell backend-ready signal."""

        if getattr(self._shell, "_backend_state", "ready") == "ready":
            self._schedule_listener_start()
            return
        state_signal = getattr(self._shell, "backend_state_changed", None)
        connect_state = getattr(state_signal, "connect", None)
        if callable(connect_state):
            connect_state(self._on_backend_state_changed)
        else:
            self._schedule_listener_start()

    def _on_backend_state_changed(self, state: str) -> None:
        """Start the listener once the backend reaches ready state."""

        if state == "ready":
            self._schedule_listener_start()

    def _schedule_listener_start(self) -> None:
        """Schedule one delayed listener start."""

        if (
            self._shutdown_requested
            or self._listener_started
            or self._listener_start_scheduled
        ):
            return
        self._listener_start_scheduled = True
        QTimer.singleShot(0, self.start_listener)

    def on_updates_pending(self) -> None:
        """Defer pending Cube Library update prompts until focus is suitable."""

        if self._modal_open:
            return
        if self._shell_window_is_focused():
            QTimer.singleShot(250, self.present_pending_updates)

    def apply_follow_latest_updates(self, selections: object) -> None:
        """Apply automatic follow-latest updates requested by the coordinator."""

        if not isinstance(selections, tuple):
            return
        typed_selections = tuple(
            selection
            for selection in selections
            if isinstance(selection, LoadedCubeUpdateSelection)
        )
        if not typed_selections:
            return
        failures = self._actions.apply_update_selections(typed_selections)
        if failures:
            log_warning(
                _LOGGER,
                "Some automatic follow-latest Cube Library updates failed",
                failure_count=len(failures),
            )
        if len(failures) != len(typed_selections):
            self._shell.request_session_autosave()

    def present_pending_updates(self) -> None:
        """Show the pending Cube Library update modal and apply selected rows."""

        if self._modal_open:
            return
        candidates = self.coordinator.collect_pending_on_focus()
        if not candidates:
            return
        self._modal_open = True
        try:
            log_info(
                _LOGGER,
                "Presenting Cube Library update modal",
                event="frontend_update_modal_present",
                candidate_count=len(candidates),
                candidate_keys=[
                    f"{candidate.workflow_id}:{candidate.cube_alias}:{candidate.cube_id}"
                    for candidate in candidates
                ],
            )
            modal = CubeUpdateModal(
                candidates=candidates,
                available_versions_by_cube_id=(
                    self.cube_versions_for_update_candidates(candidates)
                ),
                parent=self._shell,
            )
            try:
                selections = modal.choose_update_selections()
            finally:
                modal.deleteLater()
            self.coordinator.mark_presented(candidates)
            log_info(
                _LOGGER,
                "Received Cube Library update modal choices",
                event="frontend_update_modal_choice",
                candidate_count=len(candidates),
                selected_count=len(selections),
                selected_keys=[
                    f"{selection.candidate.workflow_id}:"
                    f"{selection.candidate.cube_alias}:"
                    f"{selection.candidate.cube_id}:{selection.action.value}"
                    for selection in selections
                ],
            )
            if not selections:
                return
            failures = self._actions.apply_update_selections(selections)
            if failures:
                log_warning(
                    _LOGGER,
                    "Some selected Cube Library updates failed",
                    failure_count=len(failures),
                )
            failed = set(failures)
            resolved = tuple(
                selection.candidate
                for selection in selections
                if selection not in failed
            )
            self.coordinator.mark_resolved(resolved)
            self._shell.request_session_autosave()
        finally:
            self._modal_open = False

    def cube_versions_for_update_candidates(
        self,
        candidates: Sequence[LoadedCubeUpdateCandidate],
    ) -> dict[str, tuple[str, ...]]:
        """Return versions needed by update-modal version controls."""

        versions_by_cube_id: dict[str, tuple[str, ...]] = {}
        list_versions = getattr(
            self._shell.cube_load_service, "list_cube_versions", None
        )
        if not callable(list_versions):
            return versions_by_cube_id
        cube_ids = {candidate.cube_id for candidate in candidates if candidate.cube_id}
        for cube_id in sorted(cube_ids):
            try:
                versions_by_cube_id[cube_id] = tuple(list_versions(cube_id))
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                log_warning(
                    _LOGGER,
                    "Failed to list Cube Library versions for update modal",
                    cube_id=cube_id,
                    error=repr(error),
                )
        return versions_by_cube_id

    def queue_pending(
        self,
        candidates: Sequence[LoadedCubeUpdateCandidate],
    ) -> None:
        """Queue pending candidates discovered outside the live refresh task."""

        self.coordinator.queue_pending(candidates)

    def schedule_startup_update_check(self) -> None:
        """Check loaded cubes for version drift after startup hydration."""

        self.coordinator.refresh_async()

    def _workflow_names(self) -> dict[str, str]:
        """Return display names for currently open workflows."""

        workflows = getattr(self._shell.workflow_session_service, "workflows", {})
        if not isinstance(workflows, Mapping):
            return {}
        return {
            workflow_id: self._workflow_name(workflow_id) for workflow_id in workflows
        }

    def _workflow_name(self, workflow_id: str) -> str:
        """Return the shell workflow label without using MainWindow adapters."""

        snapshot_capture = getattr(
            self._shell,
            "session_snapshot_capture_adapter",
            None,
        )
        workflow_tab_label = getattr(snapshot_capture, "workflow_tab_label", None)
        if callable(workflow_tab_label):
            return str(workflow_tab_label(workflow_id))
        tabbar = getattr(self._shell, "workflow_tabbar", None)
        item_map = getattr(tabbar, "itemMap", {})
        if isinstance(item_map, Mapping):
            tab_item = item_map.get(workflow_id)
            text = getattr(tab_item, "text", None)
            if callable(text):
                return str(text())
        return workflow_id

    def _shell_window_is_focused(self) -> bool:
        """Return whether the shell frame that owns this view is active."""

        active_window = QApplication.activeWindow()
        return active_window is self._shell or active_window is self._shell.window()


__all__ = ["CubeLibraryUpdateController"]
