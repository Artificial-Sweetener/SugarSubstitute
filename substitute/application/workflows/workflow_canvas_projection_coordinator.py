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

"""Coordinate active workflow projection across Input and Output canvases."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.workflows.input_canvas_state_service import (
    InputCanvasStateService,
)
from substitute.application.workflows.output_canvas_projection_coordinator import (
    OutputCanvasProjectionCoordinator,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.workflows.workflow_canvas_projection_coordinator")


class WorkflowCanvasProjectionCoordinator:
    """Project active workflow canvas state through named Input and Output owners."""

    def __init__(
        self,
        *,
        input_canvas_state_service: InputCanvasStateService,
        output_canvas_projection_coordinator: OutputCanvasProjectionCoordinator,
    ) -> None:
        """Store the Input and Output canvas projection owners."""

        self._input_canvas_state_service = input_canvas_state_service
        self._output_canvas_projection_coordinator = (
            output_canvas_projection_coordinator
        )

    def project_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
    ) -> None:
        """Project the active workflow into shared Input and Output canvases."""

        log_debug(
            _LOGGER,
            "workflow canvas project workflow started",
            active_workflow_id=active_workflow_id,
            active_workflow_found=active_workflow_id in workflows,
            workflow_ids=tuple(workflows.keys()),
        )
        self._input_canvas_state_service.project_workflow(
            workflows,
            active_workflow_id,
        )
        self._output_canvas_projection_coordinator.project_workflow(
            workflows,
            active_workflow_id,
        )
        log_debug(
            _LOGGER,
            "workflow canvas project workflow completed",
            active_workflow_id=active_workflow_id,
        )


__all__ = ["WorkflowCanvasProjectionCoordinator"]
