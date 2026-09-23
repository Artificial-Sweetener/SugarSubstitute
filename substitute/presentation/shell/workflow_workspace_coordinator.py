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

from substitute.presentation.workflows.workflow_tabs_view import (
    set_workflow_tab_source_text,
    workflow_tab_source_text,
)

from collections.abc import Callable, Mapping, MutableMapping
from time import perf_counter
from typing import Protocol, TypeVar
from typing import cast

from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowSnapshotService,
    WorkflowSessionService,
    WorkflowTabService,
)
from substitute.application.workflows.project_asset_owner_service import (
    ProjectAssetOwnerService,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.resources import cube_icon_resolver
from substitute.presentation.shell.closed_workflow_history import (
    ClosedWorkflowHistory,
    ClosedWorkflowHistoryView,
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
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceDirtyState,
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
from substitute.presentation.shell.workflow_workspace_materializer import (
    WorkflowWorkspaceMaterializationView,
    WorkflowWorkspaceMaterializer,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_exception,
    log_info,
)

_LOGGER = get_logger("presentation.shell.workflow_workspace_coordinator")
WidgetT = TypeVar("WidgetT", bound="LifecycleWidgetProtocol")


class WorkflowTabItemProtocol(Protocol):
    """Describe workflow-tab item operations needed by the coordinator."""

    def routeKey(self) -> str:
        """Return the workflow route key."""

    def text(self) -> str:
        """Return the current tab label."""

    def setRouteKey(self, key: str) -> None:
        """Replace the workflow route key."""

    def setText(self, text: str) -> None:
        """Replace the workflow tab label."""


class WorkflowTabBarProtocol(Protocol):
    """Describe workflow-tab bar APIs used by lifecycle projection."""

    items: list[WorkflowTabItemProtocol]
    itemMap: MutableMapping[str, WorkflowTabItemProtocol]

    def addTab(self, routeKey: str, text: str) -> WorkflowTabItemProtocol:
        """Add a workflow tab and return its item."""

    def insertTab(
        self,
        index: int,
        routeKey: str,
        text: str,
    ) -> WorkflowTabItemProtocol:
        """Insert a workflow tab and return its item."""

    def count(self) -> int:
        """Return the number of workflow tabs."""

    def currentIndex(self) -> int:
        """Return the selected tab index."""

    def tabItem(self, index: int) -> WorkflowTabItemProtocol:
        """Return tab item at index."""

    def workflow_ids_in_order(self) -> list[str]:
        """Return route keys in rendered order."""

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Select workflow tab by id without necessarily emitting user intent."""

    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Remove workflow tab by id without necessarily emitting user intent."""


class WidgetContainerProtocol(Protocol):
    """Describe stacked-widget container behavior used by projection."""

    def setCurrentWidget(self, widget: object) -> None:
        """Set the visible widget."""

    def removeWidget(self, widget: object) -> None:
        """Remove a widget from the container."""


class LifecycleWidgetProtocol(Protocol):
    """Describe Qt widget lifecycle method used during workflow close."""

    def deleteLater(self) -> None:
        """Schedule widget deletion."""


class WorkflowCubeStackProtocol(LifecycleWidgetProtocol, Protocol):
    """Describe cube-stack tab APIs used during workflow duplication."""

    def clear(self) -> None:
        """Remove all cube tabs."""

    def count(self) -> int:
        """Return current cube tab count."""

    def insertTab(
        self,
        index: int,
        *,
        routeKey: str,
        text: str,
        icon: object | None = None,
    ) -> object:
        """Insert one cube tab."""

    def setCurrentIndex(self, index: int) -> None:
        """Select the current cube tab."""


class OverrideManagerProtocol(Protocol):
    """Describe override-manager behavior used during workflow transitions."""

    def detach_override_widgets(self) -> None:
        """Detach live override toolbar controls without destroying cached widgets."""

    def _clear_all_override_widgets(self) -> None:
        """Clear live override toolbar controls."""

    def dispose(self) -> None:
        """Dispose manager-owned widget resources."""


class WorkflowCanvasProjectionCoordinatorProtocol(Protocol):
    """Describe active workflow canvas projection behavior."""

    def project_workflow(self, workflows: object, active_workflow_id: str) -> None:
        """Project one active workflow into shared canvas panes."""


class OutputCanvasProjectionCoordinatorProtocol(Protocol):
    """Describe Output projection state cleanup after workflow closure."""

    def discard_workflow_projection_state(self, workflow_id: str) -> None:
        """Release retained navigation/groups while preserving reopenable images."""


class WorkflowSurfaceRefreshSchedulerProtocol(Protocol):
    """Describe deferred workflow surface refresh scheduling."""

    def request(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        reason: str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Schedule refresh for one workflow route."""

    def cancel(self, workflow_id: str | None = None) -> None:
        """Cancel pending refresh work."""


class WorkflowSurfaceInvalidationProtocol(Protocol):
    """Describe workflow surface invalidation state used by tab policy."""

    def mark_dirty(
        self,
        workflow_id: str,
        surfaces: set[WorkflowSurface] | frozenset[WorkflowSurface],
        reason: WorkflowInvalidationReason,
    ) -> None:
        """Mark workflow surfaces dirty for a specific reason."""

    def mark_clean(
        self,
        workflow_id: str,
        surfaces: set[WorkflowSurface] | frozenset[WorkflowSurface] | None = None,
    ) -> None:
        """Mark selected surfaces, or all surfaces, clean."""

    def dirty_state(self, workflow_id: str) -> WorkflowSurfaceDirtyState:
        """Return current dirty state for one workflow."""

    def is_clean(self, workflow_id: str) -> bool:
        """Return whether no tracked surface has pending maintenance."""

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Move pending maintenance state to a renamed workflow id."""

    def remove_workflow(self, workflow_id: str) -> None:
        """Forget pending maintenance state for a closed workflow."""


class GenerationProgressProjectionProtocol(Protocol):
    """Describe generation progress projection owned by action controller."""

    def project_active_workflow_progress(self) -> None:
        """Project selected workflow progress onto shell progress surfaces."""


class CanvasRouteControllerProtocol(Protocol):
    """Describe attached canvas route availability projection."""

    def refresh_input_canvas_availability(self) -> None:
        """Refresh active workflow input-canvas availability."""


class WorkflowWorkspaceView(Protocol):
    """Describe shell dependencies required for workflow lifecycle projection."""

    closed_workflow_buffer: ClosedWorkflowBuffer
    closed_workflow_snapshot_service: ClosedWorkflowSnapshotService
    workflow_tab_service: WorkflowTabService
    workflow_session_service: WorkflowSessionService[object]
    workflow_tabbar: WorkflowTabBarProtocol
    workflow_canvas_projection_coordinator: WorkflowCanvasProjectionCoordinatorProtocol
    generation_action_controller: GenerationProgressProjectionProtocol
    canvas_route_controller: CanvasRouteControllerProtocol
    output_canvas_projection_coordinator: OutputCanvasProjectionCoordinatorProtocol
    cube_stacks: dict[str, WorkflowCubeStackProtocol]
    editor_panels: dict[str, LifecycleWidgetProtocol]
    override_managers: dict[str, OverrideManagerProtocol | None]
    cube_icon_factory: cube_icon_resolver.CubeIconFactoryProtocol
    cube_stack_container: WidgetContainerProtocol
    editor_panel_container: WidgetContainerProtocol

    def ensure_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> tuple[object, object]:
        """Create deferred workflow-scoped widgets before route activation."""

    def position_search_box(self) -> None:
        """Reposition the floating search box."""


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
        """Close one workflow and project the selected successor exactly once."""

        view = self._view
        unsaved_controller = getattr(view, "unsaved_work_controller", None)
        confirm_close = getattr(unsaved_controller, "confirm_workflow_close", None)
        if callable(confirm_close) and not confirm_close(workflow_id):
            return
        ordered_ids = self._workflow_ids_in_order()
        close_push_result = self._closed_workflow_history.buffer_workflow(
            workflow_id,
            ordered_ids,
        )
        transition = view.workflow_session_service.close_workflow(
            workflow_id,
            ordered_ids,
        )
        self._dispose_workflow_ui(workflow_id)
        self._surface_invalidation_service.remove_workflow(workflow_id)
        view.output_canvas_projection_coordinator.discard_workflow_projection_state(
            workflow_id
        )
        unsaved_work_service = getattr(view, "unsaved_work_service", None)
        remove_document_state = getattr(unsaved_work_service, "remove", None)
        if callable(remove_document_state):
            remove_document_state(workflow_id)
        workflow_progress_service = getattr(view, "workflow_progress_service", None)
        remove_workflow_progress = getattr(
            workflow_progress_service,
            "remove_workflow",
            None,
        )
        if callable(remove_workflow_progress):
            remove_workflow_progress(workflow_id)
        output_image_pipeline = getattr(view, "output_image_pipeline", None)
        remove_output_workflow = getattr(output_image_pipeline, "remove_workflow", None)
        if callable(remove_output_workflow):
            remove_output_workflow(workflow_id)
        if transition.removed_workflow is not None:
            if close_push_result is not None and close_push_result.accepted:
                self._closed_workflow_history.cleanup_evicted(
                    close_push_result.evicted_records
                )
            else:
                self._closed_workflow_history.prune_workflow_images(
                    workflow_id,
                    transition.removed_workflow,
                )
        self._remove_workflow_activity(workflow_id)
        view.workflow_tabbar.remove_workflow_tab(workflow_id, emit=False)

        if transition.next_active_workflow_id is None:
            self.add_workflow()
            return
        if transition.active_changed:
            self.project_workflow(
                transition.next_active_workflow_id,
                force_refresh=True,
            )

    def rename_workflow(self, old_workflow_id: str, proposed_name: str) -> None:
        """Rename one workflow label without changing its immutable identity."""

        view = self._view
        tab_item = view.workflow_tabbar.itemMap.get(old_workflow_id)
        if tab_item is None:
            return
        old_label = workflow_tab_source_text(tab_item)
        existing_labels = {
            workflow_tab_source_text(item)
            for workflow_id, item in view.workflow_tabbar.itemMap.items()
            if workflow_id != old_workflow_id
        }
        decision = view.workflow_tab_service.resolve_inline_rename(
            old_workflow_id=old_workflow_id,
            proposed_name=proposed_name,
            existing_labels=existing_labels,
        )
        if not decision.accepted:
            set_workflow_tab_source_text(tab_item, old_label)
            return
        if old_label == decision.tab_label:
            return
        workflow = view.workflow_session_service.get_workflow(old_workflow_id)
        if isinstance(workflow, WorkflowState):
            ProjectAssetOwnerService().pin_legacy_owners(
                workflow,
                storage_owner=old_label,
            )
        set_workflow_tab_source_text(tab_item, decision.tab_label)
        unsaved_work_service = getattr(view, "unsaved_work_service", None)
        mark_document_dirty = getattr(unsaved_work_service, "mark_dirty", None)
        if callable(mark_document_dirty):
            mark_document_dirty(old_workflow_id)
        log_info(
            _LOGGER,
            "Renamed workflow display label without changing identity",
            workflow_id=old_workflow_id,
            old_label=old_label,
            new_label=decision.tab_label,
        )

    def _remove_workflow_activity(self, workflow_id: str) -> None:
        """Remove unread activity for a closed workflow when supported."""

        activity_service = getattr(self._view, "workflow_activity_service", None)
        remove_workflow = getattr(activity_service, "remove_workflow", None)
        if callable(remove_workflow):
            remove_workflow(workflow_id)

    def _workflow_ids_in_order(self) -> list[str]:
        """Return workflow ids from the tab bar with fallback for test doubles."""

        tabbar = self._view.workflow_tabbar
        workflow_ids_in_order = getattr(tabbar, "workflow_ids_in_order", None)
        if callable(workflow_ids_in_order):
            return list(workflow_ids_in_order())
        return [item.routeKey() for item in tabbar.items]

    def _dispose_workflow_ui(self, workflow_id: str) -> None:
        """Dispose workflow-scoped widgets and manager resources."""

        view = self._view
        self._remove_widget(
            workflow_id,
            mapping=view.cube_stacks,
            container=view.cube_stack_container,
        )
        self._remove_widget(
            workflow_id,
            mapping=view.editor_panels,
            container=view.editor_panel_container,
        )
        manager = view.override_managers.pop(workflow_id, None)
        if manager is None:
            return
        try:
            manager.dispose()
        except (AttributeError, RuntimeError, TypeError) as error:
            log_exception(
                _LOGGER,
                "Failed to dispose override manager during workflow close",
                workflow_id=workflow_id,
                error=error,
            )

    @staticmethod
    def _remove_widget(
        workflow_id: str,
        *,
        mapping: MutableMapping[str, WidgetT],
        container: WidgetContainerProtocol,
    ) -> None:
        """Remove one workflow-scoped widget from mapping and container."""

        widget = mapping.pop(workflow_id, None)
        if widget is None:
            return
        container.removeWidget(widget)
        widget.deleteLater()


__all__ = [
    "WorkflowWorkspaceCoordinator",
    "WorkflowTabSwitchDiagnostic",
    "WorkflowWorkspaceView",
]
