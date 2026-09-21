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

"""Own authored graph values derived from ordered regional mask collections."""

from __future__ import annotations

from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    InputAssetEndpoint,
    InputCanvasMaskBinding,
    ProjectMaskAssetRef,
    RegionalMaskCollection,
    WorkflowState,
)


class OrderedMaskGraphValueService:
    """Project exact regional collection order into its authored graph field."""

    def __init__(self, graph_sections: WorkflowGraphSectionService) -> None:
        """Bind the authoritative graph section mutation owner."""

        self._graph_sections = graph_sections

    def synchronize(
        self,
        workflow: WorkflowState,
        binding: InputCanvasMaskBinding,
        collection: RegionalMaskCollection,
    ) -> bool:
        """Write every durable regional asset and report authoritative mutation."""

        return self._synchronize(
            workflow,
            section_key=binding.section_key,
            node_name=binding.mask_node_name,
            field_key=binding.mask_field_key,
            collection=collection,
        )

    def synchronize_endpoint(
        self,
        workflow: WorkflowState,
        endpoint: InputAssetEndpoint,
        collection: RegionalMaskCollection,
    ) -> bool:
        """Project a collection and report whether its graph owner was available."""

        return self._synchronize(
            workflow,
            section_key=endpoint.section_key,
            node_name=endpoint.node_name,
            field_key=endpoint.field_key,
            collection=collection,
        )

    def _synchronize(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
        collection: RegionalMaskCollection,
    ) -> bool:
        """Write one collection projection to an explicitly owned graph field."""

        values = [
            entry.asset_ref.relative_path
            for entry in collection.entries
            if isinstance(entry.asset_ref, ProjectMaskAssetRef)
        ]
        mutation = self._graph_sections.set_input_value(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=field_key,
            value=values,
        )
        return mutation.changed


__all__ = ["OrderedMaskGraphValueService"]
