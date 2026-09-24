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

"""Resolve graph-owned Input canvas plans, bindings, and image identities."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.input_canvas_models import (
    LoadedInputCanvasImageIdentityResolution,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    InputCanvasMaskBinding,
    InputCanvasPlan,
    WorkflowState,
)


class InputCanvasBindingService:
    """Own graph-to-canvas binding discovery and admitted-image identity."""

    def __init__(
        self,
        *,
        plans: InputCanvasPlanService,
        graph_sections: WorkflowGraphSectionService,
    ) -> None:
        """Store the graph and plan owners used for binding queries."""

        self._plans = plans
        self._graph_sections = graph_sections

    def plan(self, workflow: WorkflowState, section_key: str) -> InputCanvasPlan:
        """Return the unified Input canvas plan for one graph section."""

        graph = self._graph_sections.graph(workflow, section_key)
        if graph is None:
            return InputCanvasPlan(section_key=section_key)
        return self._plans.build_plan(section_key, graph)

    def bindings_for_image(
        self,
        workflow: WorkflowState,
        section_key: str,
        image_node_name: str,
    ) -> tuple[InputCanvasMaskBinding, ...]:
        """Return editable mask bindings for one workflow image node."""

        return self.plan(workflow, section_key).bindings_for_surface_key(
            image_node_name
        )

    def binding_for_mask(
        self,
        workflow: WorkflowState,
        section_key: str,
        mask_node_name: str,
    ) -> InputCanvasMaskBinding | None:
        """Return one editable mask binding when the graph defines it."""

        return self.plan(workflow, section_key).binding_for_mask(mask_node_name)

    def unambiguous_image_identity(
        self,
        workflow: WorkflowState,
    ) -> tuple[str, str] | None:
        """Return the only graph-bound Input image identity in a workflow."""

        identities = [
            endpoint.identity
            for section_key in self._graph_sections.section_keys(workflow)
            for endpoint in self.plan(workflow, section_key).image_endpoints
        ]
        unique_identities = tuple(dict.fromkeys(identities))
        return unique_identities[0] if len(unique_identities) == 1 else None

    def resolve_loaded_image_identity(
        self,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> LoadedInputCanvasImageIdentityResolution:
        """Resolve an admitted canvas image UUID to a workflow input node."""

        mapped_input_key = _input_key_for_image_id(workflow, image_id)
        if mapped_input_key is not None:
            parsed = _parse_input_key(mapped_input_key)
            if parsed is None:
                return LoadedInputCanvasImageIdentityResolution.rejected(
                    "malformed_input_key",
                    input_key=mapped_input_key,
                )
            cube_alias, image_node_name = parsed
            return LoadedInputCanvasImageIdentityResolution.mapped(
                cube_alias=cube_alias,
                image_node_name=image_node_name,
            )

        fallback_identity = self.unambiguous_image_identity(workflow)
        if fallback_identity is None:
            return LoadedInputCanvasImageIdentityResolution.rejected(
                "unmapped_image_id"
            )
        cube_alias, image_node_name = fallback_identity
        return LoadedInputCanvasImageIdentityResolution.mapped(
            cube_alias=cube_alias,
            image_node_name=image_node_name,
        )


def _input_key_for_image_id(workflow: WorkflowState, image_id: UUID) -> str | None:
    """Return the workflow input key currently mapped to image_id."""

    return next(
        (
            entry.input_key
            for entry in workflow.canvas.image_entries.values()
            if entry.image_id == image_id
        ),
        None,
    )


def _parse_input_key(input_key: str) -> tuple[str, str] | None:
    """Parse the durable graph-section/node Input image key."""

    cube_alias, separator, image_node_name = input_key.partition(":")
    if not cube_alias or separator != ":" or not image_node_name:
        return None
    return (cube_alias, image_node_name)


__all__ = ["InputCanvasBindingService"]
