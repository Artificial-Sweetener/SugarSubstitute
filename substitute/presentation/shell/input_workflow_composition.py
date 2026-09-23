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

"""Compose graph-backed Input workflow application owners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.input_asset_association_service import (
    InputAssetAssociationService,
)
from substitute.application.workflows.input_image_materialization_service import (
    InputImageMaterializationService,
)
from substitute.application.workflows.input_mask_binding_materialization_service import (
    InputMaskBindingMaterializationService,
)
from substitute.application.workflows.input_mask_materialization_service import (
    InputMaskMaterializationService,
)
from substitute.application.workflows.input_mask_selection_service import (
    InputMaskSelectionService,
)
from substitute.application.workflows.input_section_materialization_service import (
    InputSectionMaterializationService,
)
from substitute.application.workflows.ordered_mask_materialization_service import (
    OrderedMaskMaterializationService,
)
from substitute.application.workflows.ordered_mask_region_authoring_service import (
    OrderedMaskRegionAuthoringService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.restored_ordered_mask_collection_service import (
    RestoredOrderedMaskCollectionService,
)
from substitute.application.workflows.synthetic_input_canvas_surface_service import (
    SyntheticInputCanvasSurfaceService,
)
from substitute.application.workflows.workflow_input_canvas_duplication_service import (
    WorkflowInputCanvasDuplicationService,
)


@dataclass(frozen=True)
class InputWorkflowComposition:
    """Hold graph-backed Input workflow owners."""

    bindings: InputCanvasBindingService
    assets: InputAssetAssociationService
    mask_selection: InputMaskSelectionService
    regions: OrderedMaskRegionAuthoringService
    images: InputImageMaterializationService
    sections: InputSectionMaterializationService
    duplication: WorkflowInputCanvasDuplicationService
    restored_masks: RestoredOrderedMaskCollectionService


def compose_input_workflow_services(
    *,
    shell: Any,
    input_document: Any,
) -> InputWorkflowComposition:
    """Compose Input binding, materialization, duplication, and restore owners."""

    bindings = InputCanvasBindingService(
        plans=shell.input_canvas_plan_service,
        graph_sections=shell.graph_section_service,
    )
    ordered_graph_values = OrderedMaskGraphValueService(shell.graph_section_service)
    assets = InputAssetAssociationService(
        bindings=bindings,
        assets=shell.workflow_asset_service,
        ordered_graph_values=ordered_graph_values,
    )
    scalar_masks = InputMaskMaterializationService(
        input_masks=shell.input_mask_assets,
        canvas_io_service=shell.canvas_io_service,
        workflow_asset_service=shell.workflow_asset_service,
        graph_section_service=shell.graph_section_service,
    )
    ordered_masks = OrderedMaskMaterializationService(
        input_masks=shell.input_mask_assets,
        mask_visuals=shell.input_mask_visuals,
        canvas_io_service=shell.canvas_io_service,
        graph_section_service=shell.graph_section_service,
    )
    mask_materialization = InputMaskBindingMaterializationService(
        scalar_service=scalar_masks,
        ordered_service=ordered_masks,
    )
    synthetic_surfaces = SyntheticInputCanvasSurfaceService(
        input_images=shell.input_image_assets,
        input_cleanup=shell.input_asset_cleanup,
        canvas_io_service=shell.canvas_io_service,
    )
    images = InputImageMaterializationService(
        bindings=bindings,
        images=shell.input_image_assets,
        canvas_io=shell.canvas_io_service,
        mask_materialization=mask_materialization,
        workflow_assets=shell.workflow_asset_service,
        graph_sections=shell.graph_section_service,
    )
    sections = InputSectionMaterializationService(
        bindings=bindings,
        images=images,
        mask_materialization=mask_materialization,
        synthetic_surfaces=synthetic_surfaces,
        graph_sections=shell.graph_section_service,
    )
    mask_selection = InputMaskSelectionService(
        bindings=bindings,
        images=shell.input_image_assets,
        masks=shell.input_mask_assets,
        canvas_io=shell.canvas_io_service,
        workflow_assets=shell.workflow_asset_service,
        graph_sections=shell.graph_section_service,
        synthetic_surfaces=synthetic_surfaces,
        mask_materialization=mask_materialization,
    )
    regions = OrderedMaskRegionAuthoringService(
        binding_resolver=bindings.binding_for_mask,
        ensure_section_materialized=lambda workflow, workflow_id, section_key, workflow_name, projects_dir: (
            sections.materialize_loaded_section(
                workflows={workflow_id: workflow},
                workflow_id=workflow_id,
                section_key=section_key,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
        ),
        input_routes=shell.input_routes,
        input_images=shell.input_image_assets,
        input_masks=shell.input_mask_assets,
        canvas_io_service=shell.canvas_io_service,
        materialization_service=ordered_masks,
        graph_values=ordered_graph_values,
    )
    duplication = WorkflowInputCanvasDuplicationService(
        input_bindings=bindings,
        graph_sections=shell.graph_section_service,
        input_document=input_document,
        canvas_io=shell.canvas_io_service,
    )
    restored_masks = RestoredOrderedMaskCollectionService(
        endpoint_service=shell.input_asset_endpoint_service,
        graph_sections=shell.graph_section_service,
        graph_values=ordered_graph_values,
    )
    return InputWorkflowComposition(
        bindings=bindings,
        assets=assets,
        mask_selection=mask_selection,
        regions=regions,
        images=images,
        sections=sections,
        duplication=duplication,
        restored_masks=restored_masks,
    )


__all__ = ["InputWorkflowComposition", "compose_input_workflow_services"]
