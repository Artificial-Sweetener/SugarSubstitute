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

"""Verify graph-derived generation image selection for Input canvas surfaces."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.generation_input_image_selection_service import (
    GenerationInputImageSelectionService,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState


def test_selection_includes_authored_images_and_excludes_synthetic_surfaces() -> None:
    """Only graph image endpoints should become generation image products."""

    definitions = _DefinitionGateway()
    node_definitions = WorkflowNodeDefinitionService(definitions)
    plans = InputCanvasPlanService(
        node_definition_service=node_definitions,
        endpoint_service=InputAssetEndpointService(node_definitions),
    )
    graphs = WorkflowGraphSectionService()
    service = GenerationInputImageSelectionService(
        input_canvas_plan_service=plans,
        graph_section_service=graphs,
    )
    authored = _cube(
        "Authored",
        {
            "Image": {
                "class_type": "LoadImage",
                "inputs": {"image": "source.png"},
            },
            "Preview": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["Image", 0]},
            },
        },
    )
    regional = _cube(
        "Regional",
        {
            "Mask": {
                "class_type": "LoadImageMask",
                "inputs": {"image": "mask.png"},
            },
            "Latent": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 960, "height": 1344, "batch_size": 1},
            },
            "Sampler": {
                "class_type": "Sampler",
                "inputs": {
                    "region_masks": ["Mask", 0],
                    "latent_image": ["Latent", 0],
                },
            },
        },
    )
    workflow = WorkflowState(
        cubes={"Authored": authored, "Regional": regional},
        stack_order=["Authored", "Regional"],
    )
    authored_id = uuid4()
    synthetic_id = uuid4()
    authored_plan = plans.build_plan("Authored", authored.buffer)
    regional_plan = plans.build_plan("Regional", regional.buffer)
    workflow.canvas.bind_image(authored_plan.surfaces[0].input_key, authored_id)
    workflow.canvas.bind_image(regional_plan.surfaces[0].input_key, synthetic_id)

    selection = service.select(workflow)

    assert selection.is_valid
    assert selection.image_ids == (authored_id,)


def test_selection_rejects_canvas_entries_without_current_graph_authority() -> None:
    """Stale canvas state must fail closed instead of silently omitting an image."""

    definitions = WorkflowNodeDefinitionService(_DefinitionGateway())
    service = GenerationInputImageSelectionService(
        input_canvas_plan_service=InputCanvasPlanService(
            node_definition_service=definitions,
            endpoint_service=InputAssetEndpointService(definitions),
        ),
        graph_section_service=WorkflowGraphSectionService(),
    )
    cube = _cube(
        "Authored",
        {
            "Image": {
                "class_type": "LoadImage",
                "inputs": {"image": "source.png"},
            }
        },
    )
    workflow = WorkflowState(cubes={"Authored": cube}, stack_order=["Authored"])
    workflow.canvas.bind_image("Authored:RemovedImage", uuid4())

    selection = service.select(workflow)

    assert not selection.is_valid
    assert selection.image_ids == ()
    assert selection.unresolved_input_keys == ("Authored:RemovedImage",)


class _DefinitionGateway:
    """Provide deterministic live definitions for generation selection tests."""

    _definitions: dict[str, JsonObject] = {
        "LoadImage": {
            "input": {
                "required": {
                    "image": [
                        "STRING",
                        {"image_upload": True, "image_folder": "input"},
                    ]
                }
            },
            "output": ["IMAGE"],
        },
        "LoadImageMask": {
            "input": {
                "required": {
                    "image": [
                        "STRING",
                        {"image_upload": True, "image_folder": "input"},
                    ]
                }
            },
            "output": ["MASK"],
        },
        "PreviewImage": {
            "input": {"required": {"images": ["IMAGE", {}]}},
            "output": [],
        },
        "EmptyLatentImage": {
            "input": {
                "required": {
                    "width": ["INT", {}],
                    "height": ["INT", {}],
                    "batch_size": ["INT", {}],
                }
            },
            "output": ["LATENT"],
        },
        "Sampler": {
            "input": {
                "required": {
                    "region_masks": ["MASK", {}],
                    "latent_image": ["LATENT", {}],
                }
            },
            "output": ["LATENT"],
        },
    }

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return one cached definition."""

        return self._definitions.get(node_class, {})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return one required definition."""

        return self.get_node_definition(node_class)


def _cube(alias: str, nodes: dict[str, object]) -> CubeState:
    """Return one graph section with the supplied nodes."""

    return CubeState(
        cube_id=f"{alias}.cube",
        version="1",
        alias=alias,
        original_cube={},
        buffer={"nodes": nodes},
    )
