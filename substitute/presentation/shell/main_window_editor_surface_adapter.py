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

"""Adapt MainWindow editor surfaces to their reconciliation port."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import cast


from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjectionService,
)

from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceLifecycleState,
)
from substitute.presentation.shell.workflow_surface_results import (
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    surface_result,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_exception,
)

_LOGGER = get_logger("presentation.shell.main_window_editor_surface_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowEditorSurfaceAdapter:
    """Expose editor surface projection through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an editor-surface API."""

        self._shell = shell

    def current_projection_state(
        self,
        workflow_id: str,
    ) -> WorkflowSurfaceLifecycleState:
        """Return the editor panel's current projection state."""

        editor_panel = self._editor_panels().get(workflow_id)
        workflow = self._workflows().get(workflow_id)
        if editor_panel is None or workflow is None:
            return WorkflowSurfaceLifecycleState.UNMATERIALIZED
        try:
            projection_signature = self._projection_signature(
                editor_panel,
                workflow_id=workflow_id,
                workflow=workflow,
            )
        except (KeyError, TypeError, ValueError):
            return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED
        if projection_signature is None:
            return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED
        is_projection_clean = getattr(editor_panel, "is_projection_clean", None)
        if callable(is_projection_clean) and bool(
            is_projection_clean(projection_signature)
        ):
            return WorkflowSurfaceLifecycleState.CLEAN
        return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED

    def refresh_editor_surface(
        self,
        workflow_id: str,
        *,
        force: bool,
        on_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> SurfaceRefreshResult:
        """Refresh the active editor surface or prove the projection is clean."""

        started_at = perf_counter()
        if workflow_id != self._active_workflow_id():
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.EDITOR,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation="refresh_editor_surface",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        workflow = self._workflows().get(workflow_id)
        editor_panel = self._active_editor_panel(workflow_id)
        if workflow is None or editor_panel is None:
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.EDITOR,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="refresh_editor_surface",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="workflow or editor panel missing",
            )
        try:
            self._finalize_pending_visible_projection(
                editor_panel,
                workflow_id=workflow_id,
            )
            projection_signature = self._projection_signature(
                editor_panel,
                workflow_id=workflow_id,
                workflow=workflow,
            )
            if self._can_refresh_clean_projection(
                editor_panel,
                projection_signature=projection_signature,
                force=force,
            ):
                refresh_clean_projection = getattr(
                    editor_panel,
                    "refresh_clean_projection",
                )
                cube_states, stack_order, _cube_entries = self._workflow_projection(
                    workflow,
                )
                refresh_clean_projection(
                    cube_states=cube_states,
                    stack_order=stack_order,
                )
                result = surface_result(
                    workflow_id=workflow_id,
                    surface=WorkflowSurface.EDITOR,
                    status=SurfaceRefreshStatus.SKIPPED_CLEAN,
                    operation="refresh_editor_surface",
                    elapsed_ms=elapsed_ms_since(started_at),
                )
                if on_complete is not None:
                    on_complete(result)
                return result
            load_all_cubes = getattr(editor_panel, "load_all_cubes", None)
            if not callable(load_all_cubes):
                return self._refresh_with_legacy_hook(
                    workflow_id,
                    force=force,
                    started_at=started_at,
                    on_complete=on_complete,
                )
            cube_states, stack_order, cube_entries = self._workflow_projection(
                workflow,
            )
            log_debug(
                _RECONCILER_LOGGER,
                "Loading active editor cube surface",
                workflow_id=workflow_id,
                cube_section_count=len(cube_entries),
                stack_order_count=len(stack_order),
            )
            load_kwargs: dict[str, object] = {
                "cube_entries": cube_entries,
                "cube_states": cube_states,
                "stack_order": stack_order,
                "on_complete": self._completion_callback(
                    workflow_id,
                    started_at=started_at,
                    on_complete=on_complete,
                ),
            }
            if projection_signature is not None:
                load_kwargs["projection_signature"] = projection_signature
            load_all_cubes(**load_kwargs)
            log_debug(
                _RECONCILER_LOGGER,
                "Queued active editor cube surface refresh",
                workflow_id=workflow_id,
                cube_section_count=len(cube_entries),
                stack_order_count=len(stack_order),
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to refresh editor surface",
                workflow_id=workflow_id,
                surface=WorkflowSurface.EDITOR.value,
                operation="refresh_editor_surface",
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.EDITOR,
                status=SurfaceRefreshStatus.FAILED,
                operation="refresh_editor_surface",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.EDITOR,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="refresh_editor_surface",
            elapsed_ms=elapsed_ms_since(started_at),
            cleanable=False,
        )

    def _refresh_with_legacy_hook(
        self,
        workflow_id: str,
        *,
        force: bool,
        started_at: float,
        on_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> SurfaceRefreshResult:
        """Use a legacy shell refresh hook when a test double lacks editor APIs."""

        legacy_refresh = getattr(self._shell, "refresh_active_workflow_surface", None)
        if not callable(legacy_refresh):
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.EDITOR,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="refresh_editor_surface",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="editor panel load_all_cubes missing",
            )

        def notify_complete() -> None:
            """Convert legacy completion to a typed editor result."""

            result = surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.EDITOR,
                status=SurfaceRefreshStatus.SUCCESS,
                operation="refresh_editor_surface",
                elapsed_ms=elapsed_ms_since(started_at),
            )
            if on_complete is not None:
                on_complete(result)

        try:
            legacy_refresh(force_refresh=force, on_complete=notify_complete)
        except TypeError:
            legacy_refresh()
            notify_complete()
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.EDITOR,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="refresh_editor_surface",
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def refresh_clean_editor_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh lightweight clean projection state for an editor panel."""

        return self.refresh_editor_surface(
            workflow_id,
            force=False,
            on_complete=None,
        )

    def _completion_callback(
        self,
        workflow_id: str,
        *,
        started_at: float,
        on_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> Callable[[], None]:
        """Return an editor-load completion callback with typed result context."""

        def callback() -> None:
            """Notify reconciliation that editor projection finished."""

            result = surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.EDITOR,
                status=SurfaceRefreshStatus.SUCCESS,
                operation="refresh_editor_surface_complete",
                elapsed_ms=elapsed_ms_since(started_at),
            )
            if on_complete is not None:
                on_complete(result)

        return callback

    def _active_editor_panel(self, workflow_id: str) -> object | None:
        """Return active editor panel with mapping fallback for tests."""

        active_editor_panel = getattr(self._shell, "active_editor_panel", None)
        if active_editor_panel is not None:
            return cast(object, active_editor_panel)
        return self._editor_panels().get(workflow_id)

    def _finalize_pending_visible_projection(
        self,
        editor_panel: object,
        *,
        workflow_id: str,
    ) -> None:
        """Flush deferred editor reveal before clean-projection reuse checks."""

        finalize_pending = getattr(
            editor_panel,
            "finalize_pending_visible_projection",
            None,
        )
        if not callable(finalize_pending):
            return
        finalized = bool(finalize_pending())
        if finalized:
            log_debug(
                _RECONCILER_LOGGER,
                "Finalized pending editor projection before surface refresh",
                workflow_id=workflow_id,
            )

    def _projection_signature(
        self,
        editor_panel: object,
        *,
        workflow_id: str,
        workflow: object,
    ) -> object | None:
        """Return the editor projection signature when supported."""

        current_projection_signature = getattr(
            editor_panel,
            "current_projection_signature",
            None,
        )
        if not callable(current_projection_signature):
            return None
        cube_states, stack_order, cube_entries = self._workflow_projection(workflow)
        return cast(
            object | None,
            current_projection_signature(
                workflow_id=workflow_id,
                cube_entries=cube_entries,
                cube_states=cube_states,
                stack_order=stack_order,
            ),
        )

    @staticmethod
    def _can_refresh_clean_projection(
        editor_panel: object,
        *,
        projection_signature: object | None,
        force: bool,
    ) -> bool:
        """Return whether the editor can avoid a full cube reload."""

        is_projection_clean = getattr(editor_panel, "is_projection_clean", None)
        refresh_clean_projection = getattr(
            editor_panel,
            "refresh_clean_projection",
            None,
        )
        return bool(
            projection_signature is not None
            and not force
            and callable(is_projection_clean)
            and bool(is_projection_clean(projection_signature))
            and callable(refresh_clean_projection)
        )

    @staticmethod
    def _workflow_projection(
        workflow: object,
    ) -> tuple[Mapping[str, object], list[str], list[tuple[str, object]]]:
        """Return shared editor states, order, and ordered section entries."""

        projection = WorkflowEditorProjectionService().project(workflow)
        return projection.states, list(projection.order), list(projection.entries)

    def _active_workflow_id(self) -> str:
        """Return the active workflow id known to the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

    def _workflows(self) -> Mapping[str, object]:
        """Return workflow state by id from the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return cast(Mapping[str, object], getattr(session, "workflows", {}))

    def _editor_panels(self) -> Mapping[str, object]:
        """Return editor-panel mapping from the shell."""

        return cast(Mapping[str, object], getattr(self._shell, "editor_panels", {}))
