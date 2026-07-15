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

"""Coordinate workflow tab duplication through explicit shell ports."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import Any, Protocol

from substitute.presentation.shell.workspace_input_canvas_adapter import (
    MaterializeLoadedCubeInputCanvas,
    ScheduleRehydrationStep,
    rehydrate_duplicated_workflow_input_canvas,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.workflow_duplicate_controller")
_SLOW_DUPLICATE_PHASE_MS = 100.0
_SLOW_DUPLICATE_TOTAL_MS = 250.0


class WorkflowSessionLookupProtocol(Protocol):
    """Describe workflow-session lookup required for duplication."""

    def get_workflow(self, workflow_id: str) -> object | None:
        """Return workflow state for one workflow id."""


class WorkflowTabItemProtocol(Protocol):
    """Describe tab item text lookup required for duplicate labels."""

    def text(self) -> str:
        """Return the current workflow tab label."""


class WorkflowTabBarLookupProtocol(Protocol):
    """Describe workflow-tab lookup required for duplicate labels."""

    itemMap: Mapping[str, WorkflowTabItemProtocol]


class WorkflowDuplicateView(Protocol):
    """Describe shell state needed to duplicate one workflow tab."""

    workflow_session_service: WorkflowSessionLookupProtocol
    workflow_tabbar: WorkflowTabBarLookupProtocol


class WorkflowDuplicateServiceProtocol(Protocol):
    """Describe durable workflow clone creation."""

    def duplicate_workflow(self, source: Any) -> object:
        """Return an independent workflow copy."""


class WorkflowDuplicateWorkspaceProtocol(Protocol):
    """Describe shell workspace registration for cloned workflow state."""

    def duplicate_workflow(
        self,
        source_workflow_id: str,
        cloned_workflow: object,
        *,
        base_label: str,
    ) -> str | None:
        """Register cloned workflow state and return the new workflow id."""


def duplicate_workflow_tab_for_view(
    *,
    view: WorkflowDuplicateView,
    workflow_workspace: WorkflowDuplicateWorkspaceProtocol,
    workflow_duplicate_service: WorkflowDuplicateServiceProtocol,
    workflow_id: str,
    materialize_loaded_cube_input_canvas: MaterializeLoadedCubeInputCanvas,
    schedule_rehydration: ScheduleRehydrationStep,
) -> None:
    """Duplicate one workflow tab from in-memory workflow state."""

    duplicate_started_at = perf_counter()
    workflow = view.workflow_session_service.get_workflow(workflow_id)
    tab_item = view.workflow_tabbar.itemMap.get(workflow_id)
    base_label = tab_item.text() if tab_item is not None else workflow_id
    log_info(
        _LOGGER,
        "Workflow duplicate requested",
        source_workflow_id=workflow_id,
        base_label=base_label,
        source_workflow_found=workflow is not None,
        cube_count=len(getattr(workflow, "cubes", {}) or {}) if workflow else 0,
        stack_order_count=(
            len(getattr(workflow, "stack_order", []) or []) if workflow else 0
        ),
    )
    if workflow is None:
        log_warning(
            _LOGGER,
            "Workflow duplicate skipped because source workflow was missing",
            source_workflow_id=workflow_id,
            base_label=base_label,
        )
        return

    clone_started_at = perf_counter()
    log_info(
        _LOGGER,
        "Workflow duplicate clone requested",
        source_workflow_id=workflow_id,
        base_label=base_label,
    )
    cloned_workflow = workflow_duplicate_service.duplicate_workflow(workflow)
    _log_duplicate_phase_timing(
        "Workflow duplicate clone phase completed",
        started_at=clone_started_at,
        source_workflow_id=workflow_id,
        base_label=base_label,
        cube_count=len(getattr(cloned_workflow, "cubes", {}) or {}),
        stack_order_count=len(getattr(cloned_workflow, "stack_order", []) or []),
    )

    registration_started_at = perf_counter()
    log_info(
        _LOGGER,
        "Workflow duplicate registration requested",
        source_workflow_id=workflow_id,
        base_label=base_label,
    )
    duplicated_workflow_id = workflow_workspace.duplicate_workflow(
        workflow_id,
        cloned_workflow,
        base_label=base_label,
    )
    if duplicated_workflow_id is None:
        _log_duplicate_phase_timing(
            "Workflow duplicate registration returned no workflow",
            started_at=registration_started_at,
            source_workflow_id=workflow_id,
            base_label=base_label,
        )
        return
    _log_duplicate_phase_timing(
        "Workflow duplicate registration completed",
        started_at=registration_started_at,
        source_workflow_id=workflow_id,
        duplicated_workflow_id=duplicated_workflow_id,
        base_label=base_label,
    )
    log_info(
        _LOGGER,
        "Workflow duplicate input canvas rehydration scheduled",
        source_workflow_id=workflow_id,
        duplicated_workflow_id=duplicated_workflow_id,
        base_label=base_label,
    )
    schedule_rehydration(
        lambda: rehydrate_duplicated_workflow_input_canvas(
            workflow_session_service=view.workflow_session_service,
            workflow_id=duplicated_workflow_id,
            materialize_loaded_cube_input_canvas=materialize_loaded_cube_input_canvas,
            schedule_next=schedule_rehydration,
        )
    )
    _log_duplicate_phase_timing(
        "Workflow duplicate request completed",
        started_at=duplicate_started_at,
        slow_threshold_ms=_SLOW_DUPLICATE_TOTAL_MS,
        source_workflow_id=workflow_id,
        duplicated_workflow_id=duplicated_workflow_id,
        base_label=base_label,
    )


def _log_duplicate_phase_timing(
    message: str,
    *,
    started_at: float,
    slow_threshold_ms: float = _SLOW_DUPLICATE_PHASE_MS,
    **context: object,
) -> float:
    """Log duplicate phase duration and warn when the phase is slow."""

    elapsed_ms = elapsed_ms_since(started_at)
    log_context = dict(context)
    log_context["elapsed_ms"] = f"{elapsed_ms:.3f}"
    log_context["slow_threshold_ms"] = f"{slow_threshold_ms:.3f}"
    if elapsed_ms >= slow_threshold_ms:
        log_warning(_LOGGER, f"{message} slowly", **log_context)
    else:
        log_info(_LOGGER, message, **log_context)
    return elapsed_ms


__all__ = [
    "WorkflowDuplicateServiceProtocol",
    "WorkflowDuplicateView",
    "WorkflowDuplicateWorkspaceProtocol",
    "duplicate_workflow_tab_for_view",
]
