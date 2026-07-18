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

"""Reconcile dirty workflow presentation surfaces after route projection."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import cast

from substitute.presentation.shell.workflow_route_ports import (
    CanvasRouteProjectionPort,
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
from substitute.presentation.shell.main_window_workflow_session_state_adapter import (
    MainWindowWorkflowSessionStateAdapter,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
    WorkflowSurfaceDirtyState,
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_ports import (
    EditorSurfacePort,
    GenerationAvailabilityPort,
    OverrideSurfacePort,
    WorkflowSessionStatePort,
    WorkflowSurfaceInvalidationPort,
)
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    surface_result,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_exception

_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


@dataclass(frozen=True, slots=True)
class WorkflowSurfaceReconcileResult:
    """Summarize one projected workflow surface reconciliation."""

    workflow_id: str
    stale: bool
    full_refresh: bool
    reconciled_surfaces: frozenset[WorkflowSurface]
    canvas_projected: bool


class ActiveWorkflowSurfaceRefresher:
    """Compatibility adapter for structural active workflow surface refreshes."""

    def __init__(self, view: object) -> None:
        """Store the shell object for compatibility-only structural refreshes."""

        self._view = view

    def refresh_active_workflow_surface(
        self,
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Refresh active workflow surfaces outside the normal tab path."""

        if getattr(self._view, "_detached_for_gui_reload", False):
            log_debug(
                _LOGGER,
                "Skipped active workflow surface refresh for detached shell",
            )
            return
        if not self._has_modern_surface_dependencies():
            legacy_refresh = getattr(
                self._view, "refresh_active_workflow_surface", None
            )
            if callable(legacy_refresh):
                self._call_legacy_refresh(
                    legacy_refresh,
                    force_refresh=force_refresh,
                    on_complete=on_complete,
                )
            return
        invalidation = self._surface_invalidation_service()
        session = MainWindowWorkflowSessionStateAdapter(self._view)
        workflow_id = session.active_workflow_id
        if not workflow_id:
            legacy_refresh = getattr(
                self._view, "refresh_active_workflow_surface", None
            )
            if callable(legacy_refresh):
                self._call_legacy_refresh(
                    legacy_refresh,
                    force_refresh=force_refresh,
                    on_complete=on_complete,
                )
            return
        workflow = session.workflows.get(workflow_id)
        stack_order = (
            getattr(workflow, "stack_order", ()) if workflow is not None else ()
        )
        cube_count = (
            len(getattr(workflow, "cubes", {}) or {}) if workflow is not None else 0
        )
        log_debug(
            _LOGGER,
            "Started active workflow surface refresh",
            workflow_id=workflow_id,
            force_refresh=force_refresh,
            cube_section_count=cube_count,
            stack_order_count=len(stack_order),
        )

        def notify_complete(_result: SurfaceRefreshResult) -> None:
            """Adapt typed completion back to the public compatibility callback."""

            if on_complete is not None:
                on_complete()

        WorkflowSurfaceReconciler(
            session,
            canvas_port=MainWindowCanvasRouteAdapter(self._view),
            editor_port=MainWindowEditorSurfaceAdapter(self._view),
            override_port=MainWindowOverrideSurfaceAdapter(self._view),
            generation_port=MainWindowGenerationAvailabilityAdapter(self._view),
            surface_invalidation_service=invalidation,
        ).reconcile_projected(
            workflow_id,
            force_refresh=force_refresh,
            dirty_state=invalidation.dirty_state(workflow_id),
            on_surface_complete=notify_complete if on_complete is not None else None,
        )

    def refresh_active_workflow_surfaces(
        self,
        surfaces: frozenset[WorkflowSurface] | set[WorkflowSurface],
    ) -> None:
        """Reconcile selected active workflow surfaces through typed ports."""

        if not self._has_modern_surface_dependencies():
            legacy_refresh = getattr(
                self._view, "refresh_active_workflow_surfaces", None
            )
            if callable(legacy_refresh):
                legacy_refresh(surfaces)
            return
        invalidation = self._surface_invalidation_service()
        session = MainWindowWorkflowSessionStateAdapter(self._view)
        workflow_id = session.active_workflow_id
        dirty_state = WorkflowSurfaceDirtyState(
            workflow_id=workflow_id,
            dirty_surfaces=frozenset(surfaces),
            reasons=(),
        )
        WorkflowSurfaceReconciler(
            session,
            canvas_port=MainWindowCanvasRouteAdapter(self._view),
            editor_port=MainWindowEditorSurfaceAdapter(self._view),
            override_port=MainWindowOverrideSurfaceAdapter(self._view),
            generation_port=MainWindowGenerationAvailabilityAdapter(self._view),
            surface_invalidation_service=invalidation,
        ).reconcile_projected(
            workflow_id,
            force_refresh=False,
            dirty_state=dirty_state,
            on_surface_complete=None,
        )

    def sync_active_override_state(
        self,
        active_manager: object,
        *,
        workflow_id: str,
    ) -> None:
        """Synchronize persisted override state into the active toolbar manager."""

        del workflow_id
        method = getattr(active_manager, "sync_state_from_workflow", None)
        if callable(method):
            method()

    def apply_active_overrides_before_projection(
        self,
        active_manager: object,
        *,
        workflow_id: str,
    ) -> bool:
        """Apply persisted overrides before projecting editor cards."""

        del workflow_id
        pre_projection_apply = getattr(
            active_manager,
            "apply_global_overrides_without_snapshot_fallback",
            None,
        )
        if callable(pre_projection_apply):
            return bool(pre_projection_apply())
        apply_global_overrides = getattr(active_manager, "apply_global_overrides", None)
        if callable(apply_global_overrides):
            apply_global_overrides(use_cached_behavior_snapshot=False)
        return False

    def materialize_active_default_overrides(
        self,
        active_manager: object,
        *,
        workflow_id: str,
    ) -> bool:
        """Materialize default pinned override controls after projection exists."""

        del workflow_id
        materialize_default_overrides = getattr(
            active_manager,
            "materialize_default_overrides",
            None,
        )
        return (
            bool(materialize_default_overrides())
            if callable(materialize_default_overrides)
            else False
        )

    def apply_active_overrides_after_projection(
        self,
        active_manager: object,
        *,
        workflow_id: str,
        materialized_defaults: bool,
    ) -> None:
        """Apply active override values against projected workflow buffers."""

        del workflow_id
        apply_global_overrides = getattr(active_manager, "apply_global_overrides", None)
        if callable(apply_global_overrides):
            apply_global_overrides(
                use_cached_behavior_snapshot=not materialized_defaults
            )

    def schedule_active_override_presentation_rebuild(
        self,
        active_manager: object,
        *,
        workflow_id: str,
    ) -> None:
        """Schedule override toolbar presentation rebuild for the active workflow."""

        token = ReconciliationToken(workflow_id=workflow_id, generation=0)

        class _SingleManagerOverridePort(MainWindowOverrideSurfaceAdapter):
            """Use one provided manager for compatibility method calls."""

            def _manager(self, requested_workflow_id: str) -> object | None:
                """Return the provided active manager for the matching workflow."""

                if requested_workflow_id != workflow_id:
                    return None
                return active_manager

        _SingleManagerOverridePort(self._view).schedule_override_presentation_rebuild(
            workflow_id, token
        )

    def refresh_active_input_canvas_availability(self, workflow_id: str) -> None:
        """Refresh input-canvas availability for the active workflow."""

        MainWindowGenerationAvailabilityAdapter(self._view).refresh_input_availability(
            workflow_id
        )

    def refresh_active_generation_availability(self, workflow_id: str) -> None:
        """Refresh titlebar generation availability for the active workflow."""

        MainWindowGenerationAvailabilityAdapter(
            self._view
        ).refresh_generation_availability(workflow_id)

    def _has_modern_surface_dependencies(self) -> bool:
        """Return whether the shell exposes enough state for typed adapters."""

        return bool(
            hasattr(self._view, "workflow_session_service")
            and (
                hasattr(self._view, "active_editor_panel")
                or hasattr(self._view, "editor_panels")
            )
            and (
                hasattr(self._view, "active_override_manager")
                or hasattr(self._view, "override_managers")
            )
        )

    def _surface_invalidation_service(self) -> WorkflowSurfaceInvalidationPort:
        """Return shell invalidation state or a compatibility local instance."""

        return cast(
            WorkflowSurfaceInvalidationPort,
            getattr(
                self._view,
                "workflow_surface_invalidation_service",
                WorkflowSurfaceInvalidationService(),
            ),
        )

    @staticmethod
    def _call_legacy_refresh(
        legacy_refresh: Callable[..., object],
        *,
        force_refresh: bool,
        on_complete: Callable[[], None] | None,
    ) -> None:
        """Call legacy refresh hooks that may not accept modern keyword options."""

        parameters: Mapping[str, Parameter]
        try:
            parameters = signature(legacy_refresh).parameters
        except (TypeError, ValueError):
            parameters = {}
        supports_variadic_keywords = any(
            parameter.kind is Parameter.VAR_KEYWORD for parameter in parameters.values()
        )
        supports_force_refresh = (
            "force_refresh" in parameters or supports_variadic_keywords
        )
        supports_on_complete = "on_complete" in parameters or supports_variadic_keywords
        kwargs: dict[str, object] = {}
        if supports_force_refresh:
            kwargs["force_refresh"] = force_refresh
        if supports_on_complete:
            kwargs["on_complete"] = on_complete
        legacy_refresh(**kwargs)
        if on_complete is not None and not supports_on_complete:
            on_complete()


def active_workflow_surface_refresher_for(
    view: object,
) -> ActiveWorkflowSurfaceRefresher:
    """Return the composed active workflow surface refresher for a shell."""

    refresher = getattr(view, "active_workflow_surface_refresher", None)
    if isinstance(refresher, ActiveWorkflowSurfaceRefresher):
        return refresher
    refresher = ActiveWorkflowSurfaceRefresher(view)
    setattr(view, "active_workflow_surface_refresher", refresher)
    return refresher


class WorkflowSurfaceReconciler:
    """Own workflow surface maintenance after immediate route projection."""

    _SHELL_SURFACES = frozenset(
        {
            WorkflowSurface.EDITOR,
            WorkflowSurface.OVERRIDES,
            WorkflowSurface.GENERATION_AVAILABILITY,
        }
    )

    def __init__(
        self,
        session_port: WorkflowSessionStatePort,
        *,
        canvas_port: CanvasRouteProjectionPort,
        editor_port: EditorSurfacePort,
        override_port: OverrideSurfacePort,
        generation_port: GenerationAvailabilityPort,
        surface_invalidation_service: WorkflowSurfaceInvalidationPort,
    ) -> None:
        """Store typed dependencies for surface maintenance."""

        self._session_port = session_port
        self._canvas_port = canvas_port
        self._editor_port = editor_port
        self._override_port = override_port
        self._generation_port = generation_port
        self._surface_invalidation_service = surface_invalidation_service
        self._reconciliation_generation = 0

    def reconcile_projected(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        dirty_state: WorkflowSurfaceDirtyState,
        on_surface_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> WorkflowSurfaceReconcileResult:
        """Reconcile the active projected workflow when it is still current."""

        if workflow_id != self._session_port.active_workflow_id:
            log_debug(
                _LOGGER,
                "workflow surface reconciler skipped stale workflow",
                workflow_id=workflow_id,
                active_workflow_id=self._session_port.active_workflow_id,
                force_refresh=force_refresh,
            )
            return WorkflowSurfaceReconcileResult(
                workflow_id=workflow_id,
                stale=True,
                full_refresh=False,
                reconciled_surfaces=frozenset(),
                canvas_projected=False,
            )
        if (
            dirty_state.dirty_surfaces
            and not force_refresh
            and on_surface_complete is None
        ):
            return self._reconcile_dirty_projected(workflow_id, dirty_state)
        return self._reconcile_full_projected(
            workflow_id,
            force_refresh=force_refresh,
            on_surface_complete=on_surface_complete,
        )

    def _reconcile_full_projected(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        on_surface_complete: Callable[[SurfaceRefreshResult], None] | None,
    ) -> WorkflowSurfaceReconcileResult:
        """Run a full active workflow surface refresh and canvas projection."""

        self._reconciliation_generation += 1
        token = ReconciliationToken(
            workflow_id=workflow_id,
            generation=self._reconciliation_generation,
        )
        cleanable_surfaces: set[WorkflowSurface] = set()

        def finish_after_editor(editor_result: SurfaceRefreshResult) -> None:
            """Finish dependent shell surfaces after editor projection settles."""

            if editor_result.cleanable:
                cleanable_surfaces.add(WorkflowSurface.EDITOR)
                self._mark_cleanable(editor_result)
            for result in self._finalize_override_and_availability(
                workflow_id,
                token=token,
            ):
                if result.cleanable:
                    cleanable_surfaces.add(result.surface)
                    self._mark_cleanable(result)
            if on_surface_complete is not None:
                on_surface_complete(editor_result)
            log_debug(
                _LOGGER,
                "Completed active workflow surface refresh",
                workflow_id=workflow_id,
            )

        self._consume_result(self._override_port.sync_override_state(workflow_id))
        self._consume_result(
            self._override_port.apply_overrides_before_projection(workflow_id)
        )
        editor_result = self._editor_port.refresh_editor_surface(
            workflow_id,
            force=force_refresh,
            on_complete=finish_after_editor,
        )
        if editor_result.status in {
            SurfaceRefreshStatus.FAILED,
            SurfaceRefreshStatus.SKIPPED_MISSING,
            SurfaceRefreshStatus.SKIPPED_STALE,
        }:
            self._consume_result(editor_result)
        canvas_result = self._canvas_port.project_workflow_canvas(workflow_id)
        canvas_projected = canvas_result.status is SurfaceRefreshStatus.SUCCESS
        if canvas_result.cleanable:
            cleanable_surfaces.add(WorkflowSurface.CANVAS)
            self._mark_cleanable(canvas_result)
        self._generation_port.refresh_input_availability(workflow_id)
        log_debug(
            _LOGGER,
            "workflow surface reconciler full refresh completed",
            workflow_id=workflow_id,
            force_refresh=force_refresh,
            canvas_projected=canvas_projected,
            cleanable_surfaces=tuple(surface.value for surface in cleanable_surfaces),
        )
        return WorkflowSurfaceReconcileResult(
            workflow_id=workflow_id,
            stale=False,
            full_refresh=True,
            reconciled_surfaces=frozenset(cleanable_surfaces),
            canvas_projected=canvas_projected,
        )

    def _reconcile_dirty_projected(
        self,
        workflow_id: str,
        dirty_state: WorkflowSurfaceDirtyState,
    ) -> WorkflowSurfaceReconcileResult:
        """Reconcile only the surfaces marked dirty for the active workflow."""

        self._reconciliation_generation += 1
        token = ReconciliationToken(
            workflow_id=workflow_id,
            generation=self._reconciliation_generation,
        )
        dirty_surfaces = dirty_state.dirty_surfaces
        reconciled_surfaces: set[WorkflowSurface] = set()
        canvas_projected = False
        if WorkflowSurface.EDITOR in dirty_surfaces:
            result = self._editor_port.refresh_editor_surface(
                workflow_id,
                force=False,
                on_complete=self._mark_completion_result,
            )
            if result.cleanable:
                self._mark_cleanable(result)
                reconciled_surfaces.add(result.surface)
        if WorkflowSurface.OVERRIDES in dirty_surfaces:
            for result in self._finalize_override_and_availability(
                workflow_id,
                token=token,
                include_generation=False,
            ):
                if result.cleanable:
                    self._mark_cleanable(result)
                    reconciled_surfaces.add(result.surface)
        if WorkflowSurface.GENERATION_AVAILABILITY in dirty_surfaces:
            for result in (
                self._generation_port.refresh_input_availability(workflow_id),
                self._generation_port.refresh_generation_availability(workflow_id),
            ):
                if result.cleanable:
                    self._mark_cleanable(result)
                    reconciled_surfaces.add(result.surface)
        if WorkflowSurface.CANVAS in dirty_surfaces:
            canvas_result = self._canvas_port.project_workflow_canvas(workflow_id)
            canvas_projected = canvas_result.status is SurfaceRefreshStatus.SUCCESS
            if canvas_result.cleanable:
                self._mark_cleanable(canvas_result)
                reconciled_surfaces.add(canvas_result.surface)
        log_debug(
            _LOGGER,
            "workflow surface reconciler dirty refresh completed",
            workflow_id=workflow_id,
            dirty_surfaces=tuple(surface.value for surface in dirty_surfaces),
            dirty_reasons=tuple(reason.value for reason in dirty_state.reasons),
            reconciled_surfaces=tuple(
                surface.value for surface in sorted(reconciled_surfaces)
            ),
            canvas_projected=canvas_projected,
        )
        return WorkflowSurfaceReconcileResult(
            workflow_id=workflow_id,
            stale=False,
            full_refresh=False,
            reconciled_surfaces=frozenset(reconciled_surfaces),
            canvas_projected=canvas_projected,
        )

    def _finalize_override_and_availability(
        self,
        workflow_id: str,
        *,
        token: ReconciliationToken,
        include_generation: bool = True,
    ) -> tuple[SurfaceRefreshResult, ...]:
        """Run post-editor override and availability refresh operations."""

        results: list[SurfaceRefreshResult] = []
        materialize_result = self._override_port.materialize_default_overrides(
            workflow_id
        )
        if not materialize_result.cleanable:
            results.append(materialize_result)
        materialized_defaults = self._override_materialized_defaults(workflow_id)
        apply_result = self._override_port.apply_overrides_after_projection(
            workflow_id,
            materialized_defaults=materialized_defaults,
        )
        if not apply_result.cleanable:
            results.append(apply_result)
        schedule_result = self._override_port.schedule_override_presentation_rebuild(
            workflow_id,
            token,
            on_complete=self._mark_completion_result,
        )
        if schedule_result.cleanable:
            results.append(schedule_result)
        elif schedule_result.status is not SurfaceRefreshStatus.SUCCESS:
            results.append(schedule_result)
        if include_generation:
            results.extend(
                [
                    self._generation_port.refresh_generation_availability(workflow_id),
                ]
            )
        return tuple(results)

    def _override_materialized_defaults(self, workflow_id: str) -> bool:
        """Return adapter-reported default materialization state when available."""

        materialized_defaults = getattr(
            self._override_port,
            "last_materialized_defaults",
            None,
        )
        if callable(materialized_defaults):
            return bool(materialized_defaults(workflow_id))
        return False

    def _mark_completion_result(self, result: SurfaceRefreshResult) -> None:
        """Mark a deferred completion clean only when the result is cleanable."""

        if result.cleanable:
            self._mark_cleanable(result)
            return
        self._consume_result(result)

    def _mark_cleanable(self, result: SurfaceRefreshResult) -> None:
        """Mark exactly one surface clean from a cleanable result."""

        if not result.cleanable:
            self._consume_result(result)
            return
        self._surface_invalidation_service.mark_clean(
            result.workflow_id,
            {result.surface},
        )

    def _consume_result(self, result: SurfaceRefreshResult) -> None:
        """Log failed or non-cleanable surface results with context."""

        if result.status is SurfaceRefreshStatus.FAILED:
            log_exception(
                _LOGGER,
                "Workflow surface reconciliation failed",
                workflow_id=result.workflow_id,
                surface=result.surface.value,
                operation=result.operation,
                error=RuntimeError(result.error),
            )


def skipped_surface_result(
    workflow_id: str,
    surface: WorkflowSurface,
    *,
    operation: str,
) -> SurfaceRefreshResult:
    """Return a non-cleanable missing-surface result for tests and adapters."""

    return surface_result(
        workflow_id=workflow_id,
        surface=surface,
        status=SurfaceRefreshStatus.SKIPPED_MISSING,
        operation=operation,
        elapsed_ms=0.0,
        cleanable=False,
    )


__all__ = [
    "ActiveWorkflowSurfaceRefresher",
    "WorkflowSurfaceReconcileResult",
    "WorkflowSurfaceReconciler",
    "active_workflow_surface_refresher_for",
    "skipped_surface_result",
]
