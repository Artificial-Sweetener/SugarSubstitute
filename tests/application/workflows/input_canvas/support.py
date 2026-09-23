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

"""Build deterministic workflow Input-canvas scenarios."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_asset_service import WorkflowAssetService
from substitute.application.workflows.input_mask_materialization_service import (
    InputMaskMaterializationService,
)
from substitute.application.workflows.ordered_mask_materialization_service import (
    OrderedMaskMaterializationService,
)
from substitute.application.workflows.input_mask_binding_materialization_service import (
    InputMaskBindingMaterializationService,
)
from substitute.application.workflows.synthetic_input_canvas_surface_service import (
    SyntheticInputCanvasSurfaceService,
)
from substitute.application.workflows.input_mask_selection_service import (
    InputMaskSelectionService,
)
from substitute.application.workflows.input_image_materialization_service import (
    InputImageMaterializationService,
)
from substitute.application.workflows.input_section_materialization_service import (
    InputSectionMaterializationService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.ordered_mask_region_authoring_service import (
    OrderedMaskRegionAuthoringService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState

from tests.application.workflows.input_canvas.fakes import (
    _DefinitionGateway,
    _FakeInputCanvasStateService,
    _FakeCanvasIoService,
)


def _build_workflow(mask_path: str) -> WorkflowState:
    """Build one workflow with a single editable image-mask binding."""

    workflow = WorkflowState()
    workflow.cubes["CubeA"] = CubeState(
        cube_id="CubeA",
        version="1.0.0",
        alias="CubeA",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "input_image": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "E:/images/input.png"},
                },
                "input_mask": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": mask_path},
                },
                "consumer": {
                    "class_type": "Blend",
                    "inputs": {
                        "image": ["input_image", 0],
                        "mask": ["input_mask", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("CubeA")
    return workflow


def _mask_buffer_path(workflow: WorkflowState) -> str:
    """Return the editable mask image input from a single-cube test workflow."""

    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    input_mask_node = nodes["input_mask"]
    assert isinstance(input_mask_node, dict)
    input_values = input_mask_node["inputs"]
    assert isinstance(input_values, dict)
    value = input_values["image"]
    assert isinstance(value, str)
    return value


def _image_buffer_path(workflow: WorkflowState) -> str:
    """Return the editable image input from a single-cube test workflow."""

    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    input_image_node = nodes["input_image"]
    assert isinstance(input_image_node, dict)
    input_values = input_image_node["inputs"]
    assert isinstance(input_values, dict)
    value = input_values["image"]
    assert isinstance(value, str)
    return value


def _mask_asset_payload(workflow: WorkflowState) -> JsonObject:
    """Return the persisted input-mask asset payload from a test workflow."""

    asset_refs = cast(JsonObject, workflow.metadata["asset_refs"])
    input_masks = cast(JsonObject, asset_refs["input_masks"])
    return cast(JsonObject, input_masks["CubeA:input_mask"])


def _image_materialization_service(
    input_canvas_state_service: _FakeInputCanvasStateService,
    canvas_io_service: _FakeCanvasIoService,
    *,
    definitions: Mapping[str, JsonObject] | None = None,
    workflow_asset_service: Any | None = None,
    graph_section_service: WorkflowGraphSectionService | None = None,
) -> InputImageMaterializationService:
    """Build the input-image materialization service with standard collaborators."""

    return _input_canvas_services(
        input_canvas_state_service,
        canvas_io_service,
        definitions=definitions,
        workflow_asset_service=workflow_asset_service,
        graph_section_service=graph_section_service,
    ).images


def _section_materialization_service(
    input_canvas_state_service: _FakeInputCanvasStateService,
    canvas_io_service: _FakeCanvasIoService,
    *,
    definitions: Mapping[str, JsonObject] | None = None,
    workflow_asset_service: Any | None = None,
    graph_section_service: WorkflowGraphSectionService | None = None,
) -> InputSectionMaterializationService:
    """Build the graph-section materializer with standard collaborators."""

    return _input_canvas_services(
        input_canvas_state_service,
        canvas_io_service,
        definitions=definitions,
        workflow_asset_service=workflow_asset_service,
        graph_section_service=graph_section_service,
    ).sections


@dataclass(frozen=True)
class _InputCanvasServices:
    """Hold focused Input application owners used by workflow tests."""

    images: InputImageMaterializationService
    sections: InputSectionMaterializationService
    mask_selection: InputMaskSelectionService
    regions: OrderedMaskRegionAuthoringService


def _input_canvas_services(
    state: _FakeInputCanvasStateService,
    canvas_io: _FakeCanvasIoService,
    *,
    definitions: Mapping[str, JsonObject] | None = None,
    workflow_asset_service: Any | None = None,
    graph_section_service: WorkflowGraphSectionService | None = None,
) -> _InputCanvasServices:
    """Compose focused Input workflow owners around deterministic fakes."""

    graph_sections = graph_section_service or WorkflowGraphSectionService()
    bindings = InputCanvasBindingService(
        plans=_input_canvas_plan_service(definitions),
        graph_sections=graph_sections,
    )
    assets = workflow_asset_service or WorkflowAssetService(graph_sections)
    owner = cast(Any, state)
    scalar_masks = InputMaskMaterializationService(
        input_masks=owner,
        canvas_io_service=canvas_io,
        workflow_asset_service=assets,
        graph_section_service=graph_sections,
    )
    ordered_masks = OrderedMaskMaterializationService(
        input_masks=owner,
        mask_visuals=owner,
        canvas_io_service=canvas_io,
        graph_section_service=graph_sections,
    )
    mask_materialization = InputMaskBindingMaterializationService(
        scalar_service=scalar_masks,
        ordered_service=ordered_masks,
    )
    synthetic_surfaces = SyntheticInputCanvasSurfaceService(
        input_images=owner,
        input_cleanup=owner,
        canvas_io_service=canvas_io,
    )
    images = InputImageMaterializationService(
        bindings=bindings,
        images=owner,
        canvas_io=canvas_io,
        mask_materialization=mask_materialization,
        workflow_assets=assets,
        graph_sections=graph_sections,
    )
    sections = InputSectionMaterializationService(
        bindings=bindings,
        images=images,
        mask_materialization=mask_materialization,
        synthetic_surfaces=synthetic_surfaces,
        graph_sections=graph_sections,
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
        input_routes=owner,
        input_images=owner,
        input_masks=owner,
        canvas_io_service=canvas_io,
        materialization_service=ordered_masks,
        graph_values=OrderedMaskGraphValueService(graph_sections),
    )
    return _InputCanvasServices(
        images=images,
        sections=sections,
        mask_selection=InputMaskSelectionService(
            bindings=bindings,
            images=owner,
            masks=owner,
            canvas_io=canvas_io,
            workflow_assets=assets,
            graph_sections=graph_sections,
            synthetic_surfaces=synthetic_surfaces,
            mask_materialization=mask_materialization,
        ),
        regions=regions,
    )


def _input_canvas_plan_service(
    definitions: Mapping[str, JsonObject] | None = None,
) -> InputCanvasPlanService:
    """Build one definition-backed Input canvas planner for service tests."""

    definition_service = WorkflowNodeDefinitionService(
        _DefinitionGateway(definitions or {})
    )
    return InputCanvasPlanService(
        node_definition_service=definition_service,
        endpoint_service=InputAssetEndpointService(definition_service),
    )


def _input_canvas_binding_service(
    definitions: Mapping[str, JsonObject] | None = None,
) -> InputCanvasBindingService:
    """Build graph-backed Input canvas binding queries for service tests."""

    return InputCanvasBindingService(
        plans=_input_canvas_plan_service(definitions),
        graph_sections=WorkflowGraphSectionService(),
    )
