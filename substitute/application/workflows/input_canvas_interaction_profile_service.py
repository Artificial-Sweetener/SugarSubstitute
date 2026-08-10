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

"""Resolve Input canvas interactions from authoritative workflow surfaces."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    InputCanvasSurface,
    InputCanvasSurfaceKind,
    WorkflowState,
)
from substitute.domain.workflow.input_canvas_interaction_profile import (
    InputCanvasInteractionCapability,
    InputCanvasInteractionProfile,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_warning_exception,
)

_LOGGER = get_logger("application.workflows.input_canvas_interaction_profile_service")
_EMPTY_PROFILE = InputCanvasInteractionProfile()


class InputCanvasInteractionProfileService:
    """Derive interaction applicability from exact canvas and graph identity."""

    def __init__(
        self,
        *,
        input_canvas_plan_service: InputCanvasPlanService,
        graph_section_service: WorkflowGraphSectionService,
    ) -> None:
        """Capture the graph and Input surface planning authorities."""

        self._plans = input_canvas_plan_service
        self._graphs = graph_section_service

    def profile_for(
        self,
        workflow: WorkflowState | None,
        image_id: UUID | None,
    ) -> InputCanvasInteractionProfile:
        """Return a conservative interaction profile for the routed image."""

        if workflow is None or image_id is None:
            return _EMPTY_PROFILE
        entries = tuple(
            entry
            for entry in workflow.canvas.image_entries.values()
            if entry.image_id == image_id
        )
        if len(entries) != 1:
            self._log_unresolved(
                image_id, "ambiguous_or_missing_image_entry", len(entries)
            )
            return _EMPTY_PROFILE
        input_key = entries[0].input_key
        matching_surfaces: list[InputCanvasSurface] = []
        for section_key in self._graphs.section_keys(workflow):
            graph = self._graphs.graph(workflow, section_key)
            if graph is None:
                continue
            try:
                plan = self._plans.build_plan(section_key, graph)
            except Exception as error:
                log_warning_exception(
                    _LOGGER,
                    "Input canvas interaction planning failed closed",
                    error=error,
                    image_id=str(image_id),
                    input_key=input_key,
                    section_key=section_key,
                )
                return _EMPTY_PROFILE
            matching_surfaces.extend(
                surface for surface in plan.surfaces if surface.input_key == input_key
            )
        if len(matching_surfaces) != 1:
            self._log_unresolved(
                image_id,
                "ambiguous_or_missing_planned_surface",
                len(matching_surfaces),
                input_key=input_key,
            )
            return _EMPTY_PROFILE
        if matching_surfaces[0].kind is not InputCanvasSurfaceKind.AUTHORED_IMAGE:
            return _EMPTY_PROFILE
        return InputCanvasInteractionProfile(
            frozenset({InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE})
        )

    @staticmethod
    def _log_unresolved(
        image_id: UUID,
        reason: str,
        candidate_count: int,
        *,
        input_key: str = "",
    ) -> None:
        """Record why a routed image received a fail-closed profile."""

        log_debug(
            _LOGGER,
            "Input canvas interaction profile unresolved",
            image_id=str(image_id),
            input_key=input_key,
            candidate_count=candidate_count,
            reason=reason,
        )


__all__ = ["InputCanvasInteractionProfileService"]
