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

"""Verify ordered mask restoration before live Comfy definitions are available."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.restored_ordered_mask_collection_service import (
    RestoredOrderedMaskCollectionService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, ProjectMaskAssetRef, WorkflowState


def test_restore_projects_durable_mask_list_without_live_definitions() -> None:
    """A stale scalar graph value must recover from the durable collection directly."""

    graph: JsonObject = {
        "nodes": {
            "load_mask_batch": {
                "class_type": "SimpleSyrup.LoadMaskBatch",
                "inputs": {"image": "stale-single-mask.png", "channel": "red"},
            },
            "consumer": {
                "class_type": "RegionalSampler",
                "inputs": {"masks": ["load_mask_batch", 0]},
            },
        }
    }
    workflow = WorkflowState(
        cubes={
            "Region": CubeState(
                cube_id="Prompt by Region.cube",
                version="3.2.0",
                alias="Region",
                original_cube=graph,
                buffer=graph,
            )
        },
        stack_order=["Region"],
    )
    collection = workflow.canvas.ensure_regional_mask_collection(
        ("Region", "load_mask_batch")
    )
    image_id = uuid4()
    collection.add_region(image_id, asset_ref=ProjectMaskAssetRef("first.png"))
    collection.add_region(image_id, asset_ref=ProjectMaskAssetRef("second.png"))
    graph_sections = WorkflowGraphSectionService()
    service = RestoredOrderedMaskCollectionService(
        endpoint_service=InputAssetEndpointService(WorkflowNodeDefinitionService()),
        graph_sections=graph_sections,
        graph_values=OrderedMaskGraphValueService(graph_sections),
    )

    repaired = service.reconcile({"workflow": workflow})

    assert repaired == 1
    assert graph_sections.input_value(
        workflow,
        section_key="Region",
        node_name="load_mask_batch",
        field_key="image",
    ) == ["first.png", "second.png"]
