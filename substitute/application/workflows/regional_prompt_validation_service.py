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

"""Validate positional prompt-to-mask associations discovered from graph topology."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopologyService,
    prompt_text,
)
from substitute.domain.prompt.document.parser import parse_prompt_document
from substitute.domain.workflow import WorkflowState


@dataclass(frozen=True, slots=True)
class RegionalPromptValidationIssue:
    """Describe a prompt region that lacks an authored mask association."""

    association_key: tuple[str, str]
    required_region_count: int
    available_mask_count: int


class RegionalPromptValidationService:
    """Compare topology-related prompt partitions with ordered mask collections."""

    def __init__(
        self,
        graph_sections: WorkflowGraphSectionService | None = None,
    ) -> None:
        """Store the graph-section authority used for topology discovery."""

        self._graph_sections = graph_sections or WorkflowGraphSectionService()
        self._topology = RegionalPromptTopologyService(self._graph_sections)

    def validate(
        self,
        workflow: WorkflowState,
    ) -> tuple[RegionalPromptValidationIssue, ...]:
        """Return every ordered endpoint with fewer masks than prompt regions."""

        issues: list[RegionalPromptValidationIssue] = []
        for topology in self._topology.topologies(workflow):
            association_key = topology.association_key
            collection = workflow.canvas.regional_mask_collections[association_key]
            section_key, mask_node_name = association_key
            graph = self._graph_sections.graph(workflow, section_key)
            if graph is None:
                continue
            required_region_count = max(
                (
                    len(parse_prompt_document(text).region_structure.separators)
                    for prompt_node_name in topology.prompt_node_names
                    if (text := prompt_text(graph, prompt_node_name)) is not None
                ),
                default=0,
            )
            available_mask_count = sum(
                entry.mask_id is not None and entry.asset_ref is not None
                for entry in collection.entries
            )
            if required_region_count > available_mask_count:
                issues.append(
                    RegionalPromptValidationIssue(
                        association_key=association_key,
                        required_region_count=required_region_count,
                        available_mask_count=available_mask_count,
                    )
                )
        return tuple(issues)


__all__ = ["RegionalPromptValidationIssue", "RegionalPromptValidationService"]
