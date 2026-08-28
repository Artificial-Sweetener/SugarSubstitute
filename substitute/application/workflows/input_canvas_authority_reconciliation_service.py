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

"""Repair persisted Input surfaces that no longer have graph authority."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.application.workflows.generation_input_image_selection_service import (
    GenerationInputImageSelection,
)
from substitute.application.workflows.input_canvas_ports import (
    InputCanvasStateServicePort,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger(
    "application.workflows.input_canvas_authority_reconciliation_service"
)


@dataclass(frozen=True, slots=True)
class InputCanvasAuthorityReconciliationReport:
    """Describe stale Input surface state discovered and retired for one workflow."""

    workflow_id: str
    stale_input_keys: tuple[str, ...] = ()
    removed_input_keys: tuple[str, ...] = ()

    @property
    def unresolved_input_keys(self) -> tuple[str, ...]:
        """Return stale keys that could not be retired through the state owner."""

        removed = set(self.removed_input_keys)
        return tuple(key for key in self.stale_input_keys if key not in removed)


class InputCanvasAuthorityReconciliationService:
    """Retire invalid persisted surfaces through the authoritative canvas owner."""

    def __init__(
        self,
        *,
        select_generation_images: Callable[
            [WorkflowState], GenerationInputImageSelection
        ],
        input_canvas_state_service: InputCanvasStateServicePort,
    ) -> None:
        """Bind graph authority inspection and complete canvas-state retirement."""

        self._select_generation_images = select_generation_images
        self._input_canvas_state_service = input_canvas_state_service

    def reconcile(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
    ) -> InputCanvasAuthorityReconciliationReport:
        """Remove every persisted Input surface rejected by current graph authority."""

        workflow = workflows.get(workflow_id)
        if workflow is None:
            return InputCanvasAuthorityReconciliationReport(workflow_id=workflow_id)
        selection = self._select_generation_images(workflow)
        stale_input_keys = selection.unresolved_input_keys
        removed_input_keys = tuple(
            input_key
            for input_key in stale_input_keys
            if self._input_canvas_state_service.drop_input_surface(
                workflows,
                workflow_id,
                input_key,
            )
        )
        report = InputCanvasAuthorityReconciliationReport(
            workflow_id=workflow_id,
            stale_input_keys=stale_input_keys,
            removed_input_keys=removed_input_keys,
        )
        if removed_input_keys:
            log_info(
                _LOGGER,
                "Retired stale Input canvas surfaces without graph authority",
                workflow_id=workflow_id,
                stale_input_keys=stale_input_keys,
                removed_input_keys=removed_input_keys,
            )
        if report.unresolved_input_keys:
            log_warning(
                _LOGGER,
                "Input canvas surfaces remained stale after authority reconciliation",
                workflow_id=workflow_id,
                unresolved_input_keys=report.unresolved_input_keys,
            )
        return report


__all__ = [
    "InputCanvasAuthorityReconciliationReport",
    "InputCanvasAuthorityReconciliationService",
]
