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

"""Present scalar Input mask selection and validation outcomes."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, opaque_text
from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable
from pathlib import Path
from typing import cast

from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    SubstituteOperationContext,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_mask_picker_presenter import (
    InputMaskPickerPresenter,
)
from substitute.presentation.canvas.input.input_materialization_presenter import (
    InputMaterializationPresenter,
)
from substitute.presentation.canvas.input.input_presentation_ports import (
    InputMaskSelectionWorkflowPort,
    WorkflowSessionPort,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_mask_selection_presenter")


class InputMaskSelectionPresenter:
    """Own scalar mask selection, validation feedback, and projection."""

    def __init__(
        self,
        *,
        active_workflow: Callable[[], WorkflowState | None],
        workflow_session: WorkflowSessionPort,
        workflow_inputs: InputMaskSelectionWorkflowPort,
        workflow_name: Callable[[str], str],
        projects_dir: Callable[[], Path],
        materialization: InputMaterializationPresenter,
        mask_pickers: InputMaskPickerPresenter,
        mark_changed: Callable[[str], None] | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
    ) -> None:
        """Store mask workflow, projection, invalidation, and error owners."""

        self._active_workflow = active_workflow
        self._workflow_session = workflow_session
        self._workflow_inputs = workflow_inputs
        self._workflow_name = workflow_name
        self._projects_dir = projects_dir
        self._materialization = materialization
        self._mask_pickers = mask_pickers
        self._mark_changed = mark_changed
        self._error_presenter = error_presenter

    def apply_selection(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> bool:
        """Apply one selected scalar mask and report acceptance."""

        if self._active_workflow() is None or not mask_path:
            return False
        workflow_id = self._workflow_session.active_workflow_id
        workflow_name = self._workflow_name(workflow_id)
        projects_dir = self._projects_dir()
        result = self._workflow_inputs.apply_user_selected_input_mask(
            workflows=self._workflow_session.workflows,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            mask_node_name=node_name,
            mask_path=mask_path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        rejection_reason = getattr(result, "rejection_reason", "")
        selected_dimensions = getattr(result, "selected_dimensions", None)
        required_dimensions = getattr(result, "required_dimensions", None)
        if rejection_reason == "unverified_dimensions" or (
            rejection_reason == "dimension_mismatch"
            and (selected_dimensions is None or required_dimensions is None)
        ):
            self._report_unverified_dimensions(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_path=mask_path,
                selected_dimensions=selected_dimensions,
                required_dimensions=required_dimensions,
            )
            return False
        if rejection_reason == "dimension_mismatch":
            self._report_dimension_mismatch(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_path=mask_path,
                selected_dimensions=cast(tuple[int, int], selected_dimensions),
                required_dimensions=cast(tuple[int, int], required_dimensions),
            )
            return False
        if not bool(getattr(result, "applied", False)):
            return False
        materialization_result = getattr(result, "materialization_result", None)
        if materialization_result is not None:
            self._materialization.apply(
                materialization_result,
                projects_dir=projects_dir,
            )
        self._mask_pickers.refresh(
            cube_alias,
            node_name,
            projects_dir=projects_dir,
        )
        if self._mark_changed is not None:
            self._mark_changed(workflow_id)
        return True

    def _report_dimension_mismatch(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        selected_dimensions: tuple[int, int],
        required_dimensions: tuple[int, int],
    ) -> None:
        """Report a selected mask whose dimensions differ from its image."""

        log_warning(
            _LOGGER,
            "Rejected user-selected input mask with wrong dimensions",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_mask_size=selected_dimensions,
            required_image_size=required_dimensions,
        )
        self._show_dimension_error(
            title=app_text("Mask dimensions do not match"),
            message=app_text(
                "The selected mask dimensions do not match the loaded input image."
            ),
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_text=f"{selected_dimensions[0]}x{selected_dimensions[1]}",
            required_text=f"{required_dimensions[0]}x{required_dimensions[1]}",
            values={
                "selected_mask_width": selected_dimensions[0],
                "selected_mask_height": selected_dimensions[1],
                "required_image_width": required_dimensions[0],
                "required_image_height": required_dimensions[1],
            },
        )

    def _report_unverified_dimensions(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        selected_dimensions: tuple[int, int] | None,
        required_dimensions: tuple[int, int] | None,
    ) -> None:
        """Report a selected mask whose dimensions cannot be verified."""

        log_warning(
            _LOGGER,
            "Rejected user-selected input mask with unverified dimensions",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_mask_size=selected_dimensions,
            required_image_size=required_dimensions,
        )
        selected_text = _dimensions_text(selected_dimensions)
        required_text = _dimensions_text(required_dimensions)
        self._show_dimension_error(
            title=app_text("Mask dimensions could not be verified"),
            message=app_text(
                "The selected mask dimensions could not be verified against "
                "the loaded input image."
            ),
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_text=selected_text,
            required_text=required_text,
            values={
                "selected_mask_size": selected_text,
                "required_image_size": required_text,
            },
        )

    def _show_dimension_error(
        self,
        *,
        title: ApplicationText,
        message: ApplicationText,
        workflow_id: str,
        workflow_name: str,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        selected_text: str,
        required_text: str,
        values: dict[str, object],
    ) -> None:
        """Present shared mask-dimension diagnostic context."""

        if self._error_presenter is None:
            return
        self._error_presenter.show_error_report(
            ErrorReport(
                kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
                title=title,
                message=message,
                stage="input_mask",
                workflow_id=workflow_id,
                technical_detail=(
                    f"Selected mask: {selected_text}\n"
                    f"Required image: {required_text}\n"
                    f"Cube: {cube_alias}\n"
                    f"Mask node: {node_name}\n"
                    f"Path: {mask_path}"
                ),
                operation_context=SubstituteOperationContext(
                    operation="load_input_mask",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    path=mask_path,
                    node_name=node_name,
                    cube_alias=cube_alias,
                    values=values,
                ),
            )
        )


def _dimensions_text(dimensions: tuple[int, int] | None) -> str:
    """Return diagnostic text for optional image dimensions."""

    if dimensions is None:
        return opaque_text("unavailable")
    return f"{dimensions[0]}x{dimensions[1]}"


__all__ = ["InputMaskSelectionPresenter"]
