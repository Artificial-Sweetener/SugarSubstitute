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

"""Handle workspace cube-picker and cube-tab orchestration in the shell layer."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from inspect import Parameter, signature
from time import perf_counter
from typing import Any, Protocol, cast
from uuid import uuid4

from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.cubes import (
    CubePickerClassification,
    CubeStackDraft,
    CubeStackDraftEntry,
    CubeStackDraftResult,
    cube_stack_draft_entry_from_record,
    cube_stack_draft_from_workflow,
    cube_stack_draft_result,
    plan_cube_stack_aliases,
)
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.application.workflows import (
    NodeLinkEndpointIndex,
    PromptEndpointIndex,
    WorkflowLinkReconciliationService,
)
from substitute.application.ports import (
    CubeCatalogRecord,
    CubeCatalogSnapshot,
)
from substitute.application.errors import SubstituteOperationContext
from substitute.presentation.errors import ErrorPresenter, ErrorReportPresenterProtocol
from substitute.presentation.shell.cube_loader import (
    CubeIconFactoryProtocol,
    CubeLoadPresentationIntent,
    load_cube_async,
)
from substitute.presentation.shell.cube_removal_projection import (
    clear_cube_runtime_issues,
    remove_editor_cube_section,
)
from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyControllerProtocol,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    CUBE_STRUCTURE_SURFACES,
    WorkflowInvalidationReason,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.workspace_cube_picker_actions")


def _mark_workflow_surfaces_dirty(
    view: object,
    workflow_id: str,
    *,
    reason: WorkflowInvalidationReason,
) -> None:
    """Record cube-structure maintenance intent when the shell exposes tracking."""

    service = getattr(view, "workflow_surface_invalidation_service", None)
    mark_dirty = getattr(service, "mark_dirty", None)
    if callable(mark_dirty):
        mark_dirty(workflow_id, CUBE_STRUCTURE_SURFACES, reason)


@dataclass(frozen=True)
class CatalogRefreshRoute:
    """Carry one catalog refresh submitter and cleanup callback."""

    submitter: TaskSubmitter
    close: Callable[[], None]


CatalogRefreshRouteFactory = Callable[[str], CatalogRefreshRoute]


def _run_catalog_refresh_task(
    *,
    cube_load_service: object,
    cube_load_trace_id: str,
) -> CubeCatalogSnapshot | BaseException:
    """Refresh picker catalog data as execution task work."""

    started_at = perf_counter()
    try:
        refresh = getattr(cube_load_service, "refresh_picker_catalog")
        result: CubeCatalogSnapshot | BaseException = cast(
            CubeCatalogSnapshot,
            refresh(),
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        result = exc
    log_timing(
        _LOGGER,
        "Completed cube picker catalog background refresh",
        started_at=started_at,
        cube_load_trace_id=cube_load_trace_id,
        succeeded=not isinstance(result, BaseException),
        level="debug",
    )
    return result


def _catalog_refresh_result_from_outcome(
    outcome: TaskOutcome[CubeCatalogSnapshot | BaseException],
) -> CubeCatalogSnapshot | BaseException:
    """Return the catalog refresh payload represented by one task outcome."""

    if outcome.result is not None:
        return outcome.result
    if outcome.error is not None:
        return outcome.error
    if outcome.cancelled:
        return RuntimeError(outcome.cancellation_reason or "cancelled")
    return RuntimeError("Cube picker catalog refresh produced no outcome.")


class CubeStackTabItemProtocol(Protocol):
    """Describe cube-tab item operations used by cube actions."""

    def routeKey(self) -> str:
        """Return the cube route key."""

    def setRouteKey(self, key: str) -> None:
        """Replace the cube route key."""

    def setText(self, text: str) -> None:
        """Replace the rendered cube label."""

    def setToolTip(self, text: str) -> None:
        """Replace the rendered cube tooltip."""


class CubeStackProtocol(Protocol):
    """Describe cube-stack behavior used by cube actions."""

    items: list[object]
    itemMap: dict[str, CubeStackTabItemProtocol]

    def count(self) -> int:
        """Return number of cube tabs."""

    def tabItem(self, index: int) -> CubeStackTabItemProtocol:
        """Return cube tab at index."""

    def setCurrentIndex(self, index: int) -> None:
        """Select current cube tab."""

    def insertTab(self, index: int, **kwargs: object) -> object:
        """Insert cube tab and return created item."""

    def removeTab(self, index: int) -> None:
        """Remove cube tab at index."""

    def reorder_by_route_keys(self, route_keys: list[str]) -> None:
        """Reorder tabs to match route keys."""

    def begin_alias_editing(self, route_key: str) -> bool:
        """Begin alias editing for one route key when the stack can show it."""

    def isCompact(self) -> bool:
        """Return whether the stack is compact."""

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Set bypass presentation state for one tab."""


class EditorPanelProtocol(Protocol):
    """Describe editor-panel behavior used by cube actions."""

    def scroll_to_cube(self, route_key: str, animated: bool = False) -> None:
        """Scroll to one cube section."""

    def rename_cube(self, old_key: str, new_key: str) -> None:
        """Rename one cube section."""

    def refresh_cube_header(self, alias: str) -> None:
        """Refresh one cube section header from current cube state."""


class CubeLoadServiceProtocol(Protocol):
    """Describe cube-load service behavior used by cube actions."""

    def list_available_cubes(self) -> list[CubeCatalogRecord]:
        """Return selectable cube catalog entries."""

    def picker_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Return the immediate picker catalog snapshot."""

    def refresh_picker_catalog(self) -> CubeCatalogSnapshot:
        """Force-refresh picker catalog data."""

    def classify_picker_cubes(
        self,
        entries: list[CubeCatalogRecord],
    ) -> dict[str, CubePickerClassification]:
        """Classify listed cubes from loaded cube documents."""


class CubeRenameResolutionProtocol(Protocol):
    """Describe resolved alias information returned from a cube rename request."""

    resolved_alias: str


class CubeStackServiceProtocol(Protocol):
    """Describe cube-stack service behavior used by cube actions."""

    def resolve_unique_alias(
        self,
        workflow: object,
        requested_alias: str,
        *,
        exclude_alias: str | None = None,
    ) -> str:
        """Resolve one unique alias for a workflow."""

    def apply_reordered_aliases(self, workflow: object, new_order: list[str]) -> None:
        """Synchronize reordered aliases into workflow state."""

    def apply_cube_removal(self, workflow: object, alias_name: str) -> None:
        """Remove one cube alias from service and workflow state together."""

    def apply_cube_rename(
        self,
        workflow: object,
        old_alias: str,
        requested_alias: str,
    ) -> CubeRenameResolutionProtocol:
        """Rename one cube alias in service and workflow state together."""

    def toggle_cube_bypassed(self, workflow: object, alias_name: str) -> bool:
        """Toggle cube bypass state and return the new bypass value."""


class NodeBehaviorServiceProtocol(Protocol):
    """Describe runtime node-behavior behavior used by cube actions."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeProtocol,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Build runtime node-behavior state for one loaded cube."""

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return prompt endpoints for workflow link reconciliation."""

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return whole-node endpoints for workflow link reconciliation."""


class CubePickerProtocol(Protocol):
    """Describe cube staging picker behavior used by cube actions."""

    def edit_stack(
        self,
        *,
        parent: object,
        records: list[CubeCatalogRecord],
        initial_draft: CubeStackDraft,
        icon_factory: CubeIconFactoryProtocol,
        stack_anchor: object | None = None,
        refresh_catalog: Callable[[], CubeCatalogSnapshot] | None = None,
        classifications: Mapping[str, CubePickerClassification] | None = None,
        classify_records: Callable[
            [list[CubeCatalogRecord]], Mapping[str, CubePickerClassification]
        ]
        | None = None,
    ) -> CubeStackDraftResult | None:
        """Return the accepted stack draft or ``None`` when cancelled."""


class IconTokenProtocol(Protocol):
    """Describe icon token behavior used for placeholder cube tabs."""

    def icon(self) -> object:
        """Return concrete icon payload."""


class CubeIconProviderProtocol(Protocol):
    """Describe the icon subset used by cube actions."""

    CLOSE: IconTokenProtocol


class CubeLoaderProtocol(Protocol):
    """Describe async cube-loader entrypoint used by cube picker flow."""

    def __call__(
        self,
        callbacks: object,
        cube_id: str,
        alias_name: str,
        placeholder_index: int,
        *,
        presentation_intent: CubeLoadPresentationIntent | None = None,
        reveal_after_load: bool = True,
        on_load_finished: Callable[[str | None], None] | None = None,
        cube_load_trace_id: str | None = None,
    ) -> None:
        """Queue one cube for async load."""


class LoadedCubeProtocol(Protocol):
    """Describe loaded cube payload used for runtime preparation."""

    cube_id: str
    version: str
    display_name: str
    graph: dict[str, object]
    ui_payload: dict[str, object] | None


class WorkflowStateProtocol(Protocol):
    """Describe workflow cube state consumed by cube actions."""

    cubes: dict[str, object]
    stack_order: list[str]


class ActiveWorkflowSurfaceRefresherProtocol(Protocol):
    """Describe structural active workflow surface reconciliation."""

    def refresh_active_workflow_surface(
        self,
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Refresh active workflow surfaces after cube mutations."""


class AliasPlanProtocol(Protocol):
    """Describe alias-plan lookup used for diagnostics."""

    def alias_for(self, draft_id: str) -> str:
        """Return the planned alias for one draft id."""


class WorkspaceCubePickerActionView(Protocol):
    """Describe the shell surface consumed by workspace cube actions."""

    cube_load_service: CubeLoadServiceProtocol
    cube_icon_factory: CubeIconFactoryProtocol
    cube_stack_service: CubeStackServiceProtocol
    workflow_session_service: object
    node_behavior_service: NodeBehaviorServiceProtocol
    cube_stacks: dict[str, CubeStackProtocol]
    editor_panels: dict[str, object]
    active_cube_stack: CubeStackProtocol | None
    active_editor_panel: EditorPanelProtocol | None
    active_workflow_surface_refresher: ActiveWorkflowSurfaceRefresherProtocol
    editor_busy: EditorBusyControllerProtocol
    _pending_cubes: dict[str, int]

    def get_active_workflow(self) -> WorkflowStateProtocol:
        """Return the active workflow state."""


class WorkspaceCubePickerActions:
    """Own cube-picker, runtime-preparation, and cube-tab shell behavior."""

    def __init__(
        self,
        view: WorkspaceCubePickerActionView,
        *,
        build_cube_load_ui_callbacks: Callable[..., object],
        error_presenter: ErrorReportPresenterProtocol | None = None,
        catalog_refresh_route_factory: CatalogRefreshRouteFactory | None = None,
    ) -> None:
        """Store the shell view dependency and cube-loader callback builder."""

        self._view = view
        self._build_cube_load_ui_callbacks = build_cube_load_ui_callbacks
        self._error_presenter = error_presenter
        self._catalog_refresh_route_factory = catalog_refresh_route_factory
        self._catalog_refresh_running = False
        self._catalog_refresh_request_id = 0
        self._catalog_refresh_close: Callable[[], None] | None = None
        self._catalog_refresh_scope: TaskScope | None = None

    def shutdown(self) -> None:
        """Cancel active action-owned refresh work and release route resources."""

        self._catalog_refresh_running = False
        if self._catalog_refresh_scope is not None:
            self._catalog_refresh_scope.close(
                reason="workspace_cube_picker_actions_shutdown"
            )
            self._catalog_refresh_scope = None
        if self._catalog_refresh_close is not None:
            self._catalog_refresh_close()
            self._catalog_refresh_close = None

    def prepare_node_behavior_runtime(
        self,
        loaded_cube: LoadedCubeProtocol,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Build runtime node-behavior state for one freshly loaded cube."""

        view = self._view
        return view.node_behavior_service.prepare_runtime_state(
            loaded_cube,
            alias_name,
        )

    def show_cube_picker(
        self,
        *,
        cube_picker: CubePickerProtocol | None = None,
        icon_provider: CubeIconProviderProtocol = FIF,
        cube_loader: CubeLoaderProtocol = cast(CubeLoaderProtocol, load_cube_async),
    ) -> None:
        """Show the cube picker and queue the selected cube for async load."""

        picker_started_at = perf_counter()
        cube_load_trace_id = uuid4().hex
        view = self._view
        active_stack = view.active_cube_stack
        if active_stack is None:
            return

        workflow = view.get_active_workflow()
        workflow_session_service = getattr(view, "workflow_session_service", None)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cart_open",
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=str(
                getattr(workflow_session_service, "active_workflow_id", "")
            ),
            workflow_cube_count=len(getattr(workflow, "cubes", {}) or {}),
            workflow_stack_order=list(getattr(workflow, "stack_order", []) or []),
            active_stack_count=active_stack.count(),
            pending_cubes=dict(getattr(view, "_pending_cubes", {}) or {}),
        )
        log_info(
            _LOGGER,
            "Started cube picker screen open",
            cube_load_trace_id=cube_load_trace_id,
            workflow_cube_count=len(getattr(workflow, "cubes", {})),
            workflow_stack_count=len(getattr(workflow, "stack_order", ())),
            active_stack_present=active_stack is not None,
        )
        try:
            phase_started_at = perf_counter()
            snapshot = self._picker_catalog_snapshot()
            cube_catalog = snapshot.entries
            log_timing(
                _LOGGER,
                "Read immediate cube picker catalog snapshot for screen open",
                started_at=phase_started_at,
                cube_load_trace_id=cube_load_trace_id,
                cube_count=len(cube_catalog),
                catalog_state=snapshot.state,
                catalog_revision=snapshot.catalog_revision,
                has_error=snapshot.error is not None,
                level="debug",
            )
            if not cube_catalog and snapshot.state in {"missing", "loading"}:
                phase_started_at = perf_counter()
                snapshot = self._refresh_picker_catalog_sync(cube_load_trace_id)
                cube_catalog = snapshot.entries
                log_timing(
                    _LOGGER,
                    "Completed cold cube picker catalog refresh for screen open",
                    started_at=phase_started_at,
                    cube_load_trace_id=cube_load_trace_id,
                    cube_count=len(cube_catalog),
                    catalog_state=snapshot.state,
                    catalog_revision=snapshot.catalog_revision,
                    has_error=snapshot.error is not None,
                    level="debug",
                )
            elif snapshot.state in {"stale", "error"}:
                self._schedule_catalog_refresh(cube_load_trace_id)
            if not cube_catalog and snapshot.state in {"missing", "loading", "error"}:
                catalog_error = RuntimeError(
                    snapshot.error
                    or (
                        "Cube catalog is unavailable because the Substitute "
                        "BackEnd has not published a cube library snapshot yet."
                    )
                )
                log_warning(
                    _LOGGER,
                    "Cube picker catalog unavailable for screen open",
                    cube_load_trace_id=cube_load_trace_id,
                    catalog_state=snapshot.state,
                    catalog_revision=snapshot.catalog_revision,
                    has_error=snapshot.error is not None,
                )
                self._show_exception_report(
                    catalog_error,
                    title="Cube picker failed",
                    message=(
                        "Cube Library is not available yet. "
                        "Wait for Substitute BackEnd to finish starting, then try again."
                    ),
                    stage="cube_picker",
                    context=SubstituteOperationContext(
                        operation="list_cubes_for_picker",
                        workflow_id=getattr(
                            workflow_session_service, "active_workflow_id", None
                        ),
                        trace_id=cube_load_trace_id,
                        values={
                            "catalog_state": snapshot.state,
                            "catalog_revision": snapshot.catalog_revision,
                        },
                    ),
                )
                return
            log_timing(
                _LOGGER,
                "Listed cubes for picker",
                started_at=phase_started_at,
                cube_load_trace_id=cube_load_trace_id,
                cube_count=len(cube_catalog),
                catalog_state=snapshot.state,
                level="debug",
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            log_exception(
                _LOGGER,
                "Failed to list cubes for picker",
                cube_load_trace_id=cube_load_trace_id,
                error=exc,
            )
            self._show_exception_report(
                exc,
                title="Cube picker failed",
                message=(
                    "Failed to list available cubes. "
                    "Please verify your cube packages and try again."
                ),
                stage="cube_picker",
                context=SubstituteOperationContext(
                    operation="list_cubes_for_picker",
                    workflow_id=getattr(
                        view.workflow_session_service,
                        "active_workflow_id",
                        None,
                    ),
                    trace_id=cube_load_trace_id,
                ),
            )
            return

        phase_started_at = perf_counter()
        if cube_picker is None:
            from substitute.presentation.cube_picker import CubePickerDialog

            picker: CubePickerProtocol = CubePickerDialog()
        else:
            picker = cube_picker
        log_timing(
            _LOGGER,
            "Resolved cube picker screen object",
            started_at=phase_started_at,
            cube_load_trace_id=cube_load_trace_id,
            picker_type=type(picker).__name__,
            default_picker=cube_picker is None,
            level="debug",
        )
        phase_started_at = perf_counter()
        classifications = self._classify_picker_records(
            cube_catalog,
            cube_load_trace_id,
        )
        log_timing(
            _LOGGER,
            "Prepared cube picker classifications for screen open",
            started_at=phase_started_at,
            cube_load_trace_id=cube_load_trace_id,
            cube_count=len(cube_catalog),
            classification_count=len(classifications),
            level="debug",
        )
        phase_started_at = perf_counter()
        initial_draft = cube_stack_draft_from_workflow(workflow)
        log_timing(
            _LOGGER,
            "Built initial cube cart draft from workflow",
            started_at=phase_started_at,
            cube_load_trace_id=cube_load_trace_id,
            initial_entry_count=len(initial_draft.entries),
            level="debug",
        )
        phase_started_at = perf_counter()
        draft_result = _edit_picker_stack(
            picker,
            parent=view,
            records=cube_catalog,
            initial_draft=initial_draft,
            stack_anchor=active_stack,
            icon_factory=view.cube_icon_factory,
            refresh_catalog=lambda: self._refresh_picker_catalog_sync(
                cube_load_trace_id
            ),
            classifications=classifications,
            classify_records=lambda entries: self._classify_picker_records(
                entries,
                cube_load_trace_id,
            ),
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cart_edit_returned",
            cube_load_trace_id=cube_load_trace_id,
            initial_entries=_draft_entries_debug_payload(initial_draft.entries),
            result_entries=_draft_entries_debug_payload(draft_result.entries)
            if draft_result is not None
            else (),
            result_present=draft_result is not None,
            has_changes=(
                draft_result.has_changes_from(initial_draft)
                if draft_result is not None
                else False
            ),
        )
        log_timing(
            _LOGGER,
            "Cube picker screen edit returned",
            started_at=phase_started_at,
            cube_load_trace_id=cube_load_trace_id,
            picker_type=type(picker).__name__,
            cube_count=len(cube_catalog),
            draft_result_present=draft_result is not None,
            draft_entry_count=(
                len(draft_result.entries) if draft_result is not None else 0
            ),
            level="debug",
        )
        if draft_result is None or not draft_result.has_changes_from(initial_draft):
            log_timing(
                _LOGGER,
                "Completed cube picker stack edit without changes",
                started_at=picker_started_at,
                cube_load_trace_id=cube_load_trace_id,
                cube_count=len(cube_catalog),
                level="debug",
            )
            return

        self._apply_cube_stack_draft(
            draft_result=draft_result,
            initial_draft=initial_draft,
            workflow=workflow,
            active_stack=active_stack,
            icon_provider=icon_provider,
            cube_loader=cube_loader,
            cube_load_trace_id=cube_load_trace_id,
            picker_started_at=picker_started_at,
        )
        log_timing(
            _LOGGER,
            "Completed cube picker stack edit with draft apply",
            started_at=picker_started_at,
            cube_load_trace_id=cube_load_trace_id,
            cube_count=len(cube_catalog),
            draft_entry_count=len(draft_result.entries),
            level="debug",
        )

    def _apply_cube_stack_draft(
        self,
        *,
        draft_result: CubeStackDraftResult,
        initial_draft: CubeStackDraft,
        workflow: object,
        active_stack: CubeStackProtocol,
        icon_provider: CubeIconProviderProtocol,
        cube_loader: CubeLoaderProtocol,
        cube_load_trace_id: str,
        picker_started_at: float,
    ) -> None:
        """Reconcile an accepted draft stack with the real workflow stack."""

        final_entries = list(draft_result.entries)
        new_entries = [entry for entry in final_entries if entry.source == "new"]
        initial_existing_aliases = [
            entry.existing_alias
            for entry in initial_draft.entries
            if entry.source == "existing" and entry.existing_alias is not None
        ]
        final_existing_aliases = [
            entry.existing_alias
            for entry in final_entries
            if entry.source == "existing" and entry.existing_alias is not None
        ]
        removed_aliases = [
            alias
            for alias in initial_existing_aliases
            if alias not in final_existing_aliases
        ]
        view = self._view
        workflow_state = cast(WorkflowStateProtocol, workflow)
        workflow_id = str(
            getattr(view.workflow_session_service, "active_workflow_id", "")
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cart_commit_start",
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=workflow_id,
            initial_entries=_draft_entries_debug_payload(initial_draft.entries),
            final_entries=_draft_entries_debug_payload(final_entries),
            workflow_stack_order_before=list(workflow_state.stack_order),
            workflow_cube_aliases_before=list(workflow_state.cubes),
        )
        log_info(
            _LOGGER,
            "Started cube stack draft commit",
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=workflow_id,
            initial_entry_count=len(initial_draft.entries),
            final_entry_count=len(final_entries),
            removed_existing_count=len(removed_aliases),
            kept_existing_count=len(final_existing_aliases),
            new_entry_count=len(new_entries),
        )
        busy_token = view.editor_busy.begin(workflow_id, message="Loading")

        for alias in removed_aliases:
            view.cube_stack_service.apply_cube_removal(workflow, alias)
            clear_cube_runtime_issues(view, workflow_id, alias)
            remove_editor_cube_section(view, alias)
            _remove_stack_tab_by_route_key(active_stack, alias)

        if removed_aliases:
            log_info(
                _LOGGER,
                "Applied cube stack draft removals",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
                removed_aliases=removed_aliases,
            )

        _apply_reordered_aliases(
            view.cube_stack_service,
            workflow,
            final_existing_aliases,
        )
        _reorder_stack_by_route_keys(active_stack, final_existing_aliases)
        log_info(
            _LOGGER,
            "Applied cube stack draft existing order",
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=workflow_id,
            final_existing_order=final_existing_aliases,
        )
        batch_previous_cube_states = dict(workflow_state.cubes)
        batch_previous_stack_order = list(workflow_state.stack_order)

        if not new_entries:
            _mark_workflow_surfaces_dirty(
                view,
                workflow_id,
                reason=WorkflowInvalidationReason.CUBE_REORDERED
                if not removed_aliases
                else WorkflowInvalidationReason.CUBE_REMOVED,
            )
            view.active_workflow_surface_refresher.refresh_active_workflow_surface()
            view.editor_busy.end(busy_token)
            _activate_existing_after_draft_commit(
                self._build_cube_load_ui_callbacks(),
                workflow_id=workflow_id,
                final_existing_aliases=final_existing_aliases,
            )
            log_info(
                _LOGGER,
                "Completed cube stack draft commit without new loads",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
            )
            return

        phase_started_at = perf_counter()
        alias_plan = plan_cube_stack_aliases(final_entries)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="cart_alias_plan",
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=workflow_id,
            planned_aliases=_alias_plan_debug_payload(final_entries, alias_plan),
        )
        queued_specs: list[tuple[CubeStackDraftEntry, str, int, int]] = []
        for final_index, staged_entry in [
            (index, entry)
            for index, entry in enumerate(final_entries)
            if entry.source == "new"
        ]:
            alias_name = alias_plan.planned_alias_for(staged_entry.draft_id)
            placeholder_insert_index = max(0, min(final_index, active_stack.count()))
            placeholder_item = active_stack.insertTab(
                placeholder_insert_index,
                routeKey=f"loading:{alias_name}",
                text="Loading...",
                icon=icon_provider.CLOSE.icon(),
            )
            placeholder_index = active_stack.items.index(placeholder_item)
            active_stack.setCurrentIndex(placeholder_index)
            view._pending_cubes[alias_name] = placeholder_index
            queued_specs.append(
                (staged_entry, alias_name, placeholder_index, final_index)
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cart_placeholder_inserted",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
                cube_id=staged_entry.cube_id,
                requested_display_name=staged_entry.display_name,
                cube_alias=alias_name,
                final_index=final_index,
                placeholder_index=placeholder_index,
                stack_route_keys=_stack_route_keys(active_stack),
                pending_cubes=dict(view._pending_cubes),
            )
            log_debug(
                _LOGGER,
                "Inserted cube stack draft loading placeholder",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
                cube_id=staged_entry.cube_id,
                cube_alias=alias_name,
                final_index=final_index,
                placeholder_index=placeholder_index,
            )

        log_timing(
            _LOGGER,
            "Resolved cube staging selection",
            started_at=phase_started_at,
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=workflow_id,
            staged_count=len(queued_specs),
            staged_cube_ids=[entry.cube_id for entry, _, _, _ in queued_specs],
            level="debug",
        )
        phase_started_at = perf_counter()
        log_timing(
            _LOGGER,
            "Inserted cube loading placeholder tabs",
            started_at=phase_started_at,
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=workflow_id,
            staged_count=len(queued_specs),
            placeholder_indices=[index for _, _, index, _ in queued_specs],
            level="debug",
        )

        is_batch_load = len(queued_specs) > 1
        pending_count = len(queued_specs)
        completed_aliases: list[str] = []
        completed_aliases_by_staged_index: dict[int, str] = {}
        completed_aliases_by_final_index: dict[int, str] = {}
        busy_finished = False
        cube_load_callbacks = self._build_cube_load_ui_callbacks()
        queue_failures: list[Exception] = []
        log_info(
            _LOGGER,
            "Initialized staged cube load batch",
            cube_load_trace_id=cube_load_trace_id,
            workflow_id=workflow_id,
            staged_count=len(queued_specs),
            is_batch_load=is_batch_load,
            queued_aliases=[alias for _, alias, _, _ in queued_specs],
        )

        def finish_staged_batch() -> None:
            """End staged loading and activate the final completed cube."""

            nonlocal busy_finished
            if busy_finished:
                return
            busy_finished = True
            log_info(
                _LOGGER,
                "Completed staged cube load batch",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
                staged_count=len(queued_specs),
                completed_aliases=list(completed_aliases),
                failed_queue_count=len(queue_failures),
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cart_batch_finish_start",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
                is_batch_load=is_batch_load,
                completed_aliases=list(completed_aliases),
                completed_aliases_by_final_index=dict(completed_aliases_by_final_index),
                queue_failure_types=[type(error).__name__ for error in queue_failures],
                workflow_stack_order_before_finalize=list(workflow_state.stack_order),
                stack_route_keys_before_finalize=_stack_route_keys(active_stack),
            )
            if is_batch_load:
                final_stack_order = _resolved_final_stack_order(
                    final_entries,
                    completed_aliases_by_final_index=completed_aliases_by_final_index,
                )
                _apply_reordered_aliases(
                    view.cube_stack_service,
                    workflow,
                    final_stack_order,
                )
                _reorder_stack_by_route_keys(active_stack, final_stack_order)
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="cart_batch_final_order_applied",
                    cube_load_trace_id=cube_load_trace_id,
                    workflow_id=workflow_id,
                    final_stack_order=final_stack_order,
                    workflow_stack_order_after=list(workflow_state.stack_order),
                    stack_route_keys_after=_stack_route_keys(active_stack),
                )
                link_reconciliation_service = WorkflowLinkReconciliationService(
                    prompt_endpoint_provider=view.node_behavior_service,
                    node_link_endpoint_provider=view.node_behavior_service,
                )
                link_reconciliation_service.reconcile_transition(
                    previous_cube_states=batch_previous_cube_states,
                    previous_stack_order=batch_previous_stack_order,
                    current_cube_states=workflow_state.cubes,
                    current_stack_order=list(workflow_state.stack_order),
                )
                link_reconciliation_service.sanitize_current_state(
                    cube_states=workflow_state.cubes,
                    stack_order=list(workflow_state.stack_order),
                )
                log_info(
                    _LOGGER,
                    "Reconciled staged cube batch link state",
                    cube_load_trace_id=cube_load_trace_id,
                    workflow_id=workflow_id,
                    previous_stack_order_count=len(batch_previous_stack_order),
                    final_stack_order_count=len(final_stack_order),
                    completed_staged_count=len(completed_aliases),
                    failed_queue_count=len(queue_failures),
                )
            activation_alias = next(
                (
                    completed_aliases_by_staged_index[index]
                    for index in range(len(queued_specs))
                    if index in completed_aliases_by_staged_index
                ),
                None,
            )

            def finalize_staged_batch_presentation() -> None:
                """Finish busy state and navigate after the refreshed editor is ready."""

                view.editor_busy.end(busy_token)
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="cart_batch_finalize_presentation",
                    cube_load_trace_id=cube_load_trace_id,
                    workflow_id=workflow_id,
                    activation_alias=activation_alias,
                    is_batch_load=is_batch_load,
                    queue_failure_count=len(queue_failures),
                    workflow_stack_order=list(workflow_state.stack_order),
                    stack_route_keys=_stack_route_keys(active_stack),
                )
                if is_batch_load and activation_alias is not None:
                    activate_loaded_cube = getattr(
                        cube_load_callbacks,
                        "activate_loaded_cube",
                        None,
                    )
                    if callable(activate_loaded_cube):
                        log_info(
                            _LOGGER,
                            "Activated first staged cube after batch load",
                            cube_load_trace_id=cube_load_trace_id,
                            workflow_id=workflow_id,
                            cube_alias=activation_alias,
                        )
                        activate_loaded_cube(workflow_id, activation_alias)
                if queue_failures:
                    self._show_exception_report(
                        queue_failures[0],
                        title="Staged cube queue failed",
                        message=(
                            "Failed to queue one or more staged cubes. "
                            "Please try again."
                        ),
                        stage="cube_load",
                        context=SubstituteOperationContext(
                            operation="queue_staged_cubes",
                            workflow_id=workflow_id,
                            trace_id=cube_load_trace_id,
                            values={
                                "failed_queue_count": len(queue_failures),
                                "staged_count": len(queued_specs),
                                "queued_aliases": [
                                    alias for _, alias, _, _ in queued_specs
                                ],
                            },
                        ),
                    )

            if is_batch_load:
                _reconcile_active_workflow_after_cube_batch(
                    view,
                    on_complete=finalize_staged_batch_presentation,
                )
                return
            finalize_staged_batch_presentation()

        def mark_staged_load_finished(
            *,
            staged_entry: CubeStackDraftEntry,
            alias_name: str,
            placeholder_index: int,
            staged_index: int,
            final_index: int,
            resolved_alias: str | None,
        ) -> None:
            """Record one staged load completion and finish the batch when ready."""

            nonlocal pending_count
            if busy_finished:
                return
            pending_count -= 1
            if resolved_alias is not None:
                completed_aliases.append(resolved_alias)
                completed_aliases_by_staged_index[staged_index] = resolved_alias
                completed_aliases_by_final_index[final_index] = resolved_alias
                _mark_workflow_surfaces_dirty(
                    view,
                    workflow_id,
                    reason=WorkflowInvalidationReason.CUBE_LOADED,
                )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="cart_staged_load_finished",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
                cube_id=staged_entry.cube_id,
                requested_alias=alias_name,
                resolved_alias=resolved_alias,
                staged_index=staged_index,
                final_index=final_index,
                pending_count=pending_count,
                completed_aliases=list(completed_aliases),
                workflow_stack_order=list(workflow_state.stack_order),
                stack_route_keys=_stack_route_keys(active_stack),
            )
            log_info(
                _LOGGER,
                "Completed staged cube load",
                cube_load_trace_id=cube_load_trace_id,
                workflow_id=workflow_id,
                cube_id=staged_entry.cube_id,
                cube_alias=alias_name,
                resolved_alias=resolved_alias,
                staged_index=staged_index,
                final_index=final_index,
                staged_count=len(queued_specs),
                completed_count=len(queued_specs) - pending_count,
                pending_count=pending_count,
                placeholder_index=placeholder_index,
            )
            if pending_count <= 0:
                finish_staged_batch()

        def queue_staged_load(
            *,
            staged_index: int,
            final_index: int,
            staged_entry: CubeStackDraftEntry,
            alias_name: str,
            placeholder_index: int,
            presentation_intent: CubeLoadPresentationIntent,
        ) -> None:
            """Queue one staged load immediately while isolating its callback state."""

            load_completed = False

            def finish_staged_cube_load(resolved_alias: str | None) -> None:
                """Record one staged cube completion."""

                nonlocal load_completed
                if load_completed:
                    return
                load_completed = True
                mark_staged_load_finished(
                    staged_entry=staged_entry,
                    alias_name=alias_name,
                    placeholder_index=placeholder_index,
                    staged_index=staged_index,
                    final_index=final_index,
                    resolved_alias=resolved_alias,
                )

            try:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="cart_queue_staged_load",
                    cube_load_trace_id=cube_load_trace_id,
                    workflow_id=workflow_id,
                    cube_id=staged_entry.cube_id,
                    cube_alias=alias_name,
                    staged_index=staged_index,
                    final_index=final_index,
                    placeholder_index=placeholder_index,
                    is_batch_load=is_batch_load,
                    select_after_load=presentation_intent.select_after_load,
                    scroll_after_load=presentation_intent.scroll_after_load,
                    reveal_after_load=not is_batch_load,
                    stack_route_keys=_stack_route_keys(active_stack),
                )
                log_info(
                    _LOGGER,
                    "Starting staged cube load",
                    cube_load_trace_id=cube_load_trace_id,
                    workflow_id=workflow_id,
                    cube_id=staged_entry.cube_id,
                    cube_alias=alias_name,
                    staged_index=staged_index,
                    staged_count=len(queued_specs),
                    placeholder_index=placeholder_index,
                    select_after_load=presentation_intent.select_after_load,
                    scroll_after_load=presentation_intent.scroll_after_load,
                )
                _queue_cube_loader(
                    cube_loader=cube_loader,
                    callbacks=cube_load_callbacks,
                    cube_id=staged_entry.cube_id,
                    alias_name=alias_name,
                    placeholder_index=placeholder_index,
                    presentation_intent=presentation_intent,
                    reveal_after_load=not is_batch_load,
                    on_load_finished=finish_staged_cube_load,
                    cube_load_trace_id=cube_load_trace_id,
                )
                log_timing(
                    _LOGGER,
                    "Queued staged cube load request",
                    started_at=picker_started_at,
                    cube_load_trace_id=cube_load_trace_id,
                    workflow_id=workflow_id,
                    cube_id=staged_entry.cube_id,
                    cube_alias=alias_name,
                    staged_index=staged_index,
                    staged_count=len(queued_specs),
                    placeholder_index=placeholder_index,
                    select_after_load=presentation_intent.select_after_load,
                    scroll_after_load=presentation_intent.scroll_after_load,
                    level="debug",
                )
            except (
                AttributeError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                queue_failures.append(exc)
                log_exception(
                    _LOGGER,
                    "Failed to queue staged cube load request",
                    cube_load_trace_id=cube_load_trace_id,
                    workflow_id=workflow_id,
                    cube_id=staged_entry.cube_id,
                    cube_alias=alias_name,
                    staged_index=staged_index,
                    staged_count=len(queued_specs),
                    error=exc,
                )
                finish_staged_cube_load(None)

        for staged_index, (
            staged_entry,
            alias_name,
            placeholder_index,
            final_index,
        ) in enumerate(queued_specs):
            presentation_intent = (
                CubeLoadPresentationIntent(
                    select_after_load=False,
                    scroll_after_load=False,
                )
                if is_batch_load
                else CubeLoadPresentationIntent(
                    select_after_load=True,
                    scroll_after_load=True,
                )
            )
            queue_staged_load(
                staged_index=staged_index,
                final_index=final_index,
                staged_entry=staged_entry,
                alias_name=alias_name,
                placeholder_index=placeholder_index,
                presentation_intent=presentation_intent,
            )

    def _show_exception_report(
        self,
        error: BaseException,
        *,
        title: str,
        message: str,
        stage: str,
        context: SubstituteOperationContext,
    ) -> None:
        """Show a structured, copyable report through the application error system."""

        self._resolved_error_presenter().show_exception_report(
            title=title,
            message=message,
            stage=stage,
            error=error,
            context=context,
        )

    def _resolved_error_presenter(self) -> ErrorReportPresenterProtocol:
        """Return the injected presenter or create the standard shell presenter."""

        if self._error_presenter is None:
            self._error_presenter = ErrorPresenter(parent=cast(Any, self._view))
        return self._error_presenter

    def _picker_catalog_snapshot(self) -> CubeCatalogSnapshot:
        """Return immediate picker catalog data, falling back to blocking list APIs."""

        service = self._view.cube_load_service
        snapshot = getattr(service, "picker_catalog_snapshot", None)
        if callable(snapshot):
            return cast(CubeCatalogSnapshot, snapshot())
        entries = service.list_available_cubes()
        return CubeCatalogSnapshot(entries=entries, state="fresh")

    def _refresh_picker_catalog_sync(
        self,
        cube_load_trace_id: str,
    ) -> CubeCatalogSnapshot:
        """Refresh catalog synchronously for cold-cache picker opens."""

        service = self._view.cube_load_service
        refresh = getattr(service, "refresh_picker_catalog", None)
        if callable(refresh):
            return cast(CubeCatalogSnapshot, refresh())
        entries = service.list_available_cubes()
        log_warning(
            _LOGGER,
            "Used blocking cube picker catalog list fallback",
            cube_load_trace_id=cube_load_trace_id,
            cube_count=len(entries),
        )
        return CubeCatalogSnapshot(entries=entries, state="fresh")

    def _classify_picker_records(
        self,
        records: list[CubeCatalogRecord],
        cube_load_trace_id: str,
    ) -> dict[str, CubePickerClassification]:
        """Classify picker records through the cube load service when available."""

        classify = getattr(self._view.cube_load_service, "classify_picker_cubes", None)
        if not callable(classify):
            return {}
        started_at = perf_counter()
        try:
            classifications = cast(
                dict[str, CubePickerClassification],
                classify(records),
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            log_warning(
                _LOGGER,
                "Failed to classify cubes for picker",
                cube_load_trace_id=cube_load_trace_id,
                error=repr(exc),
            )
            return {}
        log_timing(
            _LOGGER,
            "Classified cubes for picker",
            started_at=started_at,
            cube_load_trace_id=cube_load_trace_id,
            cube_count=len(records),
            classified_count=len(classifications),
            level="debug",
        )
        return classifications

    def _schedule_catalog_refresh(self, cube_load_trace_id: str) -> None:
        """Start one background picker catalog refresh when no refresh is active."""

        if self._catalog_refresh_running:
            log_warning(
                _LOGGER,
                "Skipped duplicate cube picker catalog background refresh",
                cube_load_trace_id=cube_load_trace_id,
            )
            return
        self._catalog_refresh_running = True
        log_info(
            _LOGGER,
            "Scheduled cube picker catalog background refresh",
            cube_load_trace_id=cube_load_trace_id,
        )
        self._catalog_refresh_request_id += 1
        request_id = self._catalog_refresh_request_id
        route = self._catalog_refresh_route(cube_load_trace_id)
        self._catalog_refresh_close = route.close
        scope = TaskScope(
            submitter=route.submitter,
            scope_id=f"cube_picker_catalog_refresh_{cube_load_trace_id}",
        )
        self._catalog_refresh_scope = scope
        handle = scope.submit(
            TaskRequest(
                identity=TaskIdentity(
                    request_id=request_id,
                    domain="cube_load",
                    parts=(("operation_key", "picker_catalog_refresh"),),
                ),
                context=ExecutionContext(
                    operation="refresh_cube_picker_catalog",
                    reason="cube_picker_open",
                    lane="disk_io_low_priority",
                    safe_fields=(
                        ("operation_key", "picker_catalog_refresh"),
                        ("request_id", request_id),
                        ("trace_id", cube_load_trace_id),
                    ),
                ),
                work=lambda _token: _run_catalog_refresh_task(
                    cube_load_service=self._view.cube_load_service,
                    cube_load_trace_id=cube_load_trace_id,
                ),
            )
        )
        handle.add_done_callback(
            lambda outcome: self._on_catalog_refresh_finished(
                _catalog_refresh_result_from_outcome(outcome)
            ),
            reason="cube_picker_catalog_refresh_completed",
        )

    def _catalog_refresh_route(self, cube_load_trace_id: str) -> CatalogRefreshRoute:
        """Return the execution route for one picker catalog refresh."""

        if self._catalog_refresh_route_factory is None:
            raise RuntimeError("catalog refresh route factory is required.")
        return self._catalog_refresh_route_factory(cube_load_trace_id)

    def _on_catalog_refresh_finished(
        self,
        result: CubeCatalogSnapshot | BaseException,
    ) -> None:
        """Record background catalog refresh completion."""

        self._catalog_refresh_running = False
        self._catalog_refresh_scope = None
        if self._catalog_refresh_close is not None:
            self._catalog_refresh_close()
            self._catalog_refresh_close = None
        if isinstance(result, BaseException):
            log_exception(
                _LOGGER,
                "Cube picker catalog background refresh failed",
                error=result,
            )
            return
        log_info(
            _LOGGER,
            "Cube picker catalog background refresh finished",
            catalog_state=result.state,
            cube_count=len(result.entries),
            has_error=result.error is not None,
        )


def _edit_picker_stack(
    picker: CubePickerProtocol,
    **kwargs: object,
) -> CubeStackDraftResult | None:
    """Run the picker draft editor."""

    started_at = perf_counter()
    log_info(
        _LOGGER,
        "Dispatching cube picker stack editor",
        picker_type=type(picker).__name__,
        has_edit_stack=callable(getattr(picker, "edit_stack", None)),
        has_stage_cubes=callable(getattr(picker, "stage_cubes", None)),
        has_select_cube=callable(getattr(picker, "select_cube", None)),
    )
    edit_stack = getattr(picker, "edit_stack", None)
    if callable(edit_stack):
        result = edit_stack(**kwargs)
        if isinstance(result, CubeStackDraftResult) or result is None:
            log_timing(
                _LOGGER,
                "Cube picker edit_stack returned",
                started_at=started_at,
                picker_type=type(picker).__name__,
                result_type=type(result).__name__ if result is not None else "None",
                draft_entry_count=len(result.entries) if result is not None else 0,
                level="debug",
            )
            return result
        converted = cube_stack_draft_result(list(getattr(result, "entries", ())))
        log_timing(
            _LOGGER,
            "Cube picker edit_stack result converted",
            started_at=started_at,
            picker_type=type(picker).__name__,
            result_type=type(result).__name__,
            draft_entry_count=len(converted.entries),
            level="debug",
        )
        return converted

    stage_cubes = getattr(picker, "stage_cubes", None)
    if callable(stage_cubes):
        result = stage_cubes(**kwargs)
        if result is None:
            log_timing(
                _LOGGER,
                "Cube picker stage_cubes returned no result",
                started_at=started_at,
                picker_type=type(picker).__name__,
                level="debug",
            )
            return None
        if isinstance(result, CubeStackDraftResult):
            log_timing(
                _LOGGER,
                "Cube picker stage_cubes returned draft",
                started_at=started_at,
                picker_type=type(picker).__name__,
                draft_entry_count=len(result.entries),
                level="debug",
            )
            return result
        initial_draft = kwargs.get("initial_draft")
        entries = (
            list(initial_draft.entries)
            if isinstance(initial_draft, CubeStackDraft)
            else []
        )
        entries.extend(
            _draft_entries_from_legacy_staging_result(
                list(getattr(result, "entries", ()))
            )
        )
        converted = cube_stack_draft_result(entries)
        log_timing(
            _LOGGER,
            "Cube picker stage_cubes result converted",
            started_at=started_at,
            picker_type=type(picker).__name__,
            draft_entry_count=len(converted.entries),
            level="debug",
        )
        return converted

    select_cube = getattr(picker, "select_cube", None)
    if callable(select_cube):
        selected = select_cube(**kwargs)
        if selected is None:
            log_timing(
                _LOGGER,
                "Cube picker select_cube returned no selection",
                started_at=started_at,
                picker_type=type(picker).__name__,
                level="debug",
            )
            return None
        if not isinstance(selected, CubeCatalogRecord):
            log_timing(
                _LOGGER,
                "Cube picker select_cube returned unexpected result",
                started_at=started_at,
                picker_type=type(picker).__name__,
                result_type=type(selected).__name__,
                level="debug",
            )
            return None
        initial_draft = kwargs.get("initial_draft")
        initial_entries = (
            list(initial_draft.entries)
            if isinstance(initial_draft, CubeStackDraft)
            else []
        )
        initial_entries.append(cube_stack_draft_entry_from_record(selected))
        converted = cube_stack_draft_result(initial_entries)
        log_timing(
            _LOGGER,
            "Cube picker select_cube result converted",
            started_at=started_at,
            picker_type=type(picker).__name__,
            draft_entry_count=len(converted.entries),
            level="debug",
        )
        return converted

    log_timing(
        _LOGGER,
        "Cube picker stack editor had no compatible method",
        started_at=started_at,
        picker_type=type(picker).__name__,
        level="debug",
    )
    return None


def _draft_entries_from_legacy_staging_result(
    staged_entries: list[object],
) -> list[CubeStackDraftEntry]:
    """Convert older add-only staging entries at the picker boundary."""

    draft_entries: list[CubeStackDraftEntry] = []
    for staged_entry in staged_entries:
        draft_entries.append(
            CubeStackDraftEntry(
                draft_id=str(getattr(staged_entry, "staged_id", uuid4().hex)),
                source="new",
                cube_id=str(getattr(staged_entry, "cube_id", "")),
                display_name=str(getattr(staged_entry, "display_name", "")),
                secondary_text=str(getattr(staged_entry, "secondary_text", "")),
                icon=getattr(staged_entry, "icon", None),
                existing_alias=None,
            )
        )
    return draft_entries


def _remove_stack_tab_by_route_key(
    active_stack: CubeStackProtocol,
    route_key: str,
) -> None:
    """Remove one visible cube-stack tab by route key when present."""

    for index in range(active_stack.count()):
        if active_stack.tabItem(index).routeKey() == route_key:
            active_stack.removeTab(index)
            return


def _reorder_stack_by_route_keys(
    active_stack: CubeStackProtocol,
    route_keys: list[str],
) -> None:
    """Project visible stack order through the presentation API when available."""

    reorder = getattr(active_stack, "reorder_by_route_keys", None)
    if callable(reorder):
        reorder(route_keys)


def _stack_route_keys(active_stack: CubeStackProtocol) -> list[str]:
    """Return current cube-stack route keys for compact debug context."""

    route_keys: list[str] = []
    try:
        count = active_stack.count()
    except (AttributeError, RuntimeError, TypeError):
        return route_keys
    for index in range(count):
        try:
            route_keys.append(str(active_stack.tabItem(index).routeKey()))
        except (AttributeError, RuntimeError, TypeError):
            route_keys.append("<unreadable>")
    return route_keys


def _draft_entries_debug_payload(
    entries: Sequence[CubeStackDraftEntry],
) -> tuple[dict[str, object], ...]:
    """Return compact draft-entry diagnostics without logging full cube state."""

    return tuple(
        {
            "draft_id": entry.draft_id,
            "source": entry.source,
            "cube_id": entry.cube_id,
            "display_name": entry.display_name,
            "existing_alias": entry.existing_alias,
            "content_hash": entry.content_hash,
            "catalog_revision": entry.catalog_revision,
        }
        for entry in entries
    )


def _alias_plan_debug_payload(
    entries: Sequence[CubeStackDraftEntry],
    alias_plan: object,
) -> tuple[dict[str, object], ...]:
    """Return cart alias-plan diagnostics keyed by stable draft identity."""

    payload: list[dict[str, object]] = []
    plan = cast(AliasPlanProtocol, alias_plan)
    for entry in entries:
        try:
            planned = plan.alias_for(entry.draft_id)
        except (AttributeError, KeyError, TypeError):
            payload.append(
                {
                    "draft_id": entry.draft_id,
                    "cube_id": entry.cube_id,
                    "display_name": entry.display_name,
                    "planned_alias": "<missing>",
                    "locked": False,
                }
            )
            continue
        payload.append(
            {
                "draft_id": entry.draft_id,
                "cube_id": entry.cube_id,
                "display_name": entry.display_name,
                "requested_alias": getattr(planned, "requested_alias", ""),
                "planned_alias": getattr(planned, "planned_alias", ""),
                "locked": bool(getattr(planned, "locked", False)),
            }
        )
    return tuple(payload)


def _resolved_final_stack_order(
    final_entries: Sequence[CubeStackDraftEntry],
    *,
    completed_aliases_by_final_index: Mapping[int, str],
) -> list[str]:
    """Return final workflow order from accepted draft entries and successful loads."""

    final_order: list[str] = []
    for final_index, entry in enumerate(final_entries):
        if entry.source == "existing" and entry.existing_alias is not None:
            final_order.append(entry.existing_alias)
            continue
        if entry.source == "new":
            resolved_alias = completed_aliases_by_final_index.get(final_index)
            if resolved_alias is not None:
                final_order.append(resolved_alias)
    return final_order


def _activate_existing_after_draft_commit(
    callbacks: object,
    *,
    workflow_id: str,
    final_existing_aliases: list[str],
) -> None:
    """Activate the lowest surviving existing cube after a no-load draft commit."""

    if not final_existing_aliases:
        return
    activate_loaded_cube = getattr(callbacks, "activate_loaded_cube", None)
    if callable(activate_loaded_cube):
        activate_loaded_cube(workflow_id, final_existing_aliases[-1])


def _apply_reordered_aliases(
    cube_stack_service: object,
    workflow: object,
    aliases: list[str],
) -> None:
    """Apply stack order through the service when the operation is available."""

    apply_reordered_aliases = getattr(
        cube_stack_service, "apply_reordered_aliases", None
    )
    if callable(apply_reordered_aliases):
        apply_reordered_aliases(workflow, aliases)


def _reconcile_active_workflow_after_cube_batch(
    view: WorkspaceCubePickerActionView,
    *,
    on_complete: Callable[[], None],
) -> None:
    """Structurally reconcile active surfaces before final batch navigation."""

    refresh_active_workflow_surface = (
        view.active_workflow_surface_refresher.refresh_active_workflow_surface
    )
    supports_completion_callback = _callable_declares_keyword(
        refresh_active_workflow_surface,
        "on_complete",
    )
    if supports_completion_callback:
        cast(Callable[..., None], refresh_active_workflow_surface)(
            on_complete=on_complete
        )
        return
    refresh_active_workflow_surface()
    on_complete()


def _queue_cube_loader(
    *,
    cube_loader: CubeLoaderProtocol,
    callbacks: object,
    cube_id: str,
    alias_name: str,
    placeholder_index: int,
    presentation_intent: CubeLoadPresentationIntent,
    reveal_after_load: bool,
    on_load_finished: Callable[[str | None], None],
    cube_load_trace_id: str,
) -> None:
    """Queue one cube load with trace metadata when the loader declares support."""

    cube_loader(
        callbacks,
        cube_id,
        alias_name,
        placeholder_index,
        presentation_intent=presentation_intent,
        reveal_after_load=reveal_after_load,
        on_load_finished=on_load_finished,
        cube_load_trace_id=cube_load_trace_id,
    )


def _callable_declares_keyword(callable_object: object, keyword: str) -> bool:
    """Return whether a callable explicitly declares one keyword parameter."""

    try:
        parameters = signature(cast(Callable[..., Any], callable_object)).parameters
    except (TypeError, ValueError):
        return False
    return keyword in parameters or any(
        parameter.kind is Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


__all__ = [
    "CatalogRefreshRoute",
    "CubePickerProtocol",
    "WorkspaceCubePickerActions",
    "WorkspaceCubePickerActionView",
]
