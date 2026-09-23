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

"""Project workflow lifecycle transitions into shell UI surfaces."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import cast

from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowSnapshotService,
)
from substitute.presentation.shell.closed_workflow_history import (
    ClosedWorkflowHistory,
    ClosedWorkflowHistoryView,
)
from substitute.presentation.shell.workflow_closure_coordinator import (
    WorkflowClosureCoordinator,
    WorkflowClosureView,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)
from substitute.presentation.shell.workflow_surface_refresh_scheduler import (
    WorkflowSurfaceRefreshScheduler,
)
from substitute.presentation.shell.workflow_route_projector import (
    WorkflowRouteProjector,
)
from substitute.presentation.shell.main_window_canvas_route_adapter import (
    MainWindowCanvasRouteAdapter,
)
from substitute.presentation.shell.main_window_override_surface_adapter import (
    MainWindowOverrideSurfaceAdapter,
)
from substitute.presentation.shell.main_window_workflow_activity_adapter import (
    MainWindowWorkflowActivityAdapter,
)
from substitute.presentation.shell.main_window_workflow_route_adapter import (
    MainWindowWorkflowRouteAdapter,
)
from substitute.presentation.shell.main_window_workflow_surface_composition import (
    build_main_window_workflow_surface_reconciler,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    WorkflowSurfaceReconciler,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceRegistry,
)
from substitute.presentation.shell.workflow_surface_results import SurfaceRefreshResult
from substitute.presentation.shell.workflow_tab_switch_diagnostics import (
    WorkflowTabSwitchDiagnostic,
    WorkflowTabSwitchDiagnostics,
)
from substitute.presentation.shell.workflow_rename_controller import (
    WorkflowRenameController,
    WorkflowRenameView,
)
from substitute.presentation.shell.workflow_workspace_materializer import (
    WorkflowWorkspaceMaterializationView,
    WorkflowWorkspaceMaterializer,
)
from substitute.presentation.shell.workflow_workspace_projection_ports import (
    WorkflowSurfaceInvalidationProtocol,
    WorkflowSurfaceRefreshSchedulerProtocol,
    WorkflowWorkspaceView,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
)

_LOGGER = get_logger("presentation.shell.workflow_workspace_coordinator")


class WorkflowWorkspaceCoordinator:
    """Own workflow lifecycle projection across shell UI collaborators."""

    def __init__(
        self,
        view: WorkflowWorkspaceView,
        *,
        surface_refresh_scheduler: WorkflowSurfaceRefreshSchedulerProtocol
        | None = None,
        surface_invalidation_service: WorkflowSurfaceInvalidationProtocol | None = None,
        route_projector: WorkflowRouteProjector | None = None,
        surface_reconciler: WorkflowSurfaceReconciler | None = None,
    ) -> None:
        """Store the shell view dependency."""

        self._view = view
        closed_workflow_buffer = getattr(
            view,
            "closed_workflow_buffer",
            ClosedWorkflowBuffer(),
        )
        closed_workflow_snapshot_service = getattr(
            view,
            "closed_workflow_snapshot_service",
            ClosedWorkflowSnapshotService(),
        )
        self._closed_workflow_history = ClosedWorkflowHistory(
            cast(ClosedWorkflowHistoryView, view),
            buffer=closed_workflow_buffer,
            snapshot_service=closed_workflow_snapshot_service,
        )
        self._tab_switch_diagnostics = WorkflowTabSwitchDiagnostics()
        self._surface_invalidation_service = (
            surface_invalidation_service
            if surface_invalidation_service is not None
            else cast(
                WorkflowSurfaceInvalidationProtocol | None,
                getattr(view, "workflow_surface_invalidation_service", None),
            )
        ) or WorkflowSurfaceInvalidationService()
        self._surface_refresh_scheduler = (
            surface_refresh_scheduler
            if surface_refresh_scheduler is not None
            else WorkflowSurfaceRefreshScheduler(
                active_workflow_id=self._active_workflow_id,
                refresh_surface=self._refresh_projected_workflow_surface,
            )
        )
        workflow_session_service = getattr(view, "workflow_session_service", None)
        workflows = cast(
            Mapping[str, object],
            getattr(workflow_session_service, "workflows", {}),
        )
        self._surface_registry = WorkflowSurfaceRegistry(
            editor_panels=cast(
                Mapping[str, object], getattr(view, "editor_panels", {})
            ),
            cube_stacks=cast(Mapping[str, object], getattr(view, "cube_stacks", {})),
            override_managers=cast(
                Mapping[str, object | None],
                getattr(view, "override_managers", {}),
            ),
            workflows=workflows,
            surface_invalidation_service=self._surface_invalidation_service,
        )
        route_adapter = MainWindowWorkflowRouteAdapter(view)
        canvas_adapter = MainWindowCanvasRouteAdapter(view)
        override_adapter = MainWindowOverrideSurfaceAdapter(view)
        activity_adapter = MainWindowWorkflowActivityAdapter(view)
        self._route_projector = route_projector or WorkflowRouteProjector(
            route_adapter,
            canvas_port=canvas_adapter,
            override_port=override_adapter,
            activity_port=activity_adapter,
            surface_registry=self._surface_registry,
            surface_invalidation_service=self._surface_invalidation_service,
        )
        self._surface_reconciler = (
            surface_reconciler
            or build_main_window_workflow_surface_reconciler(
                view,
                canvas_port=canvas_adapter,
                override_port=override_adapter,
                surface_invalidation_service=self._surface_invalidation_service,
            )
        )
        self._workspace_materializer = WorkflowWorkspaceMaterializer(
            cast(WorkflowWorkspaceMaterializationView, view),
            closed_workflow_history=self._closed_workflow_history,
            project_workflow=self.project_workflow,
        )
        self._closure_coordinator = WorkflowClosureCoordinator(
            cast(WorkflowClosureView, view),
            closed_workflow_history=self._closed_workflow_history,
            surface_invalidation=self._surface_invalidation_service,
            add_workflow=self.add_workflow,
            project_workflow=self.project_workflow,
        )
        self._rename_controller = WorkflowRenameController(
            cast(WorkflowRenameView, view)
        )

    def activate_workflow(
        self,
        workflow_id: str,
        *,
        source: str = "workflow_tab",
        force_refresh: bool = False,
        on_surface_complete: Callable[[], None] | None = None,
    ) -> None:
        """Activate workflow and project it once when state changes."""

        tab_intent_received_at = perf_counter()
        view = self._view
        previous_workflow_id = view.workflow_session_service.active_workflow_id
        outgoing_manager = view.override_managers.get(previous_workflow_id)
        log_debug(
            _LOGGER,
            "workflow coordinator activate workflow started",
            requested_workflow_id=workflow_id,
            source=source,
            force_refresh=force_refresh,
            previous_workflow_id=previous_workflow_id,
            active_workspace_route=getattr(view, "_active_workspace_route", ""),
            workflow_ids=tuple(view.workflow_session_service.workflows),
            cube_stack_ids=tuple(view.cube_stacks),
            editor_panel_ids=tuple(view.editor_panels),
        )
        active_update_started_at = perf_counter()
        transition = view.workflow_session_service.activate_workflow(workflow_id)
        active_workflow_update_elapsed_ms = elapsed_ms_since(active_update_started_at)
        active_workspace_route = getattr(view, "_active_workspace_route", workflow_id)
        returning_from_non_workflow_route = active_workspace_route != workflow_id
        log_debug(
            _LOGGER,
            "workflow coordinator activate workflow transition",
            requested_workflow_id=workflow_id,
            previous_workflow_id=transition.previous_workflow_id,
            new_workflow_id=transition.new_workflow_id,
            active_changed=transition.active_changed,
            returning_from_non_workflow_route=returning_from_non_workflow_route,
        )
        if (
            not transition.active_changed
            and not force_refresh
            and not returning_from_non_workflow_route
        ):
            log_debug(
                _LOGGER,
                "workflow coordinator activate workflow skipped projection",
                requested_workflow_id=workflow_id,
            )
            return
        if transition.active_changed and outgoing_manager is not None:
            outgoing_manager.detach_override_widgets()
        if transition.active_changed:
            generation_feedback_presenter_for(
                view
            ).clear_all_model_field_load_progress()
        self.project_workflow(
            workflow_id,
            force_refresh=force_refresh,
            source=source,
            on_surface_complete=on_surface_complete,
            tab_intent_received_at=tab_intent_received_at,
            active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
        )

    def project_workflow(
        self,
        workflow_id: str,
        *,
        force_refresh: bool = False,
        source: str = "workspace_projection",
        on_surface_complete: Callable[[], None] | None = None,
        tab_intent_received_at: float | None = None,
        active_workflow_update_elapsed_ms: float = 0.0,
    ) -> None:
        """Project one workflow id into tab, editor, override, and canvas surfaces."""

        view = self._view
        log_debug(
            _LOGGER,
            "workflow coordinator project workflow started",
            workflow_id=workflow_id,
            force_refresh=force_refresh,
            source=source,
            active_route_before=getattr(view, "_active_workspace_route", ""),
            active_workflow_id=view.workflow_session_service.active_workflow_id,
            workflow_ids=tuple(view.workflow_session_service.workflows),
            cube_stack_present=workflow_id in view.cube_stacks,
            editor_panel_present=workflow_id in view.editor_panels,
        )
        should_defer_surface_refresh = self._should_defer_surface_refresh(
            source,
            on_surface_complete,
        )
        route_projection = self._route_projector.project(
            workflow_id,
            project_shared_canvas=should_defer_surface_refresh,
        )
        view.generation_action_controller.project_active_workflow_progress()
        if should_defer_surface_refresh:
            dirty_state = self._surface_invalidation_service.dirty_state(workflow_id)
            cached_surface_clean = self._cached_workflow_surface_is_clean(workflow_id)
            # Non-editor dirty state should not downgrade an unprojected editor to a
            # dirty-only refresh; restored tabs need the full surface pass first.
            deferred_force_refresh = force_refresh or (
                bool(dirty_state.dirty_surfaces) and not cached_surface_clean
            )
            if (
                not force_refresh
                and not dirty_state.dirty_surfaces
                and cached_surface_clean
            ):
                log_debug(
                    _LOGGER,
                    "workflow tab switch used clean cached surface",
                    workflow_id=workflow_id,
                    source=source,
                    route_created_widgets=route_projection.created_widgets,
                    route_canvas_projected=route_projection.canvas_projected,
                    active_route_after=getattr(view, "_active_workspace_route", ""),
                    active_workflow_id=view.workflow_session_service.active_workflow_id,
                )
                self._tab_switch_diagnostics.record(
                    source=source,
                    tab_intent_received_at=tab_intent_received_at,
                    active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
                    route_projection=route_projection,
                    editor_rebuilt=False,
                    deferred_requests=0,
                )
                return
            self._surface_refresh_scheduler.request(
                workflow_id,
                force_refresh=deferred_force_refresh,
                reason=source,
                on_complete=on_surface_complete,
            )
            log_debug(
                _LOGGER,
                "workflow coordinator project workflow scheduled surface refresh",
                workflow_id=workflow_id,
                source=source,
                force_refresh=deferred_force_refresh,
                requested_force_refresh=force_refresh,
                cached_surface_clean=cached_surface_clean,
                dirty_surfaces=tuple(
                    surface.value for surface in dirty_state.dirty_surfaces
                ),
                dirty_reasons=tuple(reason.value for reason in dirty_state.reasons),
                route_created_widgets=route_projection.created_widgets,
                route_canvas_projected=route_projection.canvas_projected,
                active_route_after=getattr(view, "_active_workspace_route", ""),
                active_workflow_id=view.workflow_session_service.active_workflow_id,
            )
            self._tab_switch_diagnostics.record(
                source=source,
                tab_intent_received_at=tab_intent_received_at,
                active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
                route_projection=route_projection,
                editor_rebuilt=False,
                deferred_requests=1,
            )
            return
        self._refresh_projected_workflow_surface(
            workflow_id,
            force_refresh,
            on_surface_complete,
        )
        self._tab_switch_diagnostics.record(
            source=source,
            tab_intent_received_at=tab_intent_received_at,
            active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
            route_projection=route_projection,
            editor_rebuilt=force_refresh or on_surface_complete is not None,
            deferred_requests=0,
        )

    @property
    def last_tab_switch_diagnostic(self) -> WorkflowTabSwitchDiagnostic | None:
        """Return the latest workflow projection diagnostic row."""

        return self._tab_switch_diagnostics.last

    def tab_switch_diagnostics(self) -> tuple[WorkflowTabSwitchDiagnostic, ...]:
        """Return recorded workflow projection diagnostics."""

        return self._tab_switch_diagnostics.history()

    def _cached_workflow_surface_is_clean(self, workflow_id: str) -> bool:
        """Return whether the target editor panel proves its cached projection is clean."""

        view = self._view
        editor_panel = view.editor_panels.get(workflow_id)
        workflow = view.workflow_session_service.workflows.get(workflow_id)
        if editor_panel is None or workflow is None:
            return False
        current_projection_signature = getattr(
            editor_panel,
            "current_projection_signature",
            None,
        )
        is_projection_clean = getattr(editor_panel, "is_projection_clean", None)
        if not callable(current_projection_signature) or not callable(
            is_projection_clean
        ):
            return True
        cube_states = getattr(workflow, "cubes", {})
        stack_order = list(getattr(workflow, "stack_order", ()) or ())
        if not isinstance(cube_states, Mapping):
            return False
        try:
            cube_entries = [(alias, cube_states[alias]) for alias in stack_order]
            projection_signature = current_projection_signature(
                workflow_id=workflow_id,
                cube_entries=cube_entries,
                cube_states=cube_states,
                stack_order=stack_order,
            )
        except (KeyError, TypeError, ValueError) as error:
            log_debug(
                _LOGGER,
                "workflow cached editor surface was not provably clean",
                workflow_id=workflow_id,
                error=repr(error),
            )
            return False
        return bool(
            projection_signature is not None
            and is_projection_clean(projection_signature)
        )

    def _refresh_projected_workflow_surface(
        self,
        workflow_id: str,
        force_refresh: bool,
        on_surface_complete: Callable[[], None] | None,
    ) -> None:
        """Refresh editor, canvas, and workflow activity for current route projection."""

        dirty_state = self._surface_invalidation_service.dirty_state(workflow_id)
        log_debug(
            _LOGGER,
            "workflow coordinator handing projected workflow to reconciler",
            workflow_id=workflow_id,
            force_refresh=force_refresh,
            dirty_surfaces=tuple(
                surface.value for surface in dirty_state.dirty_surfaces
            ),
            dirty_reasons=tuple(reason.value for reason in dirty_state.reasons),
        )
        self._surface_reconciler.reconcile_projected(
            workflow_id,
            force_refresh=force_refresh,
            dirty_state=dirty_state,
            on_surface_complete=(
                self._typed_surface_completion(on_surface_complete)
                if on_surface_complete is not None
                else None
            ),
        )

    @staticmethod
    def _typed_surface_completion(
        on_surface_complete: Callable[[], None],
    ) -> Callable[[SurfaceRefreshResult], None]:
        """Adapt public completion callbacks to typed surface result callbacks."""

        def complete(_result: SurfaceRefreshResult) -> None:
            """Run the public completion callback after surface projection."""

            on_surface_complete()

        return complete

    @staticmethod
    def _should_defer_surface_refresh(
        source: str,
        on_surface_complete: Callable[[], None] | None,
    ) -> bool:
        """Return whether route projection should hand surface work to the scheduler."""

        return source == "workflow_tab" and on_surface_complete is None

    def _active_workflow_id(self) -> str:
        """Return the currently active workflow id for deferred refresh validation."""

        return self._view.workflow_session_service.active_workflow_id

    def reconcile_active_workflow_after_structural_mutation(
        self,
        *,
        force_refresh: bool = False,
    ) -> None:
        """Structurally reconcile the active workflow after model mutation."""

        workflow_id = self._active_workflow_id()
        self._refresh_projected_workflow_surface(
            workflow_id,
            force_refresh,
            None,
        )

    def add_workflow(self) -> str:
        """Create and project a new workflow through the materialization owner."""

        return self._workspace_materializer.add_workflow()

    def reopen_latest_closed_workflow(self) -> bool:
        """Reopen the latest workflow through the materialization owner."""

        return self._workspace_materializer.reopen_latest_closed_workflow()

    def reopen_closed_workflow(self, close_id: str) -> bool:
        """Reopen one buffered workflow through the materialization owner."""

        return self._workspace_materializer.reopen_closed_workflow(close_id)

    def duplicate_workflow(
        self,
        source_workflow_id: str,
        cloned_workflow: object,
        *,
        base_label: str,
    ) -> str | None:
        """Duplicate a workflow through the materialization owner."""

        return self._workspace_materializer.duplicate_workflow(
            source_workflow_id,
            cloned_workflow,
            base_label=base_label,
        )

    def close_workflow(self, workflow_id: str) -> None:
        """Close one workflow through the scoped-resource lifecycle owner."""

        self._closure_coordinator.close_workflow(workflow_id)

    def rename_workflow(self, old_workflow_id: str, proposed_name: str) -> None:
        """Rename one workflow through the label-mutation owner."""

        self._rename_controller.rename_workflow(old_workflow_id, proposed_name)


__all__ = [
    "WorkflowWorkspaceCoordinator",
    "WorkflowTabSwitchDiagnostic",
    "WorkflowWorkspaceView",
]
