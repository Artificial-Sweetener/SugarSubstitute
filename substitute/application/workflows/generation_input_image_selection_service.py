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

"""Select graph-authored Input images that require generation products."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    InputCanvasPlan,
    InputCanvasSurfaceKind,
    WorkflowState,
)


@dataclass(frozen=True, slots=True)
class GenerationInputImageSelection:
    """Describe authored image products and canvas entries that could not resolve."""

    image_ids: tuple[UUID, ...]
    unresolved_input_keys: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether every persisted canvas entry still has graph authority."""

        return not self.unresolved_input_keys


class GenerationInputImageSelectionService:
    """Derive generation image products from the authoritative Input canvas plan."""

    def __init__(
        self,
        *,
        input_canvas_plan_service: InputCanvasPlanService,
        graph_section_service: WorkflowGraphSectionService,
    ) -> None:
        """Bind the shared graph and canvas-plan authorities."""

        self._plans = input_canvas_plan_service
        self._graphs = graph_section_service

    def select(self, workflow: WorkflowState) -> GenerationInputImageSelection:
        """Select authored image identities while excluding synthetic surfaces."""

        plans_by_section: dict[str, InputCanvasPlan] = {}
        selected: list[UUID] = []
        unresolved: list[str] = []
        for entry in sorted(
            workflow.canvas.image_entries.values(),
            key=lambda candidate: candidate.input_key,
        ):
            identity = self._parse_input_key(entry.input_key)
            if identity is None:
                unresolved.append(entry.input_key)
                continue
            section_key, surface_key = identity
            plan = plans_by_section.get(section_key)
            if plan is None:
                graph = self._graphs.graph(workflow, section_key)
                if graph is None:
                    unresolved.append(entry.input_key)
                    continue
                plan = self._plans.build_plan(section_key, graph)
                plans_by_section[section_key] = plan
            surface = plan.surface_for_key(surface_key)
            if surface is None:
                unresolved.append(entry.input_key)
                continue
            if surface.kind is InputCanvasSurfaceKind.AUTHORED_IMAGE:
                selected.append(entry.image_id)
        return GenerationInputImageSelection(
            image_ids=tuple(dict.fromkeys(selected)),
            unresolved_input_keys=tuple(unresolved),
        )

    @staticmethod
    def _parse_input_key(input_key: str) -> tuple[str, str] | None:
        """Parse one durable section and canvas-surface identity."""

        section_key, separator, surface_key = input_key.partition(":")
        if separator and section_key and surface_key:
            return section_key, surface_key
        return None


__all__ = [
    "GenerationInputImageSelection",
    "GenerationInputImageSelectionService",
]
