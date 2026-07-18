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

"""Coordinate prehydrated workspace restore lifecycle for the shell."""

from __future__ import annotations

from typing import Any

from substitute.application.workspace_state import (
    ShellLayoutSnapshot,
    WorkspaceMaterializationService,
    WorkspaceSnapshot,
)
from substitute.presentation.shell.main_window_startup_trace import (
    snapshot_trace_fields as _snapshot_trace_fields,
)
from substitute.presentation.shell.workspace_restore_controller import (
    WorkspaceRestoreController,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("mainwindow")


class ShellPrehydratedRestoreController:
    """Own prehydrated workspace restore state and finalization flow."""

    def __init__(self, shell: Any) -> None:
        """Store the shell that exposes restore collaborators and public ports."""

        self._shell = shell

    def initialize_restore_state(self) -> None:
        """Install initial prehydrated restore state on the shell."""

        self._shell._shell_restore_lifecycle = "constructing"
        self._shell._prehydrated_workspace_snapshot = None
        self._shell._prehydrated_shell_layout = None
        self._shell._prehydrated_restore_runtime_prepared = False
        self._shell._prehydrated_restore_finalized = False
        self._shell._prehydrated_active_workflow_projection_pending = ""
        self._shell._prehydrated_settings_projection_pending = False
        self._shell._deferred_prehydrated_input_masks = []

    def begin_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Enter autosave-muted prehydration for one normalized workspace."""

        trace_mark(
            "main_window.begin_prehydrated_restore",
            **_snapshot_trace_fields(snapshot),
        )
        self._shell._shell_restore_lifecycle = "prehydrating"
        self._shell._prehydrated_workspace_snapshot = snapshot
        self._shell._prehydrated_shell_layout = None
        self._shell._prehydrated_restore_runtime_prepared = False
        self._shell._prehydrated_restore_finalized = False
        self._shell._prehydrated_active_workflow_projection_pending = ""
        self._shell._prehydrated_settings_projection_pending = False
        self._shell._deferred_prehydrated_input_masks = []

    def remember_prehydrated_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot | None,
    ) -> None:
        """Store shell layout for visible restore finalization."""

        trace_mark(
            "main_window.remember_prehydrated_shell_layout",
            shell_layout_present=snapshot is not None,
        )
        self._shell._prehydrated_shell_layout = snapshot

    def finish_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Mark prehydrated workspace state ready for visible finalization."""

        trace_mark(
            "main_window.finish_prehydrated_restore.start",
            **_snapshot_trace_fields(snapshot),
        )
        self._shell._prehydrated_workspace_snapshot = snapshot
        self._shell._initial_workspace_hydrated = True
        self._shell._shell_restore_lifecycle = "prehydrating"
        self._shell._prehydrated_restore_runtime_prepared = False
        self._shell._prehydrated_restore_finalized = False
        self._shell._prehydrated_active_workflow_projection_pending = ""
        self._shell._prehydrated_settings_projection_pending = False
        log_info(
            _LOGGER,
            "mainwindow prehydrated initial workspace",
            workflow_count=len(snapshot.workflows),
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            tab_order=snapshot.tab_order,
        )
        trace_mark("main_window.finish_prehydrated_restore.end")

    def finalize_initial_workspace_restore(
        self,
        initial_workspace: WorkspaceSnapshot | None = None,
    ) -> None:
        """Finalize visible restored surfaces after hidden prehydration."""

        trace_mark(
            "main_window.finalize_initial_workspace_restore.start",
            **_snapshot_trace_fields(initial_workspace),
        )
        if self._shell._prehydrated_workspace_snapshot is None:
            trace_mark(
                "main_window.finalize_initial_workspace_restore.fallback",
                reason="no_prehydrated_snapshot",
            )
            self._shell.workspace_restore_controller.hydrate_initial_workspace(
                initial_workspace
            )
            return
        if self._shell._prehydrated_restore_finalized:
            trace_mark(
                "main_window.finalize_initial_workspace_restore.skip",
                reason="already_finalized",
            )
            return
        if not self.prepare_initial_workspace_restore_runtime():
            self._shell.workspace_restore_controller.hydrate_initial_workspace(
                initial_workspace
            )
            return
        self.finish_initial_workspace_restore_layout()
        hydrated_snapshot = self._shell._prehydrated_workspace_snapshot
        if hydrated_snapshot is None:
            return
        trace_mark(
            "main_window.finalize_initial_workspace_restore.end",
            **_snapshot_trace_fields(hydrated_snapshot),
        )

    def materialize_prehydrated_initial_workspace(
        self,
        initial_workspace: WorkspaceSnapshot | None = None,
    ) -> bool:
        """Project a prehydrated workspace snapshot without backend runtime hydration."""

        trace_mark(
            "main_window.materialize_prehydrated_initial_workspace.start",
            **_snapshot_trace_fields(initial_workspace),
        )
        if self._shell._prehydrated_restore_finalized:
            trace_mark(
                "main_window.materialize_prehydrated_initial_workspace.skip",
                reason="already_finalized",
            )
            return True
        snapshot = initial_workspace or self._shell._prehydrated_workspace_snapshot
        if snapshot is None:
            trace_mark(
                "main_window.materialize_prehydrated_initial_workspace.skip",
                reason="no_snapshot",
            )
            return False
        try:
            self._shell._shell_restore_lifecycle = "restoring"
            with trace_span("main_window.materialize_prehydrated_initial_workspace"):
                result = WorkspaceMaterializationService().materialize(
                    snapshot,
                    ShellWorkspaceMaterializationPort(self._shell),
                )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            trace_mark(
                "main_window.materialize_prehydrated_initial_workspace.error",
                error=repr(error),
            )
            log_exception(
                _LOGGER,
                "Failed to materialize prehydrated workspace snapshot",
                error=error,
            )
            return False
        for warning in result.warnings:
            log_warning(
                _LOGGER,
                "Materialized prehydrated workspace with repair",
                repair=warning,
            )
        self._shell._prehydrated_workspace_snapshot = snapshot
        self._shell._prehydrated_active_workflow_projection_pending = ""
        self._shell._prehydrated_settings_projection_pending = False
        self._shell._prehydrated_restore_finalized = True
        self._shell._initial_workspace_hydrated = True
        trace_mark(
            "main_window.materialize_prehydrated_initial_workspace.end",
            warning_count=len(result.warnings),
            **_snapshot_trace_fields(snapshot),
        )
        return True

    def prepare_initial_workspace_restore_runtime(self) -> bool:
        """Hydrate restored workflow runtime while the shell is hidden.

        Hidden prep intentionally avoids workflow projection because projection can
        trigger widget geometry mapping before the final parent hierarchy is shown.
        """

        trace_mark("main_window.prepare_initial_workspace_restore_runtime.start")
        snapshot = self._shell._prehydrated_workspace_snapshot
        if snapshot is None:
            trace_mark(
                "main_window.prepare_initial_workspace_restore_runtime.skip",
                reason="no_prehydrated_snapshot",
            )
            return False
        if self._shell._prehydrated_restore_runtime_prepared:
            trace_mark(
                "main_window.prepare_initial_workspace_restore_runtime.skip",
                reason="already_prepared",
            )
            return True
        self._shell._shell_restore_lifecycle = "restoring"
        with trace_span("post_comfy.hidden_restore_runtime_prepare.hydrate"):
            with trace_span("main_window.finalize_initial_workspace_restore.hydrate"):
                hydrated_snapshot = self._shell.workspace_restore_controller.hydrate_restored_workspace_snapshot(
                    snapshot,
                    operation="prepare_initial_workspace_restore_runtime",
                )
        with trace_span("post_comfy.hidden_restore_runtime_prepare.install"):
            with trace_span("main_window.finalize_initial_workspace_restore.install"):
                self._shell.workspace_restore_controller.install_hydrated_prehydrated_workspace(
                    hydrated_snapshot
                )
        with trace_span("post_comfy.hidden_restore_runtime_prepare.input_masks"):
            with trace_span(
                "main_window.finalize_initial_workspace_restore.input_masks"
            ):
                self._shell.workspace_restore_image_adapter.restore_deferred_prehydrated_input_masks()
        active_workflow_id = (
            WorkspaceRestoreController.active_workflow_id_from_snapshot(
                hydrated_snapshot
            )
        )
        log_info(
            _LOGGER,
            "mainwindow finalize prehydrated workspace restore",
            active_route=hydrated_snapshot.active_route,
            active_workflow_id=hydrated_snapshot.active_workflow_id,
            resolved_active_workflow_id=active_workflow_id,
            workflow_count=len(hydrated_snapshot.workflows),
        )
        self._shell._prehydrated_active_workflow_projection_pending = active_workflow_id
        self._shell._prehydrated_settings_projection_pending = (
            hydrated_snapshot.active_route == SETTINGS_WORKSPACE_ROUTE
        )
        self._shell._prehydrated_restore_runtime_prepared = True
        trace_mark(
            "main_window.prepare_initial_workspace_restore_runtime.end",
            settings_projection_pending=(
                self._shell._prehydrated_settings_projection_pending
            ),
            **_snapshot_trace_fields(hydrated_snapshot),
        )
        return True

    def finish_initial_workspace_restore_layout(self) -> bool:
        """Project restored UI and apply shell layout after hidden runtime prep."""

        trace_mark("main_window.finish_initial_workspace_restore_layout.start")
        if self._shell._prehydrated_restore_finalized:
            trace_mark(
                "main_window.finish_initial_workspace_restore_layout.skip",
                reason="already_finalized",
            )
            return True
        if not self._shell._prehydrated_restore_runtime_prepared:
            trace_mark(
                "main_window.finish_initial_workspace_restore_layout.skip",
                reason="runtime_not_prepared",
            )
            return False
        with trace_span("post_show.restore_layout_finish"):
            self._shell._shell_restore_lifecycle = "restoring"
            if self._shell._prehydrated_active_workflow_projection_pending:
                self._shell.restore_projection_controller.project_restored_workflow(
                    self._shell._prehydrated_active_workflow_projection_pending
                )
                self._shell._prehydrated_active_workflow_projection_pending = ""
            self._shell.shell_layout_restore_controller.apply_restored_shell_layout(
                self._shell._prehydrated_shell_layout
            )
            if self._shell._prehydrated_settings_projection_pending:
                self._shell.restore_projection_controller.project_restored_settings()
                self._shell._prehydrated_settings_projection_pending = False
            self._shell._prehydrated_restore_finalized = True
        hydrated_snapshot = self._shell._prehydrated_workspace_snapshot
        trace_mark(
            "main_window.finish_initial_workspace_restore_layout.end",
            **_snapshot_trace_fields(hydrated_snapshot),
        )
        return True

    def prehydrated_restore_runtime_prepared(self) -> bool:
        """Return whether hidden prehydrated restore runtime prep has completed."""

        return bool(self._shell._prehydrated_restore_runtime_prepared)

    def prehydrated_restore_finalized(self) -> bool:
        """Return whether prehydrated restore layout finalization has completed."""

        return bool(self._shell._prehydrated_restore_finalized)

    def restore_layout_finalization_pending(self) -> bool:
        """Return whether restored shell layout still has a deferred finalizer."""

        return (
            getattr(self._shell, "_pending_restored_shell_layout", None) is not None
            and getattr(self._shell, "_shell_restore_lifecycle", "") != "running"
        )


__all__ = ["ShellPrehydratedRestoreController"]
