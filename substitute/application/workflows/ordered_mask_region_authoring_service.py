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

"""Own first-use and append behavior for ordered regional mask authoring."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from substitute.application.workflows.input_canvas_ports import (
    CanvasIoServicePort,
    InputCanvasStateServicePort,
)
from substitute.application.workflows.ordered_mask_materialization_service import (
    OrderedMaskMaterializationService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.domain.workflow import (
    InputAssetCardinality,
    ProjectMaskAssetRef,
    WorkflowState,
)
from substitute.domain.workflow.input_canvas_plan import InputCanvasMaskBinding


OrderedMaskBindingResolver = Callable[
    [WorkflowState, str, str], InputCanvasMaskBinding | None
]
EnsureInputSectionMaterialized = Callable[[WorkflowState, str, str, str, Path], object]


class OrderedMaskRegionAuthoringService:
    """Create the first synthetic region or append to an existing collection."""

    def __init__(
        self,
        *,
        binding_resolver: OrderedMaskBindingResolver,
        ensure_section_materialized: EnsureInputSectionMaterialized,
        input_canvas_state_service: InputCanvasStateServicePort,
        canvas_io_service: CanvasIoServicePort,
        materialization_service: OrderedMaskMaterializationService,
        graph_values: OrderedMaskGraphValueService,
    ) -> None:
        """Store topology, materialization, canvas, and IO owners."""

        self._binding_resolver = binding_resolver
        self._ensure_section_materialized = ensure_section_materialized
        self._input_canvas_state_service = input_canvas_state_service
        self._canvas_io_service = canvas_io_service
        self._materialization_service = materialization_service
        self._graph_values = graph_values

    def add_region(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        section_key: str,
        node_name: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> UUID | None:
        """Materialize first use or append and activate one blank region."""

        binding = self._ordered_binding(workflow, section_key, node_name)
        if binding is None:
            return None
        image_entry = workflow.canvas.image_entry(
            f"{binding.section_key}:{binding.surface_key}"
        )
        if image_entry is None:
            self._ensure_section_materialized(
                workflow,
                workflow_id,
                section_key,
                workflow_name,
                projects_dir,
            )
            image_entry = workflow.canvas.image_entry(
                f"{binding.section_key}:{binding.surface_key}"
            )
            collection = workflow.canvas.regional_mask_collection(
                binding.association_key
            )
            if image_entry is None or collection is None:
                return None
            selected = (
                collection.entry(collection.selected_region_id)
                if collection.selected_region_id is not None
                else None
            )
            if selected is None or selected.mask_id is None:
                return None
            self._input_canvas_state_service.set_active_workflow_mask(
                workflow_id,
                workflow,
                selected.mask_id,
            )
            return selected.mask_id

        image_path = self._input_canvas_state_service.input_image_path(
            image_entry.image_id
        )
        if image_path is None:
            return None
        image = self._canvas_io_service.load_input_image(image_path)
        if image is None:
            return None
        collection = workflow.canvas.ensure_regional_mask_collection(
            binding.association_key
        )
        region = collection.add_region(image_entry.image_id)
        results = self._materialization_service.materialize(
            workflow=workflow,
            workflow_id=workflow_id,
            binding=binding,
            image_id=image_entry.image_id,
            image=image,
            associated_image_path=image_path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        materialized = collection.entry(region.region_id)
        if materialized is None or materialized.mask_id is None:
            collection.remove(region.region_id)
            return None
        self._input_canvas_state_service.set_active_workflow_mask(
            workflow_id,
            workflow,
            materialized.mask_id,
        )
        return materialized.mask_id if results else None

    def import_region(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        section_key: str,
        node_name: str,
        source_path: Path,
        workflow_name: str,
        projects_dir: Path,
    ) -> UUID | None:
        """Append one imported mask normalized to the synthetic canvas dimensions."""

        if not source_path.is_file():
            return None
        mask_id = self.add_region(
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=section_key,
            node_name=node_name,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        binding = self._ordered_binding(workflow, section_key, node_name)
        if mask_id is None or binding is None:
            return None
        collection = workflow.canvas.regional_mask_collection(binding.association_key)
        entry = None if collection is None else collection.entry_for_mask(mask_id)
        image_entry = workflow.canvas.image_entry(
            f"{binding.section_key}:{binding.surface_key}"
        )
        if (
            collection is None
            or entry is None
            or image_entry is None
            or not isinstance(entry.asset_ref, ProjectMaskAssetRef)
        ):
            return None
        image_path = self._input_canvas_state_service.input_image_path(
            image_entry.image_id
        )
        dimensions = (
            None
            if image_path is None
            else self._canvas_io_service.image_dimensions(image_path)
        )
        if dimensions is None:
            self.remove_region(
                workflow=workflow,
                workflow_id=workflow_id,
                section_key=section_key,
                node_name=node_name,
                region_index=collection.entries.index(entry),
            )
            return None
        destination = self._canvas_io_service.resolve_mask_path(
            workflow_name=workflow_name,
            path_from_buffer=entry.asset_ref.relative_path,
            projects_dir=projects_dir,
        )
        normalized = self._canvas_io_service.save_resampled_mask(
            source_path,
            destination,
            width=dimensions[0],
            height=dimensions[1],
        )
        updated = normalized and self._input_canvas_state_service.update_mask_from_file(
            workflow_id,
            workflow,
            binding.association_key,
            image_entry.image_id,
            mask_id,
            destination,
            dimensions,
            dimensions,
        )
        if not updated:
            self.remove_region(
                workflow=workflow,
                workflow_id=workflow_id,
                section_key=section_key,
                node_name=node_name,
                region_index=collection.entries.index(entry),
            )
            return None
        return mask_id

    def remove_region(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        section_key: str,
        node_name: str,
        region_index: int,
    ) -> bool:
        """Remove one ordered region, its canvas layer, and its Comfy list item."""

        binding = self._ordered_binding(workflow, section_key, node_name)
        if binding is None:
            return False
        collection = workflow.canvas.regional_mask_collection(binding.association_key)
        if collection is None or not 0 <= region_index < len(collection.entries):
            return False
        entry = collection.entries[region_index]
        if (
            entry.mask_id is not None
            and not self._input_canvas_state_service.remove_workflow_mask_layer(
                workflow_id,
                workflow,
                entry.image_id,
                entry.mask_id,
            )
        ):
            return False
        collection.remove(entry.region_id)
        self._graph_values.synchronize(
            workflow,
            binding,
            collection,
        )
        selected = (
            collection.entry(collection.selected_region_id)
            if collection.selected_region_id is not None
            else None
        )
        if selected is not None and selected.mask_id is not None:
            self._input_canvas_state_service.set_active_workflow_mask(
                workflow_id,
                workflow,
                selected.mask_id,
            )
        return True

    def _ordered_binding(
        self,
        workflow: WorkflowState,
        section_key: str,
        node_name: str,
    ) -> InputCanvasMaskBinding | None:
        """Return only a topology-resolved ordered mask binding."""

        binding = self._binding_resolver(workflow, section_key, node_name)
        if (
            binding is None
            or binding.mask_endpoint.cardinality is not InputAssetCardinality.ORDERED
        ):
            return None
        return binding


__all__ = ["OrderedMaskRegionAuthoringService"]
