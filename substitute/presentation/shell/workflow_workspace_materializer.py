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

"""Open new, duplicated, and restored workflows into live shell surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import Protocol

from substitute.application.workflows import (
    ClosedWorkflowRecord,
    DEFAULT_WORKFLOW_TAB_LABEL,
    WorkflowSessionService,
    WorkflowTabService,
)
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.presentation.shell.closed_workflow_history import (
    ClosedWorkflowHistory,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    generation_feedback_presenter_for,
)
from substitute.presentation.shell.workflow_cube_stack_materializer import (
    WorkflowCubeStackMaterializationView,
    WorkflowCubeStackMaterializer,
)
from substitute.presentation.shell.workflow_ui_factory import workflow_ui_factory_for
from substitute.presentation.workflows.workflow_tabs_view import (
    workflow_tab_source_text,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.workflow_workspace_materializer")
_SLOW_DUPLICATE_PHASE_MS = 100.0
_SLOW_DUPLICATE_TOTAL_MS = 250.0


class WorkflowMaterializationTabBar(Protocol):
    """Describe tab operations required when opening workflow surfaces."""

    items: list[object]

    def addTab(self, routeKey: str, text: str) -> object:
        """Add a workflow tab and return its item."""

    def insertTab(self, index: int, routeKey: str, text: str) -> object:
        """Insert a workflow tab and return its item."""

    def count(self) -> int:
        """Return the current workflow tab count."""


class WorkflowMaterializationOverrideManager(Protocol):
    """Describe outgoing override cleanup before workflow activation."""

    def _clear_all_override_widgets(self) -> None:
        """Clear live override toolbar controls."""


class WorkspaceSnapshotHydrator(Protocol):
    """Describe canonical runtime hydration for a restored workflow."""

    def hydrate_restored_workspace_snapshot(
        self,
        snapshot: WorkspaceSnapshot,
        *,
        operation: str,
    ) -> WorkspaceSnapshot:
        """Rebuild graph-derived runtime state in one restored workspace."""


class WorkflowProjectionAction(Protocol):
    """Describe projection after a workflow has been materialized."""

    def __call__(
        self,
        workflow_id: str,
        *,
        force_refresh: bool = False,
        source: str = "workflow_tab_selected",
    ) -> None:
        """Project one workflow into active shell surfaces."""


class WorkflowWorkspaceMaterializationView(
    WorkflowCubeStackMaterializationView,
    Protocol,
):
    """Describe shell dependencies needed to open workflow surfaces."""

    workflow_tab_service: WorkflowTabService
    workflow_session_service: WorkflowSessionService[object]
    workflow_tabbar: WorkflowMaterializationTabBar
    workspace_restore_controller: WorkspaceSnapshotHydrator
    override_managers: Mapping[str, WorkflowMaterializationOverrideManager | None]


def _log_duplicate_phase_timing(
    message: str,
    *,
    started_at: float,
    slow_threshold_ms: float = _SLOW_DUPLICATE_PHASE_MS,
    **context: object,
) -> float:
    """Log duplicate phase duration and elevate unexpectedly slow phases."""

    elapsed_ms = elapsed_ms_since(started_at)
    log_context = dict(context)
    log_context["elapsed_ms"] = f"{elapsed_ms:.3f}"
    log_context["slow_threshold_ms"] = f"{slow_threshold_ms:.3f}"
    if elapsed_ms >= slow_threshold_ms:
        log_warning(_LOGGER, f"{message} slowly", **log_context)
    else:
        log_info(_LOGGER, message, **log_context)
    return elapsed_ms


class WorkflowWorkspaceMaterializer:
    """Register workflow state and build the corresponding live shell UI."""

    def __init__(
        self,
        view: WorkflowWorkspaceMaterializationView,
        *,
        closed_workflow_history: ClosedWorkflowHistory,
        project_workflow: WorkflowProjectionAction,
    ) -> None:
        """Store opening collaborators with explicit history and projection owners."""

        self._view = view
        self._closed_workflow_history = closed_workflow_history
        self._project_workflow = project_workflow
        self._cube_stack_materializer = WorkflowCubeStackMaterializer(view)

    def add_workflow(self) -> str:
        """Create, register, activate, and project a new workflow."""

        view = self._view
        self._clear_outgoing_override_widgets()
        planned_tab = view.workflow_tab_service.plan_new_workflow_tab(
            base_name=DEFAULT_WORKFLOW_TAB_LABEL,
            existing_labels={
                workflow_tab_source_text(item) for item in view.workflow_tabbar.items
            },
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
        self._project_workflow(transition.workflow_id, force_refresh=True)
        return transition.workflow_id

    def reopen_latest_closed_workflow(self) -> bool:
        """Reopen the most recently closed workflow when available."""

        record = self._closed_workflow_history.pop_latest()
        if record is None:
            self._closed_workflow_history.sync_reopen_availability()
            log_info(
                _LOGGER,
                "Reopen closed workflow skipped because buffer was empty",
                operation="reopen_closed_workflow",
            )
            return False
        return self._reopen_closed_workflow_record(record)

    def reopen_closed_workflow(self, close_id: str) -> bool:
        """Reopen a specific closed workflow record when available."""

        record = self._closed_workflow_history.pop(close_id)
        if record is None:
            self._closed_workflow_history.sync_reopen_availability()
            log_info(
                _LOGGER,
                "Reopen closed workflow skipped because record was missing",
                operation="reopen_closed_workflow",
                close_id=close_id,
            )
            return False
        return self._reopen_closed_workflow_record(record)

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
        self._clear_outgoing_override_widgets()

        planned_tab = view.workflow_tab_service.plan_new_workflow_tab(
            base_name=base_label,
            existing_labels={
                workflow_tab_source_text(item) for item in view.workflow_tabbar.items
            },
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
        self._cube_stack_materializer.materialize(
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
        self._project_workflow(transition.workflow_id, force_refresh=True)
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
        unsaved_work_service = getattr(view, "unsaved_work_service", None)
        mark_document_dirty = getattr(unsaved_work_service, "mark_dirty", None)
        if callable(mark_document_dirty):
            mark_document_dirty(transition.workflow_id)
        return transition.workflow_id

    def _reopen_closed_workflow_record(self, record: ClosedWorkflowRecord) -> bool:
        """Decode, register, materialize, and project one closed workflow record."""

        view = self._view
        snapshot = self._closed_workflow_history.decode_for_reopen(record)
        if snapshot is None:
            self._closed_workflow_history.sync_reopen_availability()
            return False
        hydrated_workspace = (
            view.workspace_restore_controller.hydrate_restored_workspace_snapshot(
                WorkspaceSnapshot(
                    schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
                    workflows=(snapshot,),
                    tab_order=(snapshot.workflow_id,),
                    active_route=snapshot.workflow_id,
                    active_workflow_id=snapshot.workflow_id,
                ),
                operation="reopen_closed_workflow",
            )
        )
        if len(hydrated_workspace.workflows) != 1:
            raise RuntimeError(
                "Closed workflow hydration returned an invalid workspace."
            )
        snapshot = hydrated_workspace.workflows[0]
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
            snapshot = self._closed_workflow_history.rekey_snapshot(
                snapshot,
                new_workflow_id=workflow_id,
            )
        self._clear_outgoing_override_widgets()
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
        self._cube_stack_materializer.materialize(
            transition.workflow_id,
            snapshot.workflow,
            active_cube_alias=snapshot.active_cube_alias,
        )
        self._project_workflow(
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
        self._closed_workflow_history.sync_reopen_availability()
        return True

    def _insert_reopened_workflow_tab(
        self,
        workflow_id: str,
        tab_label: str,
        preferred_index: int,
    ) -> None:
        """Insert a reopened workflow tab at its preferred valid index."""

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
        return self._view.workflow_tab_service.generate_workflow_id(existing_ids)

    def _clear_outgoing_override_widgets(self) -> None:
        """Clear controls belonging to the workflow being deactivated."""

        view = self._view
        outgoing_manager = view.override_managers.get(
            view.workflow_session_service.active_workflow_id
        )
        if outgoing_manager is not None:
            outgoing_manager._clear_all_override_widgets()


__all__ = [
    "WorkflowProjectionAction",
    "WorkflowWorkspaceMaterializationView",
    "WorkflowWorkspaceMaterializer",
]
