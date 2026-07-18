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

"""Resolve whether workflows expose input-canvas interactions."""

from __future__ import annotations

from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import WorkflowState


class InputCanvasCapabilityService:
    """Resolve active workflow capability for the shared Input canvas."""

    def __init__(
        self,
        input_canvas_plan_service: InputCanvasPlanService,
        graph_section_service: WorkflowGraphSectionService,
    ) -> None:
        """Capture the shared graph-section and endpoint authorities."""

        self._input_canvas_plan_service = input_canvas_plan_service
        self._graph_section_service = graph_section_service

    def workflow_needs_input_canvas(self, workflow: WorkflowState | None) -> bool:
        """Return whether a workflow should expose input-canvas UI."""

        if workflow is None:
            return False
        for section_key in self._graph_section_service.section_keys(workflow):
            graph = self._graph_section_service.graph(workflow, section_key)
            if graph is None:
                continue
            plan = self._input_canvas_plan_service.build_plan(
                section_key,
                graph,
            )
            if plan.exposes_input_canvas:
                return True
        return False


__all__ = ["InputCanvasCapabilityService"]
