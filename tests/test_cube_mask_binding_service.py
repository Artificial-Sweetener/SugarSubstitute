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

"""Cube regression tests for shared editable mask binding discovery."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.application.workflows import CanvasIoService
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.workflow import InputCanvasPlan


class _DimensionlessRepository:
    """Provide unused image repository methods for path-policy tests."""

    def load_image(self, path: Path) -> object | None:
        """Return no image payload for unused load calls."""

        _ = path
        return None

    def save_image(self, path: Path, *, image: object) -> bool:
        """Return success for unused save calls."""

        _ = path, image
        return True

    def save_blank_mask(self, path: Path, *, size: object) -> bool:
        """Return success for unused blank-mask calls."""

        _ = path, size
        return True

    def save_blank_image(self, path: Path, *, width: int, height: int) -> bool:
        """Return success for unused blank-image calls."""

        _ = path, width, height
        return True

    def image_dimensions(self, path: Path) -> tuple[int, int] | None:
        """Return no dimensions for unused dimension calls."""

        _ = path
        return None


def test_build_index_discovers_editable_binding_from_inpaint_cube() -> None:
    """The inpaint cube should expose a single editable LoadImageMask binding."""

    plan = _canvas_plan("Inpaint", _inpaint_cube_graph())

    assert [endpoint.identity for endpoint in plan.image_endpoints] == [
        ("Inpaint", "load_image")
    ]
    assert len(plan.mask_bindings) == 1
    binding = plan.mask_bindings[0]
    assert binding.section_key == "Inpaint"
    assert binding.surface.surface_key == "load_image"
    assert binding.mask_node_name == "load_image_as_mask"
    assert binding.consumer_node_name == "encode_inpaint_conds"


def test_build_index_discovers_multiple_masks_for_one_image_provider() -> None:
    """One image provider may bind to every mask provider on the same consumer."""

    cube_graph = {
        "nodes": {
            "image": {"class_type": "LoadImage", "inputs": {}},
            "mask_a": {"class_type": "LoadImageMask", "inputs": {}},
            "mask_b": {"class_type": "LoadImageMask", "inputs": {}},
            "consumer": {
                "class_type": "Blend",
                "inputs": {
                    "image": ["image", 0],
                    "mask_a": ["mask_a", 0],
                    "mask_b": ["mask_b", 0],
                },
            },
        }
    }

    plan = _canvas_plan("CubeA", cube_graph)

    assert [binding.mask_node_name for binding in plan.mask_bindings] == [
        "mask_a",
        "mask_b",
    ]
    assert plan.bindings_for_surface_key("image") == plan.mask_bindings


def test_build_index_ignores_unrelated_mask_loader() -> None:
    """LoadImageMask nodes without a shared consumer should not create bindings."""

    cube_graph = {
        "nodes": {
            "image": {"class_type": "LoadImage", "inputs": {}},
            "mask": {"class_type": "LoadImageMask", "inputs": {}},
            "unused_mask": {"class_type": "LoadImageMask", "inputs": {}},
            "consumer": {
                "class_type": "Blend",
                "inputs": {
                    "image": ["image", 0],
                    "mask": ["mask", 0],
                },
            },
        }
    }

    plan = _canvas_plan("CubeA", cube_graph)

    assert [binding.mask_node_name for binding in plan.mask_bindings] == ["mask"]


def test_inpaint_binding_participates_in_input_bound_mask_path_policy(
    tmp_path: Path,
) -> None:
    """The inpaint LoadImageMask binding should produce input-bound mask names."""

    binding = _canvas_plan("Inpaint", _inpaint_cube_graph()).mask_bindings[0]

    mask_path = CanvasIoService(
        image_repository=_DimensionlessRepository()
    ).expected_bound_mask_path(
        workflow_name="Recipe",
        associated_image_path=Path("E:/photos/cat.png"),
        cube_alias=binding.section_key,
        mask_node_name=binding.mask_node_name,
        image_size=(1024, 768),
        projects_dir=tmp_path,
    )

    assert mask_path.name.startswith("cat__")
    assert "__1024x768__Inpaint__load_image_as_mask.png" in mask_path.name


def _inpaint_cube_graph() -> dict[str, object]:
    """Return the inpaint mask-binding graph shape formerly loaded from shipped cubes."""

    return {
        "nodes": {
            "load_image": {"class_type": "LoadImage", "inputs": {}},
            "load_image_as_mask": {"class_type": "LoadImageMask", "inputs": {}},
            "encode_inpaint_conds": {
                "class_type": "VAEEncodeForInpaint",
                "inputs": {
                    "pixels": ["load_image", 0],
                    "mask": ["load_image_as_mask", 0],
                },
            },
        }
    }


def _canvas_plan(
    section_key: str,
    graph: Mapping[str, object],
) -> InputCanvasPlan:
    """Build one cube-scoped plan through the shared production services."""

    definitions = WorkflowNodeDefinitionService()
    return InputCanvasPlanService(
        node_definition_service=definitions,
        endpoint_service=InputAssetEndpointService(definitions),
    ).build_plan(section_key, graph)


def test_build_index_fails_closed_for_ambiguous_mask_binding() -> None:
    """One mask feeding multiple eligible consumers should be treated as ambiguous."""

    cube_graph = {
        "nodes": {
            "image_a": {"class_type": "LoadImage", "inputs": {}},
            "image_b": {"class_type": "LoadImage", "inputs": {}},
            "mask": {"class_type": "LoadImageMask", "inputs": {}},
            "consumer_a": {
                "class_type": "Blend",
                "inputs": {"image": ["image_a", 0], "mask": ["mask", 0]},
            },
            "consumer_b": {
                "class_type": "Blend",
                "inputs": {"image": ["image_b", 0], "mask": ["mask", 0]},
            },
        }
    }

    plan = _canvas_plan("CubeA", cube_graph)

    assert plan.mask_bindings == ()
    assert plan.rejected_mask_nodes == ("mask",)
