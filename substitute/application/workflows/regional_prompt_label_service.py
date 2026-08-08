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

"""Resolve ordered regional mask labels from topology-related prompt separators."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopologyService,
    prompt_text,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import WorkflowState


class RegionalPromptLabelService:
    """Map ordered mask positions to authored names from related SEP tokens."""

    def __init__(
        self,
        *,
        graph_sections: WorkflowGraphSectionService | None = None,
        topology: RegionalPromptTopologyService | None = None,
        prompt_documents: PromptDocumentProjector | None = None,
    ) -> None:
        """Store graph, relationship, and canonical prompt parsing authorities."""

        self._graph_sections = graph_sections or WorkflowGraphSectionService()
        self._topology = topology or RegionalPromptTopologyService(self._graph_sections)
        self._prompt_documents = prompt_documents or PromptDocumentProjector()

    def labels_for_mask(
        self,
        workflow: WorkflowState,
        association_key: MaskAssociationKey,
        *,
        region_count: int,
        prompt_text_overrides: Mapping[str, str] | None = None,
    ) -> tuple[str | None, ...]:
        """Return first-authored SEP names in topology prompt order."""

        if region_count < 0:
            raise ValueError("region_count must not be negative")
        labels: list[str | None] = [None] * region_count
        topology = self._topology.topology_for_mask(workflow, association_key)
        if topology is None:
            return tuple(labels)
        graph = self._graph_sections.graph(workflow, association_key[0])
        if graph is None:
            return tuple(labels)
        overrides = prompt_text_overrides or {}
        for node_name in topology.prompt_node_names:
            text = overrides.get(node_name)
            if text is None:
                text = prompt_text(graph, node_name)
            if text is None:
                continue
            separators = self._prompt_documents.build_document_view(
                text
            ).region_structure.separators
            for index, separator in enumerate(separators[:region_count]):
                authored_name = (
                    None if separator.name is None else separator.name.strip()
                )
                if labels[index] is None and authored_name:
                    labels[index] = authored_name
        return tuple(labels)


__all__ = ["RegionalPromptLabelService"]
