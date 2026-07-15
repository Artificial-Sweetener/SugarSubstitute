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

"""Adapt MainWindow shell collaborators to narrow workflow-tab ports."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from time import perf_counter
from typing import cast

from PySide6.QtCore import QTimer

from substitute.presentation.shell.search_overlay_controller import (
    search_overlay_controller_for,
)
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceLifecycleState,
)
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    WorkflowUiPair,
    surface_result,
)
from substitute.presentation.shell.restored_workflow_materializer import (
    restored_workflow_materializer_for,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_exception,
)

_LOGGER = get_logger("presentation.shell.workflow_shell_adapters")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowWorkflowRouteAdapter:
    """Expose immediate workflow-route operations from a MainWindow instance."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind a narrow route API."""

        self._shell = shell

    @property
    def active_workflow_id(self) -> str:
        """Return the workflow session's active workflow id."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

    def show_workflow_workspace(self) -> None:
        """Show the workflow workspace route through the settings-route owner."""

        settings_route_controller = getattr(
            self._shell,
            "settings_route_controller",
            None,
        )
        show_workflow_workspace = getattr(
            settings_route_controller,
            "show_workflow_workspace",
            None,
        )
        if callable(show_workflow_workspace):
            show_workflow_workspace()

    def set_active_workspace_route(self, workflow_id: str) -> None:
        """Record the active workflow route on the shell."""

        setattr(self._shell, "_active_workspace_route", workflow_id)
        generation_action_controller = getattr(
            self._shell,
            "generation_action_controller",
            None,
        )
        apply_generation_action_availability = getattr(
            generation_action_controller,
            "apply_generation_action_availability",
            None,
        )
        if callable(apply_generation_action_availability):
            apply_generation_action_availability()

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Select the workflow tab through the shell tab bar."""

        tabbar = getattr(self._shell, "workflow_tabbar", None)
        select_workflow_tab = getattr(tabbar, "select_workflow_tab", None)
        if callable(select_workflow_tab):
            select_workflow_tab(workflow_id, emit=emit)

    def ensure_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiPair:
        """Ensure cached workflow widgets exist without exposing shell maps."""

        cube_stacks = self._cube_stacks()
        editor_panels = self._editor_panels()
        was_materialized = workflow_id in cube_stacks and workflow_id in editor_panels
        cube_stack, editor_panel = restored_workflow_materializer_for(
            self._shell
        ).ensure_workflow_ui(
            workflow_id,
            set_as_current=set_as_current,
        )
        return WorkflowUiPair(
            cube_stack=cube_stack,
            editor_panel=editor_panel,
            created=not was_materialized,
        )

    def set_current_cube_stack(self, workflow_id: str) -> bool:
        """Show the cached cube stack for one workflow."""

        cube_stack = self._cube_stacks().get(workflow_id)
        container = getattr(self._shell, "cube_stack_container", None)
        set_current_widget = getattr(container, "setCurrentWidget", None)
        if cube_stack is None or not callable(set_current_widget):
            return False
        set_current_widget(cube_stack)
        if hasattr(self._shell, "cube_stack"):
            setattr(self._shell, "cube_stack", cube_stack)
        return True

    def set_current_editor_panel(self, workflow_id: str) -> bool:
        """Show the cached editor panel for one workflow."""

        editor_panel = self._editor_panels().get(workflow_id)
        container = getattr(self._shell, "editor_panel_container", None)
        set_current_widget = getattr(container, "setCurrentWidget", None)
        if editor_panel is None or not callable(set_current_widget):
            return False
        set_current_widget(editor_panel)
        self._finalize_pending_visible_projection(editor_panel, workflow_id)
        if hasattr(self._shell, "editor_panel"):
            setattr(self._shell, "editor_panel", editor_panel)
        return True

    def _finalize_pending_visible_projection(
        self,
        editor_panel: object,
        workflow_id: str,
    ) -> None:
        """Flush completed editor background work after the panel becomes current."""

        finalize_pending = getattr(
            editor_panel,
            "finalize_pending_visible_projection",
            None,
        )
        if not callable(finalize_pending):
            return
        try:
            finalized = bool(finalize_pending())
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to finalize pending editor projection during route swap",
                workflow_id=workflow_id,
                error=error,
            )
            return
        if finalized:
            log_debug(
                _LOGGER,
                "Finalized pending editor projection during route swap",
                workflow_id=workflow_id,
            )

    def position_search_box(self) -> None:
        """Reposition lightweight editor overlays."""

        search_overlay_controller = getattr(
            self._shell,
            "search_overlay_controller",
            None,
        )
        position_search_box = getattr(
            search_overlay_controller,
            "position_search_box",
            None,
        )
        if callable(position_search_box):
            position_search_box()
            return
        search_overlay_controller_for(self._shell).position_search_box()

    def refresh_editor_busy_surface(self) -> None:
        """Refresh active editor busy presentation."""

        editor_busy = getattr(self._shell, "editor_busy", None)
        refresh_active_surface = getattr(editor_busy, "refresh_active_surface", None)
        if callable(refresh_active_surface):
            refresh_active_surface()

    def _cube_stacks(self) -> MutableMapping[str, object]:
        """Return workflow cube-stack mapping from the shell."""

        return cast(
            MutableMapping[str, object],
            getattr(self._shell, "cube_stacks", {}),
        )

    def _editor_panels(self) -> MutableMapping[str, object]:
        """Return workflow editor-panel mapping from the shell."""

        return cast(
            MutableMapping[str, object],
            getattr(self._shell, "editor_panels", {}),
        )


class MainWindowCanvasRouteAdapter:
    """Expose shared canvas route projection through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind a canvas projection API."""

        self._shell = shell

    def project_workflow_canvas(self, workflow_id: str) -> SurfaceRefreshResult:
        """Project shared canvas panes for the selected workflow."""

        started_at = perf_counter()
        session = getattr(self._shell, "workflow_session_service", None)
        active_workflow_id = str(getattr(session, "active_workflow_id", ""))
        if workflow_id != active_workflow_id:
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation="project_workflow_canvas",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        canvas_projection_coordinator = getattr(
            self._shell,
            "workflow_canvas_projection_coordinator",
            None,
        )
        project_workflow = getattr(
            canvas_projection_coordinator,
            "project_workflow",
            None,
        )
        workflows = getattr(session, "workflows", {})
        if not callable(project_workflow):
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="project_workflow_canvas",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="workflow_canvas_projection_coordinator.project_workflow missing",
            )
        try:
            project_workflow(workflows, workflow_id)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to project workflow canvas route",
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS.value,
                operation="project_workflow_canvas",
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.FAILED,
                operation="project_workflow_canvas",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="project_workflow_canvas",
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def refresh_input_canvas_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh input-canvas availability for the active workflow."""

        started_at = perf_counter()
        if workflow_id != self._active_workflow_id():
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation="refresh_input_canvas_availability",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        refresh_input_canvas_availability = getattr(
            getattr(self._shell, "canvas_route_controller", None),
            "refresh_input_canvas_availability",
            None,
        )
        if not callable(refresh_input_canvas_availability):
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="refresh_input_canvas_availability",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="canvas_route_controller.refresh_input_canvas_availability missing",
            )
        try:
            refresh_input_canvas_availability()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to refresh input canvas availability",
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS.value,
                operation="refresh_input_canvas_availability",
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.CANVAS,
                status=SurfaceRefreshStatus.FAILED,
                operation="refresh_input_canvas_availability",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CANVAS,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="refresh_input_canvas_availability",
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def _active_workflow_id(self) -> str:
        """Return the active workflow id known to the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))


class MainWindowWorkflowActivityAdapter:
    """Expose workflow activity badge updates through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an activity API."""

        self._shell = shell

    def mark_workflow_seen(self, workflow_id: str) -> bool:
        """Clear unread workflow result state when the shell exposes it."""

        activity_service = getattr(self._shell, "workflow_activity_service", None)
        mark_seen = getattr(activity_service, "mark_seen", None)
        if not callable(mark_seen) or not bool(mark_seen(workflow_id)):
            return False
        tabbar = getattr(self._shell, "workflow_tabbar", None)
        set_unread = getattr(tabbar, "set_workflow_unread_result", None)
        if callable(set_unread):
            set_unread(workflow_id, False)
        return True


class MainWindowWorkflowSessionStateAdapter:
    """Expose workflow session state through a read-only port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind a session state API."""

        self._shell = shell

    @property
    def active_workflow_id(self) -> str:
        """Return the workflow session's active workflow id."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

    @property
    def workflows(self) -> Mapping[str, object]:
        """Return workflow state by id."""

        session = getattr(self._shell, "workflow_session_service", None)
        return cast(Mapping[str, object], getattr(session, "workflows", {}))


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
        """Return cube states, stack order, and ordered cube entries."""

        cube_states = cast(Mapping[str, object], getattr(workflow, "cubes", {}))
        stack_order = [str(alias) for alias in getattr(workflow, "stack_order", [])]
        cube_entries = [(alias, cube_states[alias]) for alias in stack_order]
        return cube_states, stack_order, cube_entries

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


class MainWindowOverrideSurfaceAdapter:
    """Expose override toolbar operations through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an override-surface API."""

        self._shell = shell
        self._materialized_defaults: dict[str, bool] = {}
        self._latest_token: ReconciliationToken | None = None

    def last_materialized_defaults(self, workflow_id: str) -> bool:
        """Return whether defaults were materialized for the latest workflow pass."""

        return self._materialized_defaults.get(workflow_id, False)

    def project_workflow_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Project one workflow's override state into shared toolbar widgets."""

        def action(manager: object) -> None:
            """Synchronize state and rebuild visible override presentation."""

            self._detach_non_target_managers(workflow_id)
            self._call_optional(manager, "sync_state_from_workflow")
            self._call_optional(manager, "rebuild_override_menu")
            self._call_optional(manager, "rebuild_active_override_controls")

        return self._with_manager(
            workflow_id,
            operation="project_workflow_overrides",
            action=action,
        )

    def sync_override_state(self, workflow_id: str) -> SurfaceRefreshResult:
        """Synchronize override state for the active workflow."""

        return self._with_manager(
            workflow_id,
            operation="sync_override_state",
            action=lambda manager: self._call_optional(
                manager,
                "sync_state_from_workflow",
            ),
        )

    def apply_overrides_before_projection(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Apply overrides before editor projection."""

        def action(manager: object) -> None:
            """Run preferred pre-projection override API with fallback."""

            pre_projection_apply = getattr(
                manager,
                "apply_global_overrides_without_snapshot_fallback",
                None,
            )
            if callable(pre_projection_apply):
                pre_projection_apply()
                return
            apply_global_overrides = getattr(manager, "apply_global_overrides", None)
            if callable(apply_global_overrides):
                apply_global_overrides(use_cached_behavior_snapshot=False)

        return self._with_manager(
            workflow_id,
            operation="apply_overrides_before_projection",
            action=action,
        )

    def materialize_default_overrides(self, workflow_id: str) -> SurfaceRefreshResult:
        """Materialize default pinned override controls after editor projection."""

        def action(manager: object) -> None:
            """Record whether default override materialization changed controls."""

            materialize_default_overrides = getattr(
                manager,
                "materialize_default_overrides",
                None,
            )
            self._materialized_defaults[workflow_id] = (
                bool(materialize_default_overrides())
                if callable(materialize_default_overrides)
                else False
            )

        return self._with_manager(
            workflow_id,
            operation="materialize_default_overrides",
            action=action,
        )

    def apply_overrides_after_projection(
        self,
        workflow_id: str,
        *,
        materialized_defaults: bool,
    ) -> SurfaceRefreshResult:
        """Apply override values after editor projection exists."""

        def action(manager: object) -> None:
            """Run post-projection override application."""

            apply_global_overrides = getattr(manager, "apply_global_overrides", None)
            if callable(apply_global_overrides):
                apply_global_overrides(
                    use_cached_behavior_snapshot=not materialized_defaults
                )

        return self._with_manager(
            workflow_id,
            operation="apply_overrides_after_projection",
            action=action,
        )

    def schedule_override_presentation_rebuild(
        self,
        workflow_id: str,
        token: ReconciliationToken,
        on_complete: Callable[[SurfaceRefreshResult], None] | None = None,
    ) -> SurfaceRefreshResult:
        """Schedule override presentation rebuild for the active workflow."""

        started_at = perf_counter()
        manager = self._manager(workflow_id)
        if manager is None:
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation="schedule_override_presentation_rebuild",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="override manager missing",
            )
        self._latest_token = token
        log_debug(
            _RECONCILER_LOGGER,
            "Scheduled deferred active override presentation rebuild",
            workflow_id=workflow_id,
        )

        def rebuild_if_current() -> None:
            """Rebuild override controls when the token is still current."""

            if self._latest_token != token or workflow_id != self._active_workflow_id():
                result = surface_result(
                    workflow_id=workflow_id,
                    surface=WorkflowSurface.OVERRIDES,
                    status=SurfaceRefreshStatus.SKIPPED_STALE,
                    operation="schedule_override_presentation_rebuild",
                    elapsed_ms=elapsed_ms_since(started_at),
                    cleanable=False,
                )
                if on_complete is not None:
                    on_complete(result)
                return
            result = self._rebuild_override_presentation(
                workflow_id,
                manager,
                started_at=started_at,
            )
            if on_complete is not None:
                on_complete(result)

        QTimer.singleShot(0, rebuild_if_current)
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="schedule_override_presentation_rebuild",
            elapsed_ms=elapsed_ms_since(started_at),
            cleanable=False,
        )

    def _rebuild_override_presentation(
        self,
        workflow_id: str,
        manager: object,
        *,
        started_at: float,
    ) -> SurfaceRefreshResult:
        """Rebuild override menu and active controls with result reporting."""

        try:
            self._call_optional(manager, "rebuild_override_menu")
            self._call_optional(manager, "rebuild_active_override_controls")
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to rebuild override presentation",
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES.value,
                operation="schedule_override_presentation_rebuild",
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.FAILED,
                operation="schedule_override_presentation_rebuild",
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        log_debug(
            _RECONCILER_LOGGER,
            "Rebuilt active override presentation",
            workflow_id=workflow_id,
        )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=SurfaceRefreshStatus.SUCCESS,
            operation="schedule_override_presentation_rebuild",
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def _with_manager(
        self,
        workflow_id: str,
        *,
        operation: str,
        action: Callable[[object], None],
    ) -> SurfaceRefreshResult:
        """Run an override operation with common result and error handling."""

        started_at = perf_counter()
        if workflow_id != self._active_workflow_id():
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        manager = self._manager(workflow_id)
        if manager is None:
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error="override manager missing",
            )
        try:
            action(manager)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to refresh override surface",
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES.value,
                operation=operation,
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=WorkflowSurface.OVERRIDES,
                status=SurfaceRefreshStatus.FAILED,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.OVERRIDES,
            status=SurfaceRefreshStatus.SUCCESS,
            operation=operation,
            elapsed_ms=elapsed_ms_since(started_at),
        )

    @staticmethod
    def _call_optional(target: object, name: str) -> None:
        """Call an optional zero-argument method."""

        method = getattr(target, name, None)
        if callable(method):
            method()

    def _manager(self, workflow_id: str) -> object | None:
        """Return the override manager for one workflow."""

        override_managers = cast(
            Mapping[str, object | None],
            getattr(self._shell, "override_managers", {}),
        )
        manager = override_managers.get(workflow_id)
        if manager is not None:
            return manager
        active_manager = getattr(self._shell, "active_override_manager", None)
        return active_manager

    def _detach_non_target_managers(self, workflow_id: str) -> None:
        """Detach cached toolbar widgets owned by inactive workflow managers."""

        override_managers = cast(
            Mapping[str, object | None],
            getattr(self._shell, "override_managers", {}),
        )
        for manager_workflow_id, manager in override_managers.items():
            if manager_workflow_id == workflow_id or manager is None:
                continue
            self._call_optional(manager, "detach_override_widgets")

    def _active_workflow_id(self) -> str:
        """Return the active workflow id known to the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))


class MainWindowGenerationAvailabilityAdapter:
    """Expose generation and input availability refresh through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an availability API."""

        self._shell = shell

    def refresh_generation_availability(
        self,
        workflow_id: str,
    ) -> SurfaceRefreshResult:
        """Refresh generation action availability for one workflow."""

        return self._run(
            workflow_id,
            operation="refresh_generation_availability",
            surface=WorkflowSurface.GENERATION_AVAILABILITY,
            action_name="generation_action_controller.apply_generation_action_availability",
        )

    def refresh_input_availability(self, workflow_id: str) -> SurfaceRefreshResult:
        """Refresh active input-canvas availability for one workflow."""

        return self._run(
            workflow_id,
            operation="refresh_input_availability",
            surface=WorkflowSurface.GENERATION_AVAILABILITY,
            action_name="canvas_route_controller.refresh_input_canvas_availability",
        )

    def _run(
        self,
        workflow_id: str,
        *,
        operation: str,
        surface: WorkflowSurface,
        action_name: str,
    ) -> SurfaceRefreshResult:
        """Run one shell availability method with result reporting."""

        started_at = perf_counter()
        if workflow_id != self._active_workflow_id():
            return surface_result(
                workflow_id=workflow_id,
                surface=surface,
                status=SurfaceRefreshStatus.SKIPPED_STALE,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
            )
        action = self._resolve_action(action_name)
        if not callable(action):
            return surface_result(
                workflow_id=workflow_id,
                surface=surface,
                status=SurfaceRefreshStatus.SKIPPED_MISSING,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=f"{action_name} missing",
            )
        try:
            action()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to refresh workflow availability",
                workflow_id=workflow_id,
                surface=surface.value,
                operation=operation,
                error=error,
            )
            return surface_result(
                workflow_id=workflow_id,
                surface=surface,
                status=SurfaceRefreshStatus.FAILED,
                operation=operation,
                elapsed_ms=elapsed_ms_since(started_at),
                cleanable=False,
                error=repr(error),
            )
        return surface_result(
            workflow_id=workflow_id,
            surface=surface,
            status=SurfaceRefreshStatus.SUCCESS,
            operation=operation,
            elapsed_ms=elapsed_ms_since(started_at),
        )

    def _active_workflow_id(self) -> str:
        """Return the active workflow id known to the shell."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

    def _resolve_action(self, action_name: str) -> object:
        """Resolve a shell action, including one level of composed ownership."""

        owner: object = self._shell
        for segment in action_name.split("."):
            owner = getattr(owner, segment, None)
            if owner is None:
                return None
        return owner


class MainWindowSessionAutosaveAdapter:
    """Expose session autosave coordinator through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an autosave API."""

        self._shell = shell

    def request(self, category: SessionAutosaveRequestCategory) -> None:
        """Request debounced autosave for an interaction category."""

        controller = getattr(self._shell, "session_autosave_controller", None)
        request = getattr(controller, "request_categorized_session_autosave", None)
        if callable(request):
            request(category)
            return
        request_session_autosave = getattr(
            self._shell, "request_session_autosave", None
        )
        if callable(request_session_autosave):
            request_session_autosave()

    def flush(self, category: SessionAutosaveRequestCategory) -> None:
        """Flush one autosave category immediately when supported."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        flush = getattr(coordinator, "flush", None)
        if callable(flush):
            flush(category)
            return
        request_session_autosave = getattr(
            self._shell, "request_session_autosave", None
        )
        if callable(request_session_autosave):
            request_session_autosave()


__all__ = [
    "MainWindowCanvasRouteAdapter",
    "MainWindowEditorSurfaceAdapter",
    "MainWindowGenerationAvailabilityAdapter",
    "MainWindowOverrideSurfaceAdapter",
    "MainWindowSessionAutosaveAdapter",
    "MainWindowWorkflowActivityAdapter",
    "MainWindowWorkflowRouteAdapter",
    "MainWindowWorkflowSessionStateAdapter",
]
