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

"""Coordinate restored workflow projection and restore projection cache capture."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QTimer

from substitute.application.workspace_state import (
    RestoredEditorProjectionCacheExtractor,
    RestoreProjectionArtifact,
)
from substitute.domain.workspace_snapshot import WorkflowSnapshot
from substitute.presentation.shell.editor_viewport_restore import (
    editor_viewport_restore_controller_for,
)
from substitute.presentation.shell.restored_workflow_materializer import (
    restored_workflow_materializer_for,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("presentation.shell.restore_projection_controller")


class RestoreProjectionController:
    """Own restored workflow projection, settings projection, and cache capture."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose restored projections should be coordinated."""

        self._shell = shell

    def start_pre_show_restore_projection(
        self,
        artifact: RestoreProjectionArtifact | None,
        *,
        fallback_workflow_id: str = "",
        on_complete: Callable[[], None],
    ) -> bool:
        """Build the restored editor surface before revealing the shell."""

        workflow_id = getattr(
            self._shell,
            "_prehydrated_active_workflow_projection_pending",
            "",
        )
        cached_active_workflow_id = (
            artifact.active_workflow_id if artifact is not None else ""
        )
        workflow_count = len(artifact.workflows) if artifact is not None else 0
        trace_mark(
            "restore_projection_cache.provisional_build.start",
            workflow_id=workflow_id,
            cached_active_workflow_id=cached_active_workflow_id,
            cached_workflow_count=workflow_count,
            fallback_workflow_id=fallback_workflow_id,
            cache_artifact_present=artifact is not None,
            projection_mode="pre_show_live",
        )
        if getattr(self._shell, "_prehydrated_restore_finalized", False):
            trace_mark(
                "restore_projection_cache.provisional_build.skip",
                reason="already_finalized",
                projection_mode="pre_show_live",
            )
            return False
        if not getattr(self._shell, "_prehydrated_restore_runtime_prepared", False):
            trace_mark(
                "restore_projection_cache.provisional_build.skip",
                reason="runtime_not_prepared",
                projection_mode="pre_show_live",
            )
            return False
        if not workflow_id and fallback_workflow_id:
            workflow_id = fallback_workflow_id
        if not workflow_id:
            trace_mark(
                "restore_projection_cache.provisional_build.skip",
                reason="no_pending_workflow_projection",
                projection_mode="pre_show_live",
            )
            return False
        if artifact is not None and workflow_id != artifact.active_workflow_id:
            trace_mark(
                "restore_projection_cache.provisional_build.discard",
                reason="active_workflow_mismatch",
                workflow_id=workflow_id,
                cached_active_workflow_id=artifact.active_workflow_id,
                projection_mode="pre_show_live",
            )
            return False
        if artifact is None and workflow_id != fallback_workflow_id:
            trace_mark(
                "restore_projection_cache.provisional_build.discard",
                reason="fallback_workflow_mismatch",
                workflow_id=workflow_id,
                fallback_workflow_id=fallback_workflow_id,
                projection_mode="pre_show_live",
            )
            return False

        def finish_pre_show_projection() -> None:
            """Record hidden projection completion and continue startup reveal."""

            trace_mark(
                "restore_projection_cache.provisional_build.complete",
                workflow_id=workflow_id,
                projection_mode="pre_show_live",
            )
            on_complete()

        try:
            self.project_restored_workflow_editor_surface(
                workflow_id,
                suppress_visible_geometry=True,
                on_surface_complete=finish_pre_show_projection,
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as error:
            trace_mark(
                "restore_projection_cache.provisional_build.error",
                workflow_id=workflow_id,
                error=repr(error),
                projection_mode="pre_show_live",
            )
            log_exception(
                _LOGGER,
                "Failed to build pre-show restored editor projection",
                workflow_id=workflow_id,
                error=error,
            )
            return False
        return True

    def project_restored_workflow(self, workflow_id: str) -> None:
        """Project a restored workflow into the shell."""

        trace_mark(
            "main_window.project_restored_workflow.start",
            workflow_id=workflow_id,
        )
        log_info(
            _LOGGER,
            "mainwindow project restored workflow",
            workflow_id=workflow_id,
            active_route_before=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_before=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
            cube_stack_ids=tuple(getattr(self._shell, "cube_stacks", {})),
            editor_panel_ids=tuple(getattr(self._shell, "editor_panels", {})),
        )
        snapshot = self.restored_workflow_snapshot(workflow_id)

        def restore_viewport_after_projection() -> None:
            """Schedule restored editor viewport after editor projection completes."""

            if snapshot is None:
                return
            trace_mark(
                "main_window.restore_editor_viewport.deferred",
                delay_ms=0,
            )
            QTimer.singleShot(
                0,
                lambda: editor_viewport_restore_controller_for(
                    self._shell
                ).restore_editor_viewport_for_workflow(snapshot),
            )

        self._shell.workspace_controller.project_workflow(
            workflow_id,
            force_refresh=True,
            on_surface_complete=restore_viewport_after_projection
            if snapshot is not None
            else None,
        )
        log_info(
            _LOGGER,
            "mainwindow project restored workflow completed",
            workflow_id=workflow_id,
            active_route_after=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_after=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
            active_cube_stack_present=getattr(self._shell, "active_cube_stack", None)
            is not None,
            active_editor_panel_present=getattr(
                self._shell, "active_editor_panel", None
            )
            is not None,
        )
        trace_mark(
            "main_window.project_restored_workflow.end",
            workflow_id=workflow_id,
        )

    def restored_workflow_snapshot(self, workflow_id: str) -> WorkflowSnapshot | None:
        """Return the restored workflow snapshot retained for projection finalizers."""

        snapshots_by_id = getattr(self._shell, "_restored_workflow_snapshots_by_id", {})
        snapshot = snapshots_by_id.get(workflow_id)
        if isinstance(snapshot, WorkflowSnapshot):
            return snapshot
        pending_snapshots = getattr(
            self._shell,
            "_pending_restored_workflow_snapshots",
            {},
        )
        snapshot = pending_snapshots.get(workflow_id)
        if isinstance(snapshot, WorkflowSnapshot):
            return snapshot
        workspace = getattr(self._shell, "_prehydrated_workspace_snapshot", None)
        workflows = getattr(workspace, "workflows", ()) if workspace is not None else ()
        for workflow in workflows:
            if (
                isinstance(workflow, WorkflowSnapshot)
                and workflow.workflow_id == workflow_id
            ):
                if isinstance(snapshots_by_id, dict):
                    snapshots_by_id[workflow_id] = workflow
                return workflow
        return None

    def project_restored_workflow_editor_surface(
        self,
        workflow_id: str,
        *,
        suppress_visible_geometry: bool,
        on_surface_complete: Callable[[], None],
    ) -> None:
        """Project restored editor widgets without visible-only geometry work."""

        log_info(
            _LOGGER,
            "mainwindow project restored workflow editor surface",
            workflow_id=workflow_id,
            suppress_visible_geometry=suppress_visible_geometry,
            active_route_before=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_before=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
        )
        self._shell.workflow_session_service.activate_workflow(workflow_id)
        self._set_active_workspace_route(workflow_id)
        restored_workflow_materializer_for(self._shell).ensure_workflow_ui(
            workflow_id,
            set_as_current=True,
        )
        select_workflow_tab = getattr(
            self._shell.workflow_tabbar,
            "select_workflow_tab",
            None,
        )
        if callable(select_workflow_tab):
            select_workflow_tab(workflow_id, emit=False)
        cube_stack = self._shell.cube_stacks.get(workflow_id)
        if cube_stack is not None:
            self._shell.cube_stack_container.setCurrentWidget(cube_stack)
        editor_panel = self._shell.editor_panels.get(workflow_id)
        if editor_panel is not None:
            self._shell.editor_panel_container.setCurrentWidget(editor_panel)
        self.reconcile_active_workflow_for_restore_projection(
            force_refresh=True,
            on_complete=on_surface_complete,
        )

    def _set_active_workspace_route(self, workflow_id: str) -> None:
        """Record restored workflow route state and refresh generation actions."""

        self._shell._active_workspace_route = workflow_id
        apply_generation_action_availability = getattr(
            getattr(self._shell, "generation_action_controller", None),
            "apply_generation_action_availability",
            None,
        )
        if callable(apply_generation_action_availability):
            apply_generation_action_availability()

    def reconcile_active_workflow_for_restore_projection(
        self,
        *,
        force_refresh: bool,
        on_complete: Callable[[], None],
    ) -> None:
        """Structurally reconcile restored workflow editor widgets before display."""

        self._shell.active_workflow_surface_refresher.refresh_active_workflow_surface(
            force_refresh=force_refresh,
            on_complete=on_complete,
        )

    def queue_restore_projection_cache_capture(self, workflow_id: str) -> None:
        """Remember that live restored editor projection can be cached when running."""

        self._shell._pending_restore_projection_cache_capture_workflow_id = workflow_id
        trace_mark(
            "restore_projection_cache.capture.queued",
            workflow_id=workflow_id,
            lifecycle=getattr(self._shell, "_shell_restore_lifecycle", ""),
        )
        self.maybe_capture_restore_projection_cache()

    def maybe_capture_restore_projection_cache(self) -> None:
        """Persist cache metadata once live restore and shell finalization are complete."""

        workflow_id = getattr(
            self._shell,
            "_pending_restore_projection_cache_capture_workflow_id",
            "",
        )
        if not workflow_id:
            return
        if getattr(self._shell, "_shell_restore_lifecycle", "") != "running":
            trace_mark(
                "restore_projection_cache.capture.skip",
                reason="restore_not_running",
                workflow_id=workflow_id,
                lifecycle=getattr(self._shell, "_shell_restore_lifecycle", ""),
            )
            return
        self._shell._pending_restore_projection_cache_capture_workflow_id = ""
        repository = getattr(self._shell, "restore_projection_cache_repository", None)
        if repository is None:
            trace_mark(
                "restore_projection_cache.capture.skip",
                reason="no_repository",
                workflow_id=workflow_id,
            )
            return
        snapshot = getattr(self._shell, "_prehydrated_workspace_snapshot", None)
        if snapshot is None:
            trace_mark(
                "restore_projection_cache.capture.skip",
                reason="no_workspace_snapshot",
                workflow_id=workflow_id,
            )
            return
        try:
            trace_mark(
                "restore_projection_cache.capture.start",
                workflow_id=workflow_id,
            )
            artifact = RestoredEditorProjectionCacheExtractor().capture_and_store(
                repository=repository,
                snapshot=snapshot,
                target_key=getattr(self._shell, "restore_projection_target_key", ""),
                editor_panels=getattr(self._shell, "editor_panels", {}),
                node_definition_gateway=self._shell.node_definition_gateway,
            )
            trace_mark(
                "restore_projection_cache.capture.write",
                workflow_id=workflow_id,
                workflow_count=len(artifact.workflows),
                cube_count=sum(len(workflow.cubes) for workflow in artifact.workflows),
                node_definition_count=len(artifact.node_definition_fingerprints),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            trace_mark(
                "restore_projection_cache.capture.error",
                workflow_id=workflow_id,
                error=repr(error),
            )
            log_exception(
                _LOGGER,
                "Failed to capture restore projection cache",
                workflow_id=workflow_id,
                error=error,
            )

    def project_restored_settings(self) -> None:
        """Project the restored Settings route into the shell."""

        trace_mark("main_window.project_restored_settings.start")
        log_info(
            _LOGGER,
            "mainwindow project restored settings",
            active_route_before=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_before=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
        )
        self._shell.settings_route_controller.project_settings_workspace()
        log_info(
            _LOGGER,
            "mainwindow project restored settings completed",
            active_route_after=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_after=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
        )
        trace_mark("main_window.project_restored_settings.end")


def restore_projection_controller_for(shell: Any) -> RestoreProjectionController:
    """Return the composed restore projection controller for a shell."""

    controller = getattr(shell, "restore_projection_controller", None)
    if isinstance(controller, RestoreProjectionController):
        return controller
    controller = RestoreProjectionController(shell)
    setattr(shell, "restore_projection_controller", controller)
    return controller


__all__ = [
    "RestoreProjectionController",
    "restore_projection_controller_for",
]
