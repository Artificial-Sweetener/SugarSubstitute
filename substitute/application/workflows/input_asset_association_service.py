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

"""Own graph-backed Input image and mask asset associations."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.input_canvas_ports import (
    WorkflowAssetServicePort,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.domain.workflow import (
    InputAssetCardinality,
    ProjectMaskAssetRef,
    WorkflowAssetRef,
    WorkflowState,
)


class InputAssetAssociationService:
    """Own Input graph asset mutation, lookup, and project path resolution."""

    def __init__(
        self,
        *,
        bindings: InputCanvasBindingService,
        assets: WorkflowAssetServicePort,
        ordered_graph_values: OrderedMaskGraphValueService,
    ) -> None:
        """Store binding, asset persistence, and ordered-value owners."""

        self._bindings = bindings
        self._assets = assets
        self._ordered_graph_values = ordered_graph_values

    def associate_project_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Persist a project mask through its discovered upload field."""

        binding = self._bindings.binding_for_mask(workflow, section_key, node_name)
        if binding is None:
            return False
        return self._assets.associate_project_input_mask(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=binding.mask_field_key,
            relative_path=relative_path,
        )

    def associate_project_ordered_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        region_id: UUID,
        relative_path: Path | str,
    ) -> bool:
        """Associate a project mask with one ordered region and graph value."""

        binding = self._bindings.binding_for_mask(workflow, section_key, node_name)
        if (
            binding is None
            or binding.mask_endpoint.cardinality is not InputAssetCardinality.ORDERED
        ):
            return False
        collection = workflow.canvas.regional_mask_collection(binding.association_key)
        if collection is None or collection.entry(region_id) is None:
            return False
        collection.bind_asset(
            region_id,
            ProjectMaskAssetRef(Path(relative_path).as_posix()),
        )
        self._ordered_graph_values.synchronize(workflow, binding, collection)
        return True

    def input_image_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return an image asset through its discovered upload field."""

        endpoint = self._bindings.plan(workflow, section_key).image_endpoint_for_node(
            node_name
        )
        if endpoint is None:
            return None
        return self._assets.input_image_asset_ref(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=endpoint.field_key,
        )

    def input_mask_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return a mask asset through its discovered upload field."""

        binding = self._bindings.binding_for_mask(workflow, section_key, node_name)
        if binding is None:
            return None
        return self._assets.input_mask_asset_ref(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=binding.mask_field_key,
        )

    def resolve_input_mask_path(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
        section_key: str,
        node_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve a mask asset through its discovered upload field."""

        binding = self._bindings.binding_for_mask(workflow, section_key, node_name)
        if binding is None:
            return None
        return self._assets.resolve_input_mask_path(
            workflow,
            workflow_name=workflow_name,
            section_key=section_key,
            node_name=node_name,
            field_key=binding.mask_field_key,
            projects_dir=projects_dir,
        )


__all__ = ["InputAssetAssociationService"]
