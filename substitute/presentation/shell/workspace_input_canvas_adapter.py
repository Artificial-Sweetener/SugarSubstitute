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

"""Adapt workspace shell events to Input canvas presenter ownership."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from time import perf_counter
from typing import Protocol, cast

from substitute.presentation.shell.workspace_ports import InputCanvasPresenterProtocol
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.workspace_input_canvas_adapter")
_SLOW_REHYDRATION_PHASE_MS = 100.0


class WorkflowLookupProtocol(Protocol):
    """Describe workflow lookup required for duplicated canvas rehydration."""

    def get_workflow(self, workflow_id: str) -> object | None:
        """Return workflow state for one workflow id."""


ScheduleRehydrationStep = Callable[[Callable[[], None]], None]
MaterializeLoadedCubeInputCanvas = Callable[[str, str], None]


def input_canvas_presenter_for_view(
    canvas_view: object,
) -> InputCanvasPresenterProtocol:
    """Return the required Input canvas presenter from a shell canvas view."""

    presenter = getattr(canvas_view, "input_canvas_presenter", None)
    if presenter is None:
        raise RuntimeError("InputCanvasPresenter is required for Input canvas intent.")
    return cast(InputCanvasPresenterProtocol, presenter)


def handle_input_image_changed_for_view(
    canvas_view: object,
    cube_alias: str,
    node_name: str,
    image_path: str,
) -> None:
    """Route an editor-panel LoadImage change intent to the presenter."""

    input_canvas_presenter_for_view(canvas_view).handle_input_image_changed(
        cube_alias,
        node_name,
        image_path,
    )


def handle_input_image_clicked_for_view(
    canvas_view: object,
    cube_alias: str,
    node_name: str,
    image_path: str,
) -> None:
    """Route an editor-panel LoadImage focus intent to the presenter."""

    input_canvas_presenter_for_view(canvas_view).handle_input_image_clicked(
        cube_alias,
        node_name,
        image_path,
    )


def handle_input_canvas_image_loaded_for_view(
    canvas_view: object,
    image_id: object,
    image_path: str,
) -> None:
    """Route a confirmed Input canvas image load to the presenter."""

    input_canvas_presenter_for_view(canvas_view).handle_input_canvas_image_loaded(
        image_id,
        image_path,
    )


def refresh_active_mask_pickers_for_view(canvas_view: object) -> None:
    """Route active mask-picker refresh to the presenter."""

    input_canvas_presenter_for_view(canvas_view).refresh_active_mask_pickers()


def handle_input_mask_changed_for_view(
    canvas_view: object,
    cube_alias: str,
    node_name: str,
    mask_path: str,
) -> None:
    """Route an editor-panel LoadImageMask change intent to the presenter."""

    input_canvas_presenter_for_view(canvas_view).handle_input_mask_changed(
        cube_alias,
        node_name,
        mask_path,
    )


def handle_input_mask_clicked_for_view(
    canvas_view: object,
    cube_alias: str,
    node_name: str,
    mask_path: str,
) -> None:
    """Route an editor-panel LoadImageMask focus intent to the presenter."""

    input_canvas_presenter_for_view(canvas_view).handle_input_mask_clicked(
        cube_alias,
        node_name,
        mask_path,
    )


def handle_mask_save_completed_for_view(
    canvas_view: object,
    mask_id: str,
    path: str,
) -> None:
    """Route QPane mask-save completion to presenter-owned refresh logic."""

    input_canvas_presenter_for_view(canvas_view).handle_mask_save_completed(
        mask_id,
        path,
    )


def reconcile_active_input_canvas_image_for_view(canvas_view: object) -> None:
    """Reconcile the active Input image before generation request capture."""

    input_canvas_presenter_for_view(canvas_view).reconcile_active_input_canvas_image()


def materialize_loaded_cube_input_canvas_for_view(
    canvas_view: object,
    workflow_id: str,
    cube_alias: str,
) -> None:
    """Materialize loaded-cube Input canvas state through the presenter."""

    log_debug(
        _LOGGER,
        "Cube load detail",
        event="adapter_materialize_input_canvas",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
    )
    input_canvas_presenter_for_view(canvas_view).materialize_loaded_cube_input_canvas(
        workflow_id, cube_alias
    )


def rehydrate_duplicated_workflow_input_canvas(
    *,
    workflow_session_service: WorkflowLookupProtocol,
    workflow_id: str,
    materialize_loaded_cube_input_canvas: MaterializeLoadedCubeInputCanvas,
    schedule_next: ScheduleRehydrationStep,
) -> None:
    """Rebuild live Input canvas state for a duplicated workflow."""

    rehydrate_started_at = perf_counter()
    workflow = workflow_session_service.get_workflow(workflow_id)
    if workflow is None:
        log_warning(
            _LOGGER,
            "Workflow duplicate input canvas rehydration skipped because workflow was missing",
            duplicated_workflow_id=workflow_id,
        )
        return
    stack_order = list(getattr(workflow, "stack_order", ()) or [])
    log_info(
        _LOGGER,
        "Workflow duplicate input canvas rehydration started",
        duplicated_workflow_id=workflow_id,
        stack_order_count=len(stack_order),
    )
    _rehydrate_duplicated_workflow_input_canvas_cube(
        workflow_id=workflow_id,
        stack_order=stack_order,
        next_index=0,
        rehydrate_started_at=rehydrate_started_at,
        materialize_loaded_cube_input_canvas=materialize_loaded_cube_input_canvas,
        schedule_next=schedule_next,
    )


def _rehydrate_duplicated_workflow_input_canvas_cube(
    *,
    workflow_id: str,
    stack_order: Sequence[object],
    next_index: int,
    rehydrate_started_at: float,
    materialize_loaded_cube_input_canvas: MaterializeLoadedCubeInputCanvas,
    schedule_next: ScheduleRehydrationStep,
) -> None:
    """Materialize one duplicated Input canvas cube and schedule the next."""

    if next_index >= len(stack_order):
        _log_rehydration_phase_timing(
            "Workflow duplicate input canvas rehydration completed",
            started_at=rehydrate_started_at,
            duplicated_workflow_id=workflow_id,
            stack_order_count=len(stack_order),
        )
        return

    cube_alias = str(stack_order[next_index])
    cube_started_at = perf_counter()
    log_info(
        _LOGGER,
        "Workflow duplicate input canvas cube rehydration started",
        duplicated_workflow_id=workflow_id,
        cube_alias=cube_alias,
        cube_index=next_index,
        stack_order_count=len(stack_order),
    )
    materialize_loaded_cube_input_canvas(workflow_id, cube_alias)
    _log_rehydration_phase_timing(
        "Workflow duplicate input canvas cube rehydration completed",
        started_at=cube_started_at,
        duplicated_workflow_id=workflow_id,
        cube_alias=cube_alias,
        cube_index=next_index,
        stack_order_count=len(stack_order),
    )
    schedule_next(
        lambda: _rehydrate_duplicated_workflow_input_canvas_cube(
            workflow_id=workflow_id,
            stack_order=stack_order,
            next_index=next_index + 1,
            rehydrate_started_at=rehydrate_started_at,
            materialize_loaded_cube_input_canvas=materialize_loaded_cube_input_canvas,
            schedule_next=schedule_next,
        )
    )


def _log_rehydration_phase_timing(
    message: str,
    *,
    started_at: float,
    slow_threshold_ms: float = _SLOW_REHYDRATION_PHASE_MS,
    **context: object,
) -> float:
    """Log duplicated Input canvas rehydration phase duration."""

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
    "MaterializeLoadedCubeInputCanvas",
    "ScheduleRehydrationStep",
    "WorkflowLookupProtocol",
    "handle_input_canvas_image_loaded_for_view",
    "handle_input_image_changed_for_view",
    "handle_input_image_clicked_for_view",
    "handle_input_mask_changed_for_view",
    "handle_input_mask_clicked_for_view",
    "handle_mask_save_completed_for_view",
    "input_canvas_presenter_for_view",
    "materialize_loaded_cube_input_canvas_for_view",
    "reconcile_active_input_canvas_image_for_view",
    "refresh_active_mask_pickers_for_view",
    "rehydrate_duplicated_workflow_input_canvas",
]
