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

"""Verify synthetic canvas resolution-role projection from graph authority."""

from __future__ import annotations

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRoleService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)


def test_resolution_role_comes_only_from_graph_authority() -> None:
    """Resolve an editable dimension role only for graph-authorized spatial roots."""

    definitions = {
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
        "RegionalCondition": {
            "input": {"required": {"mask": ["MASK", {}]}},
            "output": ["CONDITIONING"],
        },
        "ArbitraryPackSpatialSource": {
            "input": {
                "required": {
                    "width": ["INT", {"min": 16, "step": 8}],
                    "height": ["INT", {"min": 16, "step": 8}],
                }
            },
            "output": ["LATENT"],
        },
        "Sampler": {
            "input": {
                "required": {
                    "latent_image": ["LATENT", {}],
                    "positive": ["CONDITIONING", {}],
                }
            },
            "output": ["LATENT"],
        },
    }
    graph = {
        "nodes": {
            "mask": {
                "class_type": "LoadImageMask",
                "inputs": {"image": "mask.png"},
            },
            "region": {
                "class_type": "RegionalCondition",
                "inputs": {"mask": ["mask", 0]},
            },
            "latent_root": {
                "class_type": "ArbitraryPackSpatialSource",
                "inputs": {"width": 1216, "height": 832},
            },
            "sampler": {
                "class_type": "Sampler",
                "inputs": {
                    "latent_image": ["latent_root", 0],
                    "positive": ["region", 0],
                },
            },
        }
    }
    definitions_service = WorkflowNodeDefinitionService()
    plans = InputCanvasPlanService(
        node_definition_service=definitions_service,
        endpoint_service=InputAssetEndpointService(definitions_service),
    )
    roles = SyntheticCanvasResolutionRoleService(plans)

    role = roles.resolve_for_node(
        section_key="renamed cube",
        graph=graph,
        node_name="latent_root",
        node_definitions=definitions,
    )

    assert role is not None
    assert role.section_key == "renamed cube"
    assert role.field_pair_for_node("latent_root") == ("width", "height")
    assert role.authority.dimensions.width == 1216
    assert role.authority.dimensions.height == 832
    assert (
        roles.resolve_for_node(
            section_key="renamed cube",
            graph=graph,
            node_name="sampler",
            node_definitions=definitions,
        )
        is None
    )
