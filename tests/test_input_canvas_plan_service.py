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

"""Verify unified authored and synthetic Input canvas planning semantics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.workflow import InputCanvasSurfaceKind


def test_custom_named_spatial_root_creates_mask_only_canvas() -> None:
    """Class-independent latent roots should establish a synthetic mask surface."""

    graph = _regional_graph(
        root_class="PackSpecificNoiseFactory",
        width=1024,
        height=768,
    )
    definitions = _regional_definitions("PackSpecificNoiseFactory")

    plan = _service().build_plan("cube", graph, node_definitions=definitions)

    assert len(plan.surfaces) == 1
    surface = plan.surfaces[0]
    assert surface.kind is InputCanvasSurfaceKind.SYNTHETIC
    assert surface.dimensions is not None
    assert (surface.dimensions.width, surface.dimensions.height) == (1024, 768)
    assert surface.dimension_authority is not None
    assert surface.dimension_authority.node_names == ("latent_root",)
    assert [binding.mask_endpoint.node_name for binding in plan.mask_bindings] == [
        "mask"
    ]
    assert plan.rejected_mask_nodes == ()


def test_spatial_transformer_dimensions_do_not_create_canvas_authority() -> None:
    """Detailer tile dimensions must not replace an upstream spatial authority."""

    definitions = _base_definitions()
    definitions.update(
        {
            "OpaqueLatentSource": {
                "input": {"required": {}},
                "output": ["LATENT"],
            },
            "PackDetailer": {
                "input": {
                    "required": {
                        "latent": ["LATENT", {}],
                        "conditioning": ["CONDITIONING", {}],
                        "tile_width": ["INT", {}],
                        "tile_height": ["INT", {}],
                    }
                },
                "output": ["LATENT"],
            },
        }
    )
    graph = _graph(
        {
            "mask": _mask_node(),
            "region": _node("RegionalCondition", mask=["mask", 0]),
            "opaque": _node("OpaqueLatentSource"),
            "detailer": _node(
                "PackDetailer",
                latent=["opaque", 0],
                conditioning=["region", 0],
                tile_width=512,
                tile_height=512,
            ),
        }
    )

    plan = _service().build_plan("cube", graph, node_definitions=definitions)

    assert plan.surfaces == ()
    assert plan.mask_bindings == ()
    assert plan.rejected_mask_nodes == ("mask",)
    assert plan.rejections[0].reason == "no_relevant_spatial_root_with_dimensions"


@pytest.mark.parametrize(
    ("transform_class", "carrier_type"),
    (
        ("CustomImageCrop", "IMAGE"),
        ("CustomLatentResize", "LATENT"),
        ("CustomLatentUpscale", "LATENT"),
    ),
)
def test_spatial_crop_resize_and_upscale_nodes_are_not_dimension_roots(
    transform_class: str,
    carrier_type: str,
) -> None:
    """Spatial transforms must not authorize a new canvas from target dimensions."""

    definitions = _base_definitions()
    definitions.update(
        {
            "OpaqueSpatialSource": {
                "input": {"required": {}},
                "output": [carrier_type],
            },
            transform_class: {
                "input": {
                    "required": {
                        "spatial": [carrier_type, {}],
                        "conditioning": ["CONDITIONING", {}],
                        "target_width": ["INT", {}],
                        "target_height": ["INT", {}],
                    }
                },
                "output": [carrier_type],
            },
        }
    )
    graph = _graph(
        {
            "mask": _mask_node(),
            "region": _node("RegionalCondition", mask=["mask", 0]),
            "source": _node("OpaqueSpatialSource"),
            "transform": _node(
                transform_class,
                spatial=["source", 0],
                conditioning=["region", 0],
                target_width=512,
                target_height=512,
            ),
        }
    )

    plan = _service().build_plan("workflow", graph, node_definitions=definitions)

    assert plan.surfaces == ()
    assert plan.rejected_mask_nodes == ("mask",)


def test_conflicting_relevant_spatial_roots_fail_closed() -> None:
    """Mask-only canvases should remain unavailable when relevant roots disagree."""

    definitions = _base_definitions()
    definitions.update(
        {
            "RootA": _latent_root_definition(),
            "RootB": _latent_root_definition(),
            "LatentConditionMerge": {
                "input": {
                    "required": {
                        "first": ["LATENT", {}],
                        "second": ["LATENT", {}],
                        "conditioning": ["CONDITIONING", {}],
                    }
                },
                "output": ["LATENT"],
            },
        }
    )
    graph = _graph(
        {
            "mask": _mask_node(),
            "region": _node("RegionalCondition", mask=["mask", 0]),
            "large": _node("RootA", width=1024, height=1024),
            "small": _node("RootB", width=512, height=512),
            "merge": _node(
                "LatentConditionMerge",
                first=["large", 0],
                second=["small", 0],
                conditioning=["region", 0],
            ),
        }
    )

    plan = _service().build_plan("workflow", graph, node_definitions=definitions)

    assert plan.surfaces == ()
    assert plan.rejected_mask_nodes == ("mask",)
    assert plan.rejections[0].reason == "relevant_spatial_roots_disagree"
    assert set(plan.rejections[0].candidate_node_names) == {"large", "small"}


def test_agreeing_relevant_spatial_roots_form_consensus_authority() -> None:
    """Multiple relevant roots may establish a surface when their sizes agree."""

    definitions = _base_definitions()
    definitions.update(
        {
            "RootA": _latent_root_definition(),
            "RootB": _latent_root_definition(),
            "LatentConditionMerge": {
                "input": {
                    "required": {
                        "first": ["LATENT", {}],
                        "second": ["LATENT", {}],
                        "conditioning": ["CONDITIONING", {}],
                    }
                },
                "output": ["LATENT"],
            },
        }
    )
    graph = _graph(
        {
            "mask": _mask_node(),
            "region": _node("RegionalCondition", mask=["mask", 0]),
            "first": _node("RootA", width=640, height=896),
            "second": _node("RootB", width=640, height=896),
            "merge": _node(
                "LatentConditionMerge",
                first=["first", 0],
                second=["second", 0],
                conditioning=["region", 0],
            ),
        }
    )

    plan = _service().build_plan("workflow", graph, node_definitions=definitions)

    assert len(plan.surfaces) == 1
    authority = plan.surfaces[0].dimension_authority
    assert authority is not None
    assert set(authority.node_names) == {"first", "second"}
    assert authority.dimensions.width == 640
    assert authority.dimensions.height == 896


def test_disconnected_dimensioned_root_does_not_authorize_mask_canvas() -> None:
    """A spatial root elsewhere in a workflow must not authorize an unrelated mask."""

    graph = _regional_graph(root_class="NoiseRoot", width=768, height=768)
    nodes = graph["nodes"]
    assert isinstance(nodes, dict)
    nodes["sampler"] = _node("Sampler", latent_image=["latent_root", 0])
    definitions = _regional_definitions("NoiseRoot")

    plan = _service().build_plan("workflow", graph, node_definitions=definitions)

    assert plan.surfaces == ()
    assert plan.rejected_mask_nodes == ("mask",)
    assert plan.rejections[0].reason == "no_relevant_spatial_root_with_dimensions"


def test_cube_graph_section_cannot_borrow_dimensions_from_another_cube() -> None:
    """Cube-scoped planning must not inspect a spatial root in a sibling section."""

    definitions = _regional_definitions("NoiseRoot")
    mask_cube = _graph(
        {
            "mask": _mask_node(),
            "region": _node("RegionalCondition", mask=["mask", 0]),
            "sampler": _node("Sampler", positive=["region", 0]),
        }
    )
    dimensions_cube = _graph(
        {
            "latent_root": _node("NoiseRoot", width=1024, height=1024),
            "sampler": _node("Sampler", latent_image=["latent_root", 0]),
        }
    )

    mask_plan = _service().build_plan(
        "MaskCube",
        mask_cube,
        node_definitions=definitions,
    )
    dimensions_plan = _service().build_plan(
        "DimensionsCube",
        dimensions_cube,
        node_definitions=definitions,
    )

    assert mask_plan.surfaces == ()
    assert mask_plan.rejected_mask_nodes == ("mask",)
    assert dimensions_plan.surfaces == ()


def test_incomplete_live_root_definition_fails_closed_with_diagnostic() -> None:
    """Missing output metadata must reject synthetic authority without import failure."""

    graph = _regional_graph(root_class="UnavailablePackRoot", width=768, height=512)
    definitions = _regional_definitions("UnavailablePackRoot")
    del definitions["UnavailablePackRoot"]

    plan = _service().build_plan("workflow", graph, node_definitions=definitions)

    assert plan.surfaces == ()
    assert plan.rejected_mask_nodes == ("mask",)
    assert plan.rejections[0].reason == "no_relevant_spatial_root_with_dimensions"


def test_authored_image_mask_relationship_remains_image_backed() -> None:
    """Existing image-plus-mask consumers should retain their authored surface."""

    definitions = _base_definitions()
    definitions.update(
        {
            "LoadImage": {
                "input": {
                    "required": {
                        "image": [
                            "STRING",
                            {"image_upload": True, "image_folder": "input"},
                        ]
                    }
                },
                "output": ["IMAGE", "MASK"],
            },
            "ImageMaskConsumer": {
                "input": {
                    "required": {
                        "image": ["IMAGE", {}],
                        "mask": ["MASK", {}],
                    }
                },
                "output": ["IMAGE"],
            },
        }
    )
    graph = _graph(
        {
            "image": _node("LoadImage", image="source.png"),
            "mask": _mask_node(),
            "consumer": _node(
                "ImageMaskConsumer",
                image=["image", 0],
                mask=["mask", 0],
            ),
        }
    )

    plan = _service().build_plan("cube", graph, node_definitions=definitions)

    assert len(plan.surfaces) == 1
    assert plan.surfaces[0].kind is InputCanvasSurfaceKind.AUTHORED_IMAGE
    assert plan.surfaces[0].surface_key == "image"
    assert len(plan.mask_bindings) == 1
    assert plan.mask_bindings[0].surface == plan.surfaces[0]


def test_multiple_masks_share_one_synthetic_surface() -> None:
    """Regional masks resolving through one spatial root should share a canvas."""

    graph = _regional_graph(root_class="NoiseRoot", width=1280, height=720)
    nodes = graph["nodes"]
    assert isinstance(nodes, dict)
    nodes["mask_b"] = _mask_node()
    nodes["region_b"] = _node("RegionalCondition", mask=["mask_b", 0])
    sampler = cast(dict[str, object], nodes["sampler"])
    sampler_inputs = cast(dict[str, object], sampler["inputs"])
    sampler_inputs["negative"] = ["region_b", 0]
    definitions = _regional_definitions("NoiseRoot")
    sampler_definition = definitions["Sampler"]
    definition_inputs = cast(dict[str, object], sampler_definition["input"])
    required_inputs = cast(dict[str, object], definition_inputs["required"])
    required_inputs["negative"] = [
        "CONDITIONING",
        {},
    ]

    plan = _service().build_plan("workflow", graph, node_definitions=definitions)

    assert len(plan.surfaces) == 1
    assert {binding.mask_endpoint.node_name for binding in plan.mask_bindings} == {
        "mask",
        "mask_b",
    }
    assert {binding.surface for binding in plan.mask_bindings} == {plan.surfaces[0]}


def test_independent_mask_regions_receive_independent_synthetic_surfaces() -> None:
    """Unrelated regional branches should retain separate canvas identities."""

    definitions = _regional_definitions("NoiseRoot")
    graph = _graph(
        {
            "mask_a": _mask_node(),
            "region_a": _node("RegionalCondition", mask=["mask_a", 0]),
            "root_a": _node("NoiseRoot", width=1024, height=768),
            "sampler_a": _node(
                "Sampler",
                latent_image=["root_a", 0],
                positive=["region_a", 0],
            ),
            "mask_b": _mask_node(),
            "region_b": _node("RegionalCondition", mask=["mask_b", 0]),
            "root_b": _node("NoiseRoot", width=512, height=512),
            "sampler_b": _node(
                "Sampler",
                latent_image=["root_b", 0],
                positive=["region_b", 0],
            ),
        }
    )

    plan = _service().build_plan("workflow", graph, node_definitions=definitions)

    assert len(plan.surfaces) == 2
    dimensions_by_mask = {
        binding.mask_node_name: (
            binding.surface.dimensions.width,
            binding.surface.dimensions.height,
        )
        for binding in plan.mask_bindings
        if binding.surface.dimensions is not None
    }
    assert dimensions_by_mask == {
        "mask_a": (1024, 768),
        "mask_b": (512, 512),
    }


def _service() -> InputCanvasPlanService:
    """Build the pure planning service used by deterministic tests."""

    definitions = WorkflowNodeDefinitionService()
    return InputCanvasPlanService(
        node_definition_service=definitions,
        endpoint_service=InputAssetEndpointService(definitions),
    )


def _regional_graph(
    *,
    root_class: str,
    width: int,
    height: int,
) -> dict[str, object]:
    """Return one mask-conditioning and latent-root convergence graph."""

    return _graph(
        {
            "mask": _mask_node(),
            "region": _node("RegionalCondition", mask=["mask", 0]),
            "latent_root": _node(root_class, width=width, height=height),
            "sampler": _node(
                "Sampler",
                latent_image=["latent_root", 0],
                positive=["region", 0],
            ),
        }
    )


def _regional_definitions(
    root_class: str,
) -> dict[str, dict[str, object]]:
    """Return live definitions for a basic custom regional graph."""

    definitions = _base_definitions()
    definitions.update(
        {
            root_class: _latent_root_definition(),
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
    )
    return definitions


def _base_definitions() -> dict[str, dict[str, object]]:
    """Return reusable mask upload and regional-conditioning definitions."""

    return {
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
    }


def _latent_root_definition() -> dict[str, object]:
    """Return one class-independent latent creation capability definition."""

    return {
        "input": {
            "required": {
                "width": ["INT", {"min": 16, "step": 8}],
                "height": ["INT", {"min": 16, "step": 8}],
            }
        },
        "output": ["LATENT"],
    }


def _mask_node() -> dict[str, object]:
    """Return one authored mask upload node."""

    return _node("LoadImageMask", image="mask.png")


def _node(class_type: str, **inputs: object) -> dict[str, object]:
    """Return one API-style authored graph node."""

    return {"class_type": class_type, "inputs": dict(inputs)}


def _graph(nodes: Mapping[str, object]) -> dict[str, object]:
    """Return one editor graph wrapper."""

    return {"nodes": dict(nodes)}
