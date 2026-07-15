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

"""Coordinate initial workspace restore for the shell."""

from __future__ import annotations

from typing import Any

from substitute.application.cube_library import CubeLibraryUpdateDetectionService
from substitute.application.ports import CubeCatalogRecord, CubeCatalogSnapshot
from substitute.application.workspace_state import (
    SnapshotNormalizationService,
    WorkspaceMaterializationService,
    WorkspacePrehydrationService,
    WorkspaceRuntimeHydrationService,
    WorkspaceSnapshot,
)
from substitute.domain.cube_library import (
    CubeCatalog,
    CubeCatalogEntry,
    CubeSourceMetadata,
)
from substitute.presentation.cube_updates import CubeUpdateModal
from substitute.presentation.shell.main_window_startup_trace import (
    mark_startup_milestone,
    snapshot_trace_fields,
    startup_phase,
)
from substitute.presentation.shell.initial_workspace_controller import (
    initial_workspace_controller_for,
)
from substitute.presentation.shell.restore_projection_controller import (
    restore_projection_controller_for,
)
from substitute.presentation.shell.shell_workspace_prehydration_port import (
    ShellWorkspacePrehydrationPort,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("presentation.shell.workspace_restore_controller")


class WorkspaceRestoreController:
    """Own initial workspace restore orchestration for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose workspace should be restored."""

        self._shell = shell

    def prehydrate_initial_workspace(
        self,
        initial_workspace: WorkspaceSnapshot | None,
    ) -> bool:
        """Prepare safe restored workspace chrome before the shell is visible."""

        trace_mark(
            "main_window.prehydrate_initial_workspace.start",
            **snapshot_trace_fields(initial_workspace),
        )
        if self._shell._initial_workspace_hydrated or initial_workspace is None:
            trace_mark(
                "main_window.prehydrate_initial_workspace.skip",
                reason="already_hydrated"
                if self._shell._initial_workspace_hydrated
                else "no_initial_workspace",
            )
            return False
        try:
            with trace_span(
                "main_window.prehydrate_initial_workspace.service",
                **snapshot_trace_fields(initial_workspace),
            ):
                WorkspacePrehydrationService().prehydrate(
                    initial_workspace,
                    ShellWorkspacePrehydrationPort(self._shell),
                )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._reset_failed_prehydration_state()
            log_exception(
                _LOGGER,
                "Failed to prehydrate session snapshot; falling back to visible hydration",
                error=error,
            )
            return False
        trace_mark("main_window.prehydrate_initial_workspace.end")
        return True

    def hydrate_initial_workspace(
        self,
        initial_workspace: WorkspaceSnapshot | None = None,
    ) -> None:
        """Create and hydrate the first workflow surface when startup schedules it."""

        trace_mark(
            "main_window.hydrate_initial_workspace.start",
            **snapshot_trace_fields(initial_workspace),
        )
        if self._shell._initial_workspace_hydrated:
            trace_mark(
                "main_window.hydrate_initial_workspace.skip",
                reason="already_hydrated",
            )
            return
        self._shell._initial_workspace_hydrated = True
        with startup_phase(
            getattr(self._shell, "_startup_timer", None),
            "mainwindow.initialize_initial_workspace",
        ):
            if (
                initial_workspace is not None
                and self.restore_initial_workspace_snapshot(initial_workspace)
            ):
                trace_mark(
                    "main_window.hydrate_initial_workspace.end",
                    restore_path="provided_snapshot",
                )
                self._schedule_startup_update_check()
                return
            if (
                initial_workspace is None
                and self.restore_initial_workspace_from_session()
            ):
                trace_mark(
                    "main_window.hydrate_initial_workspace.end",
                    restore_path="session_snapshot",
                )
                self._schedule_startup_update_check()
                return
            initial_workspace_controller_for(self._shell).initialize_initial_workspace()
            self._shell._shell_restore_lifecycle = "running"
            mark_startup_milestone(
                getattr(self._shell, "_startup_timer", None),
                "restore_lifecycle_running",
            )
        trace_mark("main_window.hydrate_initial_workspace.end", restore_path="blank")
        self._schedule_startup_update_check()

    def restore_initial_workspace_from_session(self) -> bool:
        """Load, normalize, and materialize the last session when available."""

        trace_mark("main_window.restore_initial_workspace_from_session.start")
        log_info(
            _LOGGER,
            "mainwindow session restore started",
            existing_active_route=getattr(self._shell, "_active_workspace_route", ""),
            existing_active_workflow_id=getattr(
                self._shell.workflow_session_service,
                "active_workflow_id",
                "",
            ),
        )
        try:
            session_snapshot = self._shell.session_snapshot_repository.load()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            trace_mark(
                "main_window.restore_initial_workspace_from_session.error",
                error=repr(error),
            )
            log_exception(
                _LOGGER,
                "Failed to load session snapshot during startup restore",
                error=error,
            )
            return False
        if session_snapshot is None:
            trace_mark(
                "main_window.restore_initial_workspace_from_session.skip",
                reason="no_snapshot",
            )
            log_info(
                _LOGGER,
                "mainwindow session restore skipped no snapshot",
            )
            return False
        log_info(
            _LOGGER,
            "mainwindow session restore loaded snapshot",
            captured_at=session_snapshot.captured_at.isoformat(),
            active_route=session_snapshot.workspace.active_route,
            active_workflow_id=session_snapshot.workspace.active_workflow_id,
            tab_order=session_snapshot.workspace.tab_order,
            workflow_count=len(session_snapshot.workspace.workflows),
        )
        try:
            self._shell._shell_restore_lifecycle = "restoring"
            normalization = SnapshotNormalizationService().normalize(
                session_snapshot.workspace
            )
            log_info(
                _LOGGER,
                "mainwindow session restore normalized snapshot",
                active_route=normalization.snapshot.active_route,
                active_workflow_id=normalization.snapshot.active_workflow_id,
                tab_order=normalization.snapshot.tab_order,
                warning_count=len(normalization.warnings),
            )
            return self.restore_initial_workspace_snapshot(
                normalization.snapshot,
                captured_at=session_snapshot.captured_at.isoformat(),
                normalization_warnings=normalization.warnings,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            trace_mark(
                "main_window.restore_initial_workspace_from_session.error",
                error=repr(error),
            )
            log_exception(
                _LOGGER,
                "Failed to restore session snapshot; falling back to blank workspace",
                error=error,
            )
            return False

    def restore_initial_workspace_snapshot(
        self,
        snapshot: WorkspaceSnapshot,
        *,
        captured_at: str | None = None,
        normalization_warnings: tuple[str, ...] = (),
    ) -> bool:
        """Materialize one normalized workspace snapshot into the shell."""

        trace_mark(
            "main_window.restore_initial_workspace_snapshot.start",
            captured_at=captured_at or "",
            normalization_warning_count=len(normalization_warnings),
            **snapshot_trace_fields(snapshot),
        )
        try:
            self._shell._shell_restore_lifecycle = "restoring"
            with trace_span("main_window.restore_initial_workspace_snapshot.hydrate"):
                hydrated_snapshot = self.hydrate_restored_workspace_snapshot(
                    snapshot,
                    operation="restore_initial_workspace_snapshot",
                )
            with trace_span(
                "main_window.restore_initial_workspace_snapshot.materialize"
            ):
                restore_result = WorkspaceMaterializationService().materialize(
                    hydrated_snapshot,
                    ShellWorkspaceMaterializationPort(self._shell),
                )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            trace_mark(
                "main_window.restore_initial_workspace_snapshot.error",
                error=repr(error),
            )
            log_exception(
                _LOGGER,
                "Failed to restore session snapshot; falling back to blank workspace",
                error=error,
            )
            return False
        log_info(
            _LOGGER,
            "Restored initial workspace from session snapshot",
            captured_at=captured_at or "",
            workflow_count=len(hydrated_snapshot.workflows),
            normalization_warning_count=len(normalization_warnings),
            restore_warning_count=len(restore_result.warnings),
        )
        if getattr(self._shell, "_pending_restored_shell_layout", None) is None:
            self._shell._shell_restore_lifecycle = "running"
            mark_startup_milestone(
                getattr(self._shell, "_startup_timer", None),
                "restore_lifecycle_running",
            )
            restore_projection_controller_for(
                self._shell
            ).maybe_capture_restore_projection_cache()
        trace_mark(
            "main_window.restore_initial_workspace_snapshot.end",
            restore_warning_count=len(restore_result.warnings),
            **snapshot_trace_fields(hydrated_snapshot),
        )
        return True

    def hydrate_restored_workspace_snapshot(
        self,
        snapshot: WorkspaceSnapshot,
        *,
        operation: str,
    ) -> WorkspaceSnapshot:
        """Return a restored snapshot rebuilt through normal cube runtime rules."""

        preserve_cube_keys = self.restore_update_preserve_keys(snapshot)
        trace_mark(
            "main_window.hydrate_restored_workspace_snapshot.start",
            operation=operation,
            **snapshot_trace_fields(snapshot),
        )
        with trace_span(
            "main_window.hydrate_restored_workspace_snapshot.service",
            operation=operation,
        ):
            hydration = WorkspaceRuntimeHydrationService(
                cube_load_service=self._shell.cube_load_service,
                node_behavior_service=self._shell.node_behavior_service,
                preserve_cube_keys=preserve_cube_keys,
            ).hydrate(snapshot)
        for warning in hydration.warnings:
            log_warning(
                _LOGGER,
                "Hydrated restored workspace with repair",
                operation=operation,
                repair=warning,
            )
        trace_mark(
            "main_window.hydrate_restored_workspace_snapshot.end",
            operation=operation,
            warning_count=len(hydration.warnings),
            **snapshot_trace_fields(hydration.snapshot),
        )
        return hydration.snapshot

    def restore_update_preserve_keys(
        self,
        snapshot: WorkspaceSnapshot,
    ) -> frozenset[tuple[str, str]]:
        """Ask which stale restored cubes should keep embedded snapshot state."""

        catalog = self._cached_restore_update_catalog()
        if catalog is None:
            return frozenset()
        workflows = {
            workflow.workflow_id: workflow.workflow for workflow in snapshot.workflows
        }
        workflow_names = {
            workflow.workflow_id: workflow.tab_label for workflow in snapshot.workflows
        }
        candidates = CubeLibraryUpdateDetectionService().detect_updates(
            workflows=workflows,
            workflow_names=workflow_names,
            catalog=catalog,
        )
        if not candidates:
            return frozenset()
        if not self._shell.isVisible():
            self._shell.cube_library_update_controller.queue_pending(candidates)
            return frozenset(
                (candidate.workflow_id, candidate.cube_alias)
                for candidate in candidates
            )
        modal = CubeUpdateModal(
            candidates=candidates,
            available_versions_by_cube_id=(
                self._shell.cube_library_update_controller.cube_versions_for_update_candidates(
                    candidates
                )
            ),
            parent=self._shell,
        )
        try:
            selections = modal.choose_update_selections()
        finally:
            modal.deleteLater()
        selected_keys = {
            (selection.candidate.workflow_id, selection.candidate.cube_alias)
            for selection in selections
            if selection.action.value != "keep_pinned"
        }
        return frozenset(
            (candidate.workflow_id, candidate.cube_alias)
            for candidate in candidates
            if (candidate.workflow_id, candidate.cube_alias) not in selected_keys
        )

    def _cached_restore_update_catalog(self) -> CubeCatalog | None:
        """Return cached catalog data for non-blocking restore update detection."""

        cube_load_service = getattr(self._shell, "cube_load_service", None)
        picker_catalog_snapshot = getattr(
            cube_load_service,
            "picker_catalog_snapshot",
            None,
        )
        if not callable(picker_catalog_snapshot):
            log_warning(
                _LOGGER,
                "Skipped restore update detection because cached catalog access is unavailable",
            )
            return None
        try:
            snapshot = picker_catalog_snapshot()
        except Exception as error:
            log_warning(
                _LOGGER,
                "Skipped restore update detection after cached catalog read failed",
                error=repr(error),
            )
            return None
        if not isinstance(snapshot, CubeCatalogSnapshot):
            log_warning(
                _LOGGER,
                "Skipped restore update detection after invalid cached catalog snapshot",
                snapshot_type=type(snapshot).__name__,
            )
            return None
        if snapshot.state not in {"fresh", "stale"}:
            log_info(
                _LOGGER,
                "Deferred restore update detection until post-startup catalog refresh",
                catalog_state=snapshot.state,
                cube_count=len(snapshot.entries),
            )
            return None
        log_info(
            _LOGGER,
            "Using cached catalog for restore update detection",
            catalog_state=snapshot.state,
            cube_count=len(snapshot.entries),
            catalog_revision=snapshot.catalog_revision,
        )
        return _catalog_from_picker_snapshot(snapshot)

    def install_hydrated_prehydrated_workspace(
        self,
        snapshot: WorkspaceSnapshot,
    ) -> None:
        """Replace prehydrated raw workflow state with hydrated runtime state."""

        trace_mark(
            "main_window.install_hydrated_prehydrated_workspace.start",
            **snapshot_trace_fields(snapshot),
        )
        workflows_by_id = {
            workflow.workflow_id: workflow.workflow for workflow in snapshot.workflows
        }
        active_workflow_id = self.active_workflow_id_from_snapshot(snapshot)
        self._shell.workflow_session_service.replace_workflows(
            workflows_by_id,
            active_workflow_id=active_workflow_id,
        )
        self._shell._pending_restored_workflow_snapshots = {
            workflow.workflow_id: workflow for workflow in snapshot.workflows
        }
        self._shell._restored_workflow_snapshots_by_id = dict(
            self._shell._pending_restored_workflow_snapshots
        )
        self._shell._prehydrated_workspace_snapshot = snapshot
        trace_mark(
            "main_window.install_hydrated_prehydrated_workspace.end",
            workflow_count=len(workflows_by_id),
            active_workflow_id=active_workflow_id,
        )

    @staticmethod
    def active_workflow_id_from_snapshot(snapshot: WorkspaceSnapshot) -> str:
        """Return the active workflow id from a normalized workspace snapshot."""

        if snapshot.active_workflow_id in snapshot.tab_order:
            return snapshot.active_workflow_id
        return (
            snapshot.active_route if snapshot.active_route in snapshot.tab_order else ""
        )

    def _reset_failed_prehydration_state(self) -> None:
        """Reset shell fields after prehydration fails."""

        self._shell._prehydrated_workspace_snapshot = None
        self._shell._prehydrated_shell_layout = None
        self._shell._prehydrated_restore_runtime_prepared = False
        self._shell._prehydrated_restore_finalized = False
        self._shell._prehydrated_active_workflow_projection_pending = ""
        self._shell._prehydrated_settings_projection_pending = False
        self._shell._deferred_prehydrated_input_masks = []
        self._shell._shell_restore_lifecycle = "constructing"

    def _schedule_startup_update_check(self) -> None:
        """Schedule the cube-library startup update check when available."""

        controller = getattr(self._shell, "cube_library_update_controller", None)
        schedule = getattr(controller, "schedule_startup_update_check", None)
        if callable(schedule):
            schedule()
            return
        legacy_schedule = getattr(
            self._shell,
            "_schedule_cube_library_startup_update_check",
            None,
        )
        if callable(legacy_schedule):
            legacy_schedule()


def workspace_restore_controller_for(shell: Any) -> WorkspaceRestoreController:
    """Return the composed workspace restore controller for a shell."""

    controller = getattr(shell, "workspace_restore_controller", None)
    if isinstance(controller, WorkspaceRestoreController):
        return controller
    controller = WorkspaceRestoreController(shell)
    setattr(shell, "workspace_restore_controller", controller)
    return controller


def _catalog_from_picker_snapshot(snapshot: CubeCatalogSnapshot) -> CubeCatalog:
    """Convert picker cache records into the update-detection catalog model."""

    return CubeCatalog(
        schema_version=1,
        catalog_revision=snapshot.catalog_revision,
        generated_at="",
        cubes=tuple(_catalog_entry_from_record(record) for record in snapshot.entries),
    )


def _catalog_entry_from_record(record: CubeCatalogRecord) -> CubeCatalogEntry:
    """Convert one picker catalog record into a domain catalog entry."""

    return CubeCatalogEntry(
        cube_id=record.cube_id,
        version=record.version,
        display_name=record.display_name,
        description=record.description,
        source=record.source or CubeSourceMetadata(kind="", path=""),
        content_hash=record.content_hash,
        updated_at=record.updated_at,
        supported_models=record.supported_models,
        icon=record.icon,
    )


__all__ = [
    "WorkspaceRestoreController",
    "workspace_restore_controller_for",
]
