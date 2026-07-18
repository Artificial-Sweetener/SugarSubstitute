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

import json
import os
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Protocol, TypeVar
from typing import cast
from uuid import uuid4

from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowPushResult,
    ClosedWorkflowRecord,
    ClosedWorkflowSnapshotError,
    ClosedWorkflowSnapshotService,
    DEFAULT_WORKFLOW_TAB_LABEL,
    WorkflowSessionService,
    WorkflowTabService,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    WorkflowSnapshot,
)
from substitute.presentation.shell.cube_stack_presenter import (
    CubeIconFactoryProtocol,
    CubeStackPresenter,
    CubeStackProtocol,
    CubeTabIconResolver,
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
from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)
from substitute.presentation.shell.main_window_generation_availability_adapter import (
    MainWindowGenerationAvailabilityAdapter,
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
from substitute.presentation.shell.main_window_workflow_session_state_adapter import (
    MainWindowWorkflowSessionStateAdapter,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)
from substitute.presentation.shell.workflow_ui_factory import workflow_ui_factory_for
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
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.workflow_workspace_coordinator")
_SLOW_DUPLICATE_PHASE_MS = 100.0
_SLOW_DUPLICATE_TOTAL_MS = 250.0
_WORKFLOW_TAB_PERF_ENV = "SUGARSUBSTITUTE_WORKFLOW_TAB_PERF"
_WORKFLOW_TAB_PERF_PATH_ENV = "SUGARSUBSTITUTE_WORKFLOW_TAB_PERF_PATH"
_DEFAULT_WORKFLOW_TAB_PERF_PATH = (
    Path("artifacts") / "workflow_tab_profile" / "live_tab_switches.jsonl"
)
WidgetT = TypeVar("WidgetT", bound="LifecycleWidgetProtocol")


@dataclass(frozen=True, slots=True)
class WorkflowTabSwitchDiagnostic:
    """Record non-fragile timing and work counters for one workflow projection."""

    workflow_id: str
    source: str
    tab_intent_received_at: float
    active_workflow_update_elapsed_ms: float
    route_projection_elapsed_ms: float
    canvas_projection_elapsed_ms: float
    ensure_workflow_ui_elapsed_ms: float
    show_route_elapsed_ms: float
    tab_select_elapsed_ms: float
    cube_stack_swap_elapsed_ms: float
    editor_panel_swap_elapsed_ms: float
    override_projection_elapsed_ms: float
    input_canvas_availability_elapsed_ms: float
    overlay_refresh_elapsed_ms: float
    activity_badge_elapsed_ms: float
    overrides_projected: bool
    widgets_created: bool
    editor_rebuilt: bool
    deferred_requests: int
    info_logs: int = 0


def _log_duplicate_phase_timing(
    message: str,
    *,
    started_at: float,
    slow_threshold_ms: float = _SLOW_DUPLICATE_PHASE_MS,
    **context: object,
) -> float:
    """Log coordinator duplicate phase duration with slow-phase warnings."""

    elapsed_ms = elapsed_ms_since(started_at)
    log_context = dict(context)
    log_context["elapsed_ms"] = f"{elapsed_ms:.3f}"
    log_context["slow_threshold_ms"] = f"{slow_threshold_ms:.3f}"
    if elapsed_ms >= slow_threshold_ms:
        log_warning(_LOGGER, f"{message} slowly", **log_context)
    else:
        log_info(_LOGGER, message, **log_context)
    return elapsed_ms


def _workflow_tab_perf_enabled() -> bool:
    """Return whether live workflow-tab performance rows should be persisted."""

    return os.environ.get(_WORKFLOW_TAB_PERF_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _workflow_tab_perf_path() -> Path:
    """Return the JSONL output path for live workflow-tab performance rows."""

    configured_path = os.environ.get(_WORKFLOW_TAB_PERF_PATH_ENV, "").strip()
    path = Path(configured_path) if configured_path else _DEFAULT_WORKFLOW_TAB_PERF_PATH
    if path.is_absolute():
        return path
    return Path.cwd() / path


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
    """Describe Output canvas projection and pruning behavior."""

    def prune_closed_workflow_images(
        self,
        closed_workflow_id: str,
        closed_workflow: object,
        remaining_workflows: object,
    ) -> None:
        """Prune images that only belonged to a closed workflow."""


class InputCanvasStateServiceProtocol(Protocol):
    """Describe Input catalog pruning behavior."""

    def prune_closed_workflow_images(
        self,
        closed_workflow: object,
        remaining_workflows: object,
    ) -> None:
        """Prune Input images that only belonged to a closed workflow."""


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


class WorkflowSnapshotCaptureProtocol(Protocol):
    """Describe snapshot reads needed while closing a workflow."""

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return the tab label for one workflow id."""

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return the active cube alias for one workflow."""

    def editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return restorable editor viewport state for one workflow."""

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return restorable input image references for one workflow."""

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return restorable input mask references for one workflow."""

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return restorable output image references for one workflow."""


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
    input_canvas_state_service: InputCanvasStateServiceProtocol
    session_snapshot_capture_adapter: WorkflowSnapshotCaptureProtocol
    cube_stacks: dict[str, WorkflowCubeStackProtocol]
    editor_panels: dict[str, LifecycleWidgetProtocol]
    override_managers: dict[str, OverrideManagerProtocol | None]
    cube_icon_factory: CubeIconFactoryProtocol
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
        self._closed_workflow_buffer = getattr(
            view,
            "closed_workflow_buffer",
            ClosedWorkflowBuffer(),
        )
        self._closed_workflow_snapshot_service = getattr(
            view,
            "closed_workflow_snapshot_service",
            ClosedWorkflowSnapshotService(),
        )
        self._last_tab_switch_diagnostic: WorkflowTabSwitchDiagnostic | None = None
        self._tab_switch_diagnostics: list[WorkflowTabSwitchDiagnostic] = []
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
        self._surface_reconciler = surface_reconciler or WorkflowSurfaceReconciler(
            MainWindowWorkflowSessionStateAdapter(view),
            canvas_port=canvas_adapter,
            editor_port=MainWindowEditorSurfaceAdapter(view),
            override_port=override_adapter,
            generation_port=MainWindowGenerationAvailabilityAdapter(view),
            surface_invalidation_service=self._surface_invalidation_service,
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
                self._record_tab_switch_diagnostic(
                    workflow_id=workflow_id,
                    source=source,
                    tab_intent_received_at=tab_intent_received_at,
                    active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
                    route_projection_elapsed_ms=(
                        route_projection.route_projection_elapsed_ms
                    ),
                    canvas_projection_elapsed_ms=(
                        route_projection.canvas_projection_elapsed_ms
                    ),
                    ensure_workflow_ui_elapsed_ms=(
                        route_projection.ensure_workflow_ui_elapsed_ms
                    ),
                    show_route_elapsed_ms=route_projection.show_route_elapsed_ms,
                    tab_select_elapsed_ms=route_projection.tab_select_elapsed_ms,
                    cube_stack_swap_elapsed_ms=(
                        route_projection.cube_stack_swap_elapsed_ms
                    ),
                    editor_panel_swap_elapsed_ms=(
                        route_projection.editor_panel_swap_elapsed_ms
                    ),
                    override_projection_elapsed_ms=(
                        route_projection.override_projection_elapsed_ms
                    ),
                    input_canvas_availability_elapsed_ms=(
                        route_projection.input_canvas_availability_elapsed_ms
                    ),
                    overlay_refresh_elapsed_ms=(
                        route_projection.overlay_refresh_elapsed_ms
                    ),
                    activity_badge_elapsed_ms=(
                        route_projection.activity_badge_elapsed_ms
                    ),
                    overrides_projected=route_projection.overrides_projected,
                    widgets_created=route_projection.created_widgets,
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
            self._record_tab_switch_diagnostic(
                workflow_id=workflow_id,
                source=source,
                tab_intent_received_at=tab_intent_received_at,
                active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
                route_projection_elapsed_ms=route_projection.route_projection_elapsed_ms,
                canvas_projection_elapsed_ms=(
                    route_projection.canvas_projection_elapsed_ms
                ),
                ensure_workflow_ui_elapsed_ms=(
                    route_projection.ensure_workflow_ui_elapsed_ms
                ),
                show_route_elapsed_ms=route_projection.show_route_elapsed_ms,
                tab_select_elapsed_ms=route_projection.tab_select_elapsed_ms,
                cube_stack_swap_elapsed_ms=(
                    route_projection.cube_stack_swap_elapsed_ms
                ),
                editor_panel_swap_elapsed_ms=(
                    route_projection.editor_panel_swap_elapsed_ms
                ),
                override_projection_elapsed_ms=(
                    route_projection.override_projection_elapsed_ms
                ),
                input_canvas_availability_elapsed_ms=(
                    route_projection.input_canvas_availability_elapsed_ms
                ),
                overlay_refresh_elapsed_ms=route_projection.overlay_refresh_elapsed_ms,
                activity_badge_elapsed_ms=route_projection.activity_badge_elapsed_ms,
                overrides_projected=route_projection.overrides_projected,
                widgets_created=route_projection.created_widgets,
                editor_rebuilt=False,
                deferred_requests=1,
            )
            return
        self._refresh_projected_workflow_surface(
            workflow_id,
            force_refresh,
            on_surface_complete,
        )
        self._record_tab_switch_diagnostic(
            workflow_id=workflow_id,
            source=source,
            tab_intent_received_at=tab_intent_received_at,
            active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
            route_projection_elapsed_ms=route_projection.route_projection_elapsed_ms,
            canvas_projection_elapsed_ms=route_projection.canvas_projection_elapsed_ms,
            ensure_workflow_ui_elapsed_ms=(
                route_projection.ensure_workflow_ui_elapsed_ms
            ),
            show_route_elapsed_ms=route_projection.show_route_elapsed_ms,
            tab_select_elapsed_ms=route_projection.tab_select_elapsed_ms,
            cube_stack_swap_elapsed_ms=route_projection.cube_stack_swap_elapsed_ms,
            editor_panel_swap_elapsed_ms=route_projection.editor_panel_swap_elapsed_ms,
            override_projection_elapsed_ms=(
                route_projection.override_projection_elapsed_ms
            ),
            input_canvas_availability_elapsed_ms=(
                route_projection.input_canvas_availability_elapsed_ms
            ),
            overlay_refresh_elapsed_ms=route_projection.overlay_refresh_elapsed_ms,
            activity_badge_elapsed_ms=route_projection.activity_badge_elapsed_ms,
            overrides_projected=route_projection.overrides_projected,
            widgets_created=route_projection.created_widgets,
            editor_rebuilt=force_refresh or on_surface_complete is not None,
            deferred_requests=0,
        )

    @property
    def last_tab_switch_diagnostic(self) -> WorkflowTabSwitchDiagnostic | None:
        """Return the latest workflow projection diagnostic row."""

        return self._last_tab_switch_diagnostic

    def tab_switch_diagnostics(self) -> tuple[WorkflowTabSwitchDiagnostic, ...]:
        """Return recorded workflow projection diagnostics."""

        return tuple(self._tab_switch_diagnostics)

    def _record_tab_switch_diagnostic(
        self,
        *,
        workflow_id: str,
        source: str,
        tab_intent_received_at: float | None,
        active_workflow_update_elapsed_ms: float,
        route_projection_elapsed_ms: float,
        canvas_projection_elapsed_ms: float,
        ensure_workflow_ui_elapsed_ms: float,
        show_route_elapsed_ms: float,
        tab_select_elapsed_ms: float,
        cube_stack_swap_elapsed_ms: float,
        editor_panel_swap_elapsed_ms: float,
        override_projection_elapsed_ms: float,
        input_canvas_availability_elapsed_ms: float,
        overlay_refresh_elapsed_ms: float,
        activity_badge_elapsed_ms: float,
        overrides_projected: bool,
        widgets_created: bool,
        editor_rebuilt: bool,
        deferred_requests: int,
    ) -> None:
        """Record diagnostic fields for profiling without log scraping."""

        diagnostic = WorkflowTabSwitchDiagnostic(
            workflow_id=workflow_id,
            source=source,
            tab_intent_received_at=tab_intent_received_at or perf_counter(),
            active_workflow_update_elapsed_ms=active_workflow_update_elapsed_ms,
            route_projection_elapsed_ms=route_projection_elapsed_ms,
            canvas_projection_elapsed_ms=canvas_projection_elapsed_ms,
            ensure_workflow_ui_elapsed_ms=ensure_workflow_ui_elapsed_ms,
            show_route_elapsed_ms=show_route_elapsed_ms,
            tab_select_elapsed_ms=tab_select_elapsed_ms,
            cube_stack_swap_elapsed_ms=cube_stack_swap_elapsed_ms,
            editor_panel_swap_elapsed_ms=editor_panel_swap_elapsed_ms,
            override_projection_elapsed_ms=override_projection_elapsed_ms,
            input_canvas_availability_elapsed_ms=input_canvas_availability_elapsed_ms,
            overlay_refresh_elapsed_ms=overlay_refresh_elapsed_ms,
            activity_badge_elapsed_ms=activity_badge_elapsed_ms,
            overrides_projected=overrides_projected,
            widgets_created=widgets_created,
            editor_rebuilt=editor_rebuilt,
            deferred_requests=deferred_requests,
        )
        self._last_tab_switch_diagnostic = diagnostic
        self._tab_switch_diagnostics.append(diagnostic)
        log_debug(
            _LOGGER,
            "workflow tab switch diagnostic captured",
            workflow_id=workflow_id,
            source=source,
            active_workflow_update_elapsed_ms=(
                f"{active_workflow_update_elapsed_ms:.3f}"
            ),
            route_projection_elapsed_ms=f"{route_projection_elapsed_ms:.3f}",
            canvas_projection_elapsed_ms=f"{canvas_projection_elapsed_ms:.3f}",
            ensure_workflow_ui_elapsed_ms=f"{ensure_workflow_ui_elapsed_ms:.3f}",
            show_route_elapsed_ms=f"{show_route_elapsed_ms:.3f}",
            tab_select_elapsed_ms=f"{tab_select_elapsed_ms:.3f}",
            cube_stack_swap_elapsed_ms=f"{cube_stack_swap_elapsed_ms:.3f}",
            editor_panel_swap_elapsed_ms=f"{editor_panel_swap_elapsed_ms:.3f}",
            override_projection_elapsed_ms=f"{override_projection_elapsed_ms:.3f}",
            input_canvas_availability_elapsed_ms=(
                f"{input_canvas_availability_elapsed_ms:.3f}"
            ),
            overlay_refresh_elapsed_ms=f"{overlay_refresh_elapsed_ms:.3f}",
            activity_badge_elapsed_ms=f"{activity_badge_elapsed_ms:.3f}",
            overrides_projected=overrides_projected,
            widgets_created=widgets_created,
            editor_rebuilt=editor_rebuilt,
            deferred_requests=deferred_requests,
        )
        self._write_tab_switch_perf_diagnostic(diagnostic)

    def _write_tab_switch_perf_diagnostic(
        self,
        diagnostic: WorkflowTabSwitchDiagnostic,
    ) -> None:
        """Append one live tab-switch performance row when env-gated diagnostics are on."""

        if not _workflow_tab_perf_enabled():
            return
        path = _workflow_tab_perf_path()
        payload = {
            "captured_at": datetime.now(UTC).isoformat(),
            **asdict(diagnostic),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
        except OSError as error:
            log_warning(
                _LOGGER,
                "Failed to write workflow tab performance diagnostic",
                path=str(path),
                error=repr(error),
            )

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
        """Create, register, activate, and project a new workflow."""

        view = self._view
        outgoing_manager = view.override_managers.get(
            view.workflow_session_service.active_workflow_id
        )
        if outgoing_manager is not None:
            outgoing_manager._clear_all_override_widgets()

        planned_tab = view.workflow_tab_service.plan_new_workflow_tab(
            base_name=DEFAULT_WORKFLOW_TAB_LABEL,
            existing_labels={item.text() for item in view.workflow_tabbar.items},
            existing_workflow_ids=view.workflow_session_service.workflows.keys(),
        )
        transition = view.workflow_session_service.add_workflow(
            planned_tab.workflow_id,
            activate=True,
        )
        view.workflow_tabbar.addTab(planned_tab.workflow_id, planned_tab.tab_label)
        workflow_ui_factory_for(view).create_workflow_ui(
            transition.workflow_id,
            set_as_current=True,
        )
        self.project_workflow(transition.workflow_id, force_refresh=True)
        return transition.workflow_id

    def reopen_latest_closed_workflow(self) -> bool:
        """Reopen the most recently closed workflow when available."""

        record = self._closed_workflow_buffer.pop_latest()
        if record is None:
            self._sync_reopen_closed_workflow_action()
            log_info(
                _LOGGER,
                "Reopen closed workflow skipped because buffer was empty",
                operation="reopen_closed_workflow",
            )
            return False
        return self._reopen_closed_workflow_record(record)

    def reopen_closed_workflow(self, close_id: str) -> bool:
        """Reopen a specific closed workflow record when available."""

        record = self._closed_workflow_buffer.pop(close_id)
        if record is None:
            self._sync_reopen_closed_workflow_action()
            log_info(
                _LOGGER,
                "Reopen closed workflow skipped because record was missing",
                operation="reopen_closed_workflow",
                close_id=close_id,
            )
            return False
        return self._reopen_closed_workflow_record(record)

    def _reopen_closed_workflow_record(self, record: ClosedWorkflowRecord) -> bool:
        """Decode, register, materialize, and project one closed workflow record."""

        view = self._view
        try:
            snapshot = self._closed_workflow_snapshot_service.decode(
                record.snapshot_payload
            )
        except ClosedWorkflowSnapshotError as error:
            log_warning(
                _LOGGER,
                "Failed to decode closed workflow for reopen",
                operation="reopen_closed_workflow",
                close_id=record.close_id,
                workflow_id=record.workflow_id,
                tab_label=record.tab_label,
                payload_size_bytes=record.payload_size_bytes,
                error=repr(error),
            )
            self._sync_reopen_closed_workflow_action()
            return False
        workflow_id = self._unique_reopened_workflow_id(snapshot.workflow_id)
        if workflow_id != snapshot.workflow_id:
            log_info(
                _LOGGER,
                "Reopened workflow id collision resolved",
                operation="reopen_closed_workflow",
                close_id=record.close_id,
                workflow_id=snapshot.workflow_id,
                new_workflow_id=workflow_id,
            )
            snapshot = self._closed_workflow_snapshot_service.rekey_snapshot(
                snapshot,
                new_workflow_id=workflow_id,
            )
        outgoing_manager = view.override_managers.get(
            view.workflow_session_service.active_workflow_id
        )
        if outgoing_manager is not None:
            outgoing_manager._clear_all_override_widgets()
        generation_feedback_presenter_for(view).clear_all_model_field_load_progress()
        try:
            transition = view.workflow_session_service.add_existing_workflow(
                workflow_id,
                snapshot.workflow,
                activate=True,
            )
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Failed to register reopened workflow",
                operation="reopen_closed_workflow",
                close_id=record.close_id,
                workflow_id=workflow_id,
                error=repr(error),
            )
            return False
        self._insert_reopened_workflow_tab(
            transition.workflow_id,
            snapshot.tab_label,
            record.tab_index,
        )
        workflow_ui_factory_for(view).create_workflow_ui(
            transition.workflow_id,
            set_as_current=True,
        )
        self._materialize_workflow_cube_stack(
            transition.workflow_id,
            snapshot.workflow,
            active_cube_alias=snapshot.active_cube_alias,
        )
        self.project_workflow(
            transition.workflow_id,
            force_refresh=True,
            source="reopen_closed_workflow",
        )
        log_info(
            _LOGGER,
            "Reopened closed workflow",
            operation="reopen_closed_workflow",
            close_id=record.close_id,
            workflow_id=record.workflow_id,
            new_workflow_id=transition.workflow_id,
            tab_label=snapshot.tab_label,
            tab_index=record.tab_index,
        )
        self._sync_reopen_closed_workflow_action()
        return True

    def _insert_reopened_workflow_tab(
        self,
        workflow_id: str,
        tab_label: str,
        preferred_index: int,
    ) -> None:
        """Insert reopened workflow tab at its preferred index when practical."""

        tabbar = self._view.workflow_tabbar
        index = max(0, min(preferred_index, tabbar.count()))
        insert_tab = getattr(tabbar, "insertTab", None)
        if callable(insert_tab):
            insert_tab(index, workflow_id, tab_label)
            return
        tabbar.addTab(workflow_id, tab_label)

    def _unique_reopened_workflow_id(self, preferred_workflow_id: str) -> str:
        """Return a workflow id that does not collide with open workflow ids."""

        existing_ids = self._view.workflow_session_service.workflows.keys()
        if preferred_workflow_id and preferred_workflow_id not in existing_ids:
            return preferred_workflow_id
        base = preferred_workflow_id or "reopened_workflow"
        candidate = f"{base}_reopened"
        if candidate not in existing_ids:
            return candidate
        counter = 2
        while True:
            candidate = f"{base}_reopened_{counter}"
            if candidate not in existing_ids:
                return candidate
            counter += 1

    def _sync_reopen_closed_workflow_action(self) -> None:
        """Refresh presentation command enablement for closed workflow reopen."""

        frame_integration_controller = getattr(
            self._view,
            "shell_frame_integration_controller",
            None,
        )
        set_enabled = getattr(
            frame_integration_controller,
            "set_reopen_closed_workflow_enabled",
            None,
        )
        if callable(set_enabled):
            set_enabled(bool(self._closed_workflow_buffer.summaries()))

    def duplicate_workflow(
        self,
        source_workflow_id: str,
        cloned_workflow: object,
        *,
        base_label: str,
    ) -> str | None:
        """Create, register, activate, and project a duplicated workflow."""

        duplicate_started_at = perf_counter()
        view = self._view
        log_info(
            _LOGGER,
            "Workflow duplicate coordinator started",
            source_workflow_id=source_workflow_id,
            base_label=base_label,
            cube_count=len(getattr(cloned_workflow, "cubes", {}) or {}),
            stack_order_count=len(getattr(cloned_workflow, "stack_order", []) or []),
        )
        if source_workflow_id not in view.workflow_session_service.workflows:
            log_warning(
                _LOGGER,
                "Skipped workflow duplication because source workflow was missing",
                source_workflow_id=source_workflow_id,
                base_label=base_label,
            )
            return None
        outgoing_manager = view.override_managers.get(
            view.workflow_session_service.active_workflow_id
        )
        if outgoing_manager is not None:
            outgoing_manager._clear_all_override_widgets()

        planned_tab = view.workflow_tab_service.plan_new_workflow_tab(
            base_name=base_label,
            existing_labels={item.text() for item in view.workflow_tabbar.items},
            existing_workflow_ids=view.workflow_session_service.workflows.keys(),
        )
        log_info(
            _LOGGER,
            "Workflow duplicate tab planned",
            source_workflow_id=source_workflow_id,
            duplicated_workflow_id=planned_tab.workflow_id,
            base_label=base_label,
            tab_label=planned_tab.tab_label,
        )
        phase_started_at = perf_counter()
        transition = view.workflow_session_service.add_existing_workflow(
            planned_tab.workflow_id,
            cloned_workflow,
            activate=True,
        )
        _log_duplicate_phase_timing(
            "Workflow duplicate existing workflow registered",
            started_at=phase_started_at,
            source_workflow_id=source_workflow_id,
            duplicated_workflow_id=transition.workflow_id,
            base_label=base_label,
            tab_label=planned_tab.tab_label,
        )
        view.workflow_tabbar.addTab(planned_tab.workflow_id, planned_tab.tab_label)
        workflow_ui_factory_for(view).create_workflow_ui(
            transition.workflow_id,
            set_as_current=True,
        )
        log_info(
            _LOGGER,
            "Workflow duplicate UI created",
            source_workflow_id=source_workflow_id,
            duplicated_workflow_id=transition.workflow_id,
            base_label=base_label,
            tab_label=planned_tab.tab_label,
            target_cube_stack_exists=transition.workflow_id in view.cube_stacks,
            active_editor_panel_exists=(
                getattr(view, "active_editor_panel", None) is not None
            ),
            active_override_manager_exists=(
                getattr(view, "active_override_manager", None) is not None
            ),
        )
        phase_started_at = perf_counter()
        self._materialize_workflow_cube_stack(
            transition.workflow_id,
            cloned_workflow,
            active_cube_alias=None,
        )
        _log_duplicate_phase_timing(
            "Workflow duplicate cube-stack materialization phase completed",
            started_at=phase_started_at,
            source_workflow_id=source_workflow_id,
            duplicated_workflow_id=transition.workflow_id,
            base_label=base_label,
            tab_label=planned_tab.tab_label,
        )
        phase_started_at = perf_counter()
        log_info(
            _LOGGER,
            "Workflow duplicate projection started",
            source_workflow_id=source_workflow_id,
            duplicated_workflow_id=transition.workflow_id,
            base_label=base_label,
            tab_label=planned_tab.tab_label,
        )
        self.project_workflow(transition.workflow_id, force_refresh=True)
        _log_duplicate_phase_timing(
            "Workflow duplicate projection completed",
            started_at=phase_started_at,
            source_workflow_id=source_workflow_id,
            duplicated_workflow_id=transition.workflow_id,
            base_label=base_label,
            tab_label=planned_tab.tab_label,
        )
        _log_duplicate_phase_timing(
            "Workflow duplicate coordinator completed",
            started_at=duplicate_started_at,
            slow_threshold_ms=_SLOW_DUPLICATE_TOTAL_MS,
            source_workflow_id=source_workflow_id,
            duplicated_workflow_id=transition.workflow_id,
            base_label=base_label,
            tab_label=planned_tab.tab_label,
            cube_count=len(getattr(cloned_workflow, "cubes", {}) or {}),
            stack_order_count=len(getattr(cloned_workflow, "stack_order", []) or []),
        )
        return transition.workflow_id

    def _materialize_workflow_cube_stack(
        self,
        workflow_id: str,
        workflow: object,
        *,
        active_cube_alias: str | None,
    ) -> None:
        """Populate cube-stack tabs from workflow state."""

        view = self._view
        cube_stack = view.cube_stacks.get(workflow_id)
        if cube_stack is None:
            log_warning(
                _LOGGER,
                "Skipped duplicate cube-stack materialization because stack was missing",
                workflow_id=workflow_id,
            )
            return
        cubes = getattr(workflow, "cubes", {})
        stack_order = list(getattr(workflow, "stack_order", ()) or [])
        if not isinstance(cubes, dict):
            log_warning(
                _LOGGER,
                "Skipped duplicate cube-stack materialization because cube state was invalid",
                workflow_id=workflow_id,
                cube_state_type=type(cubes).__name__,
            )
            return

        log_info(
            _LOGGER,
            "Workflow duplicate cube-stack materialization started",
            workflow_id=workflow_id,
            cube_count=len(cubes),
            stack_order_count=len(stack_order),
        )
        resolved_active_cube_alias = active_cube_alias
        if resolved_active_cube_alias not in stack_order:
            resolved_active_cube_alias = stack_order[-1] if stack_order else None
        result = CubeStackPresenter(
            icon_resolver=CubeTabIconResolver(
                cube_icon_factory=getattr(view, "cube_icon_factory", None),
            ),
        ).rebuild_stack(
            cast(CubeStackProtocol, cube_stack),
            workflow_id=workflow_id,
            workflow=workflow,
            active_cube_alias=resolved_active_cube_alias,
        )
        log_info(
            _LOGGER,
            "Materialized duplicated workflow cube stack",
            workflow_id=workflow_id,
            inserted_count=result.inserted_count,
            stack_order_count=len(stack_order),
            warning_count=len(result.warnings),
        )

    def close_workflow(self, workflow_id: str) -> None:
        """Close one workflow and project the selected successor exactly once."""

        view = self._view
        ordered_ids = self._workflow_ids_in_order()
        close_push_result = self._buffer_closed_workflow(
            workflow_id,
            ordered_ids,
        )
        transition = view.workflow_session_service.close_workflow(
            workflow_id,
            ordered_ids,
        )
        self._dispose_workflow_ui(workflow_id)
        self._surface_invalidation_service.remove_workflow(workflow_id)
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
                self._cleanup_closed_workflow_records(close_push_result.evicted_records)
            else:
                self._prune_closed_workflow_images(
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
        """Resolve inline rename and propagate accepted workflow id changes."""

        view = self._view
        decision = view.workflow_tab_service.resolve_inline_rename(
            old_workflow_id=old_workflow_id,
            proposed_name=proposed_name,
            existing_tab_keys=view.workflow_tabbar.itemMap.keys(),
            existing_workflow_ids=view.workflow_session_service.workflows.keys(),
        )
        tab_item = view.workflow_tabbar.itemMap.get(old_workflow_id)
        if not decision.accepted:
            if tab_item is not None:
                tab_item.setText(old_workflow_id)
            return
        if tab_item is None:
            return

        if old_workflow_id == decision.workflow_id:
            tab_item.setText(decision.tab_label)
            return

        tab_item.setText(decision.tab_label)
        tab_item.setRouteKey(decision.workflow_id)
        view.workflow_tab_service.rekey_mapping(
            view.workflow_tabbar.itemMap,
            old_key=old_workflow_id,
            new_key=decision.workflow_id,
        )
        transition = view.workflow_session_service.rename_workflow(
            old_workflow_id,
            decision.workflow_id,
        )
        if transition is None:
            return
        self._rename_workflow_activity(old_workflow_id, decision.workflow_id)
        self._surface_invalidation_service.rename_workflow(
            old_workflow_id,
            decision.workflow_id,
        )
        workflow_progress_service = getattr(view, "workflow_progress_service", None)
        rename_workflow_progress = getattr(
            workflow_progress_service,
            "rename_workflow",
            None,
        )
        if callable(rename_workflow_progress):
            rename_workflow_progress(old_workflow_id, decision.workflow_id)
        output_image_pipeline = getattr(view, "output_image_pipeline", None)
        rename_output_workflow = getattr(output_image_pipeline, "rename_workflow", None)
        if callable(rename_output_workflow):
            rename_output_workflow(old_workflow_id, decision.workflow_id)
        view.workflow_tab_service.rekey_workflow_scoped_maps(
            old_workflow_id=old_workflow_id,
            new_workflow_id=decision.workflow_id,
            mappings=(
                cast(MutableMapping[str, object], view.editor_panels),
                cast(MutableMapping[str, object], view.cube_stacks),
                cast(MutableMapping[str, object], view.override_managers),
            ),
        )
        if transition.active_changed:
            view.workflow_tabbar.select_workflow_tab(decision.workflow_id, emit=False)

    def _buffer_closed_workflow(
        self,
        workflow_id: str,
        ordered_ids: list[str],
    ) -> ClosedWorkflowPushResult | None:
        """Serialize and retain one closing workflow before destructive cleanup."""

        workflow = self._workflow_for_close(workflow_id)
        if workflow is None:
            log_warning(
                _LOGGER,
                "Skipped closed workflow buffering because workflow was missing",
                operation="close_workflow_buffer",
                workflow_id=workflow_id,
            )
            return None
        tab_label = self._workflow_tab_label(workflow_id)
        tab_index = self._workflow_tab_index(workflow_id, ordered_ids)
        try:
            snapshot = WorkflowSnapshot(
                workflow_id=workflow_id,
                tab_label=tab_label,
                workflow=workflow,
                active_cube_alias=self._active_cube_alias(workflow_id),
                input_images=self._input_image_references(workflow_id, workflow),
                input_masks=self._input_mask_references(workflow_id, workflow),
                output_images=self._output_image_references(workflow_id, workflow),
                editor_viewport=self._editor_viewport_snapshot(workflow_id),
            )
            payload = self._closed_workflow_snapshot_service.encode(snapshot)
        except (ClosedWorkflowSnapshotError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to capture closed workflow snapshot",
                operation="close_workflow_buffer",
                workflow_id=workflow_id,
                tab_label=tab_label,
                tab_index=tab_index,
                error=repr(error),
            )
            return None
        record = ClosedWorkflowRecord(
            close_id=uuid4().hex,
            workflow_id=workflow_id,
            tab_label=tab_label,
            tab_index=tab_index,
            snapshot_payload=payload,
            payload_size_bytes=len(payload),
            closed_at=datetime.now(UTC),
        )
        result = self._closed_workflow_buffer.push(record)
        log_info(
            _LOGGER,
            "Closed workflow buffer push completed",
            operation="close_workflow_buffer",
            close_id=record.close_id,
            workflow_id=workflow_id,
            tab_label=tab_label,
            tab_index=tab_index,
            payload_size_bytes=record.payload_size_bytes,
            accepted=result.accepted,
            evicted_count=len(result.evicted_records),
            buffer_total_bytes=self._closed_workflow_buffer.total_bytes,
            buffer_budget_bytes=self._closed_workflow_buffer.budget_bytes,
        )
        self._sync_reopen_closed_workflow_action()
        return result

    def _cleanup_closed_workflow_records(
        self,
        records: tuple[ClosedWorkflowRecord, ...],
    ) -> None:
        """Finalize cleanup for closed workflows that are no longer reopenable."""

        for record in records:
            try:
                snapshot = self._closed_workflow_snapshot_service.decode(
                    record.snapshot_payload
                )
            except ClosedWorkflowSnapshotError as error:
                log_warning(
                    _LOGGER,
                    "Failed to decode evicted closed workflow for cleanup",
                    operation="closed_workflow_eviction_cleanup",
                    close_id=record.close_id,
                    workflow_id=record.workflow_id,
                    tab_label=record.tab_label,
                    payload_size_bytes=record.payload_size_bytes,
                    error=repr(error),
                )
                continue
            self._prune_closed_workflow_images(
                snapshot.workflow_id,
                snapshot.workflow,
            )

    def _prune_closed_workflow_images(
        self,
        workflow_id: str,
        workflow: object,
    ) -> None:
        """Prune canvas image records for a workflow no longer reopenable."""

        view = self._view
        view.input_canvas_state_service.prune_closed_workflow_images(
            workflow,
            view.workflow_session_service.workflows,
        )
        view.output_canvas_projection_coordinator.prune_closed_workflow_images(
            workflow_id,
            workflow,
            view.workflow_session_service.workflows,
        )

    def _workflow_for_close(self, workflow_id: str) -> WorkflowState | None:
        """Return live workflow state for close-time snapshot capture."""

        session = self._view.workflow_session_service
        get_workflow = getattr(session, "get_workflow", None)
        if callable(get_workflow):
            workflow = get_workflow(workflow_id)
            return workflow if isinstance(workflow, WorkflowState) else None
        workflows = getattr(session, "workflows", {})
        if isinstance(workflows, Mapping):
            workflow = workflows.get(workflow_id)
            return workflow if isinstance(workflow, WorkflowState) else None
        return None

    def _workflow_tab_label(self, workflow_id: str) -> str:
        """Return current tab label with a stable fallback."""

        snapshot_capture = self._snapshot_capture_adapter()
        if snapshot_capture is not None:
            return snapshot_capture.workflow_tab_label(workflow_id)
        item = self._view.workflow_tabbar.itemMap.get(workflow_id)
        if item is None:
            return workflow_id
        return item.text()

    def _workflow_tab_index(self, workflow_id: str, ordered_ids: list[str]) -> int:
        """Return current workflow tab index with ordered-id fallback."""

        tabbar = self._view.workflow_tabbar
        workflow_tab_index = getattr(tabbar, "workflow_tab_index", None)
        if callable(workflow_tab_index):
            index = int(workflow_tab_index(workflow_id))
            if index >= 0:
                return index
        try:
            return ordered_ids.index(workflow_id)
        except ValueError:
            return max(0, len(ordered_ids))

    def _active_cube_alias(self, workflow_id: str) -> str | None:
        """Return active cube alias for one workflow from snapshot capture."""

        snapshot_capture = self._snapshot_capture_adapter()
        if snapshot_capture is not None:
            return snapshot_capture.active_cube_alias(workflow_id)
        return None

    def _editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return editor viewport snapshot from snapshot capture."""

        snapshot_capture = self._snapshot_capture_adapter()
        if snapshot_capture is not None:
            return snapshot_capture.editor_viewport_snapshot(workflow_id)
        return None

    def _input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return input image references from snapshot capture."""

        snapshot_capture = self._snapshot_capture_adapter()
        if snapshot_capture is not None:
            return snapshot_capture.input_image_references(workflow_id, workflow)
        return ()

    def _input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return input mask references from snapshot capture."""

        snapshot_capture = self._snapshot_capture_adapter()
        if snapshot_capture is not None:
            return snapshot_capture.input_mask_references(workflow_id, workflow)
        return ()

    def _output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return output image references from snapshot capture."""

        snapshot_capture = self._snapshot_capture_adapter()
        if snapshot_capture is not None:
            return snapshot_capture.output_image_references(workflow_id, workflow)
        return ()

    def _snapshot_capture_adapter(self) -> WorkflowSnapshotCaptureProtocol | None:
        """Return the composed snapshot capture adapter when the view provides it."""

        snapshot_capture = getattr(self._view, "session_snapshot_capture_adapter", None)
        if snapshot_capture is None:
            return None
        return cast(WorkflowSnapshotCaptureProtocol, snapshot_capture)

    def _rename_workflow_activity(
        self,
        old_workflow_id: str,
        new_workflow_id: str,
    ) -> None:
        """Re-key unread activity for a renamed workflow when supported."""

        view = self._view
        activity_service = getattr(view, "workflow_activity_service", None)
        rename_workflow = getattr(activity_service, "rename_workflow", None)
        if callable(rename_workflow):
            rename_workflow(old_workflow_id, new_workflow_id)
        has_unread = getattr(activity_service, "has_unread_result", None)
        set_unread = getattr(view.workflow_tabbar, "set_workflow_unread_result", None)
        if callable(has_unread) and callable(set_unread):
            set_unread(new_workflow_id, bool(has_unread(new_workflow_id)))

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
