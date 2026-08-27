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

"""Protect recipe serialization at the canonical cube authoring boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.ports.recipe_repository import LoadedRecipeDocument
from substitute.application.recipes import RecipeIoService
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState


class _UnusedRecipeRepository:
    """Satisfy the recipe repository port for serialization-only tests."""

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Reject repository reads outside this test's serialization scope."""

        raise AssertionError(f"Unexpected recipe read: {path}")

    def has_embedded_recipe_script(self, path: Path) -> bool:
        """Reject embedded-script checks outside this test's scope."""

        raise AssertionError(f"Unexpected recipe inspection: {path}")

    def save_recipe_document(
        self,
        path: Path,
        *,
        project_name: str,
        sugar_script_text: str,
    ) -> None:
        """Reject repository writes outside this test's serialization scope."""

        raise AssertionError(
            f"Unexpected recipe write: {path}; {project_name}; {sugar_script_text}"
        )


def _cube_state(alias: str, graph: JsonObject) -> CubeState:
    """Return one canonical cube state backed by the supplied runtime graph."""

    return CubeState(
        cube_id=str(graph["cube_id"]),
        version=str(graph["version"]),
        alias=alias,
        original_cube=graph,
        buffer=graph,
    )


def _surface_control(
    node_key: str,
    input_key: str,
    *,
    value_type: str,
) -> dict[str, str]:
    """Return one canonical authored surface-control declaration."""

    return {
        "control_id": f"{node_key}.{input_key}",
        "symbol": node_key,
        "input_name": input_key,
        "label": input_key,
        "class_type": "TestNode",
        "value_type": value_type,
    }


def test_recipe_serialization_omits_cube_boundary_implementation_values() -> None:
    """Boundary-owned node inputs must remain structural instead of becoming sets."""

    source: JsonObject = {
        "cube_id": "test/source.cube",
        "version": "1.0.0",
        "nodes": {"generate": {"class_type": "TestSource", "inputs": {}}},
        "inputs": {},
        "outputs": {"output.image": "generate"},
        "surface": {"default_flavor_id": "default", "controls": []},
    }
    upscale: JsonObject = {
        "cube_id": "test/upscale.cube",
        "version": "1.0.0",
        "nodes": {
            "upscale_by_factor": {
                "class_type": "TestNode",
                "inputs": {
                    "image": ["@binding", "input.value"],
                    "value": 1.2,
                },
            }
        },
        "inputs": {
            "input.value": {
                "kind": "input",
                "targets": [["upscale_by_factor", "image"]],
            }
        },
        "outputs": {"output.image": "upscale_by_factor"},
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                _surface_control("upscale_by_factor", "value", value_type="number")
            ],
        },
    }
    workflow = SimpleNamespace(
        stack_order=["Source", "Upscale"],
        cubes={
            "Source": _cube_state("Source", source),
            "Upscale": _cube_state("Upscale", upscale),
        },
        global_overrides={},
        global_override_selections={},
        override_control_states={},
    )

    script = RecipeIoService(
        recipe_repository=_UnusedRecipeRepository()
    ).serialize_workflow_to_sugar_script(workflow)

    assert "@binding" not in script
    assert "set Upscale.upscale_by_factor.image" not in script
    assert "set Upscale.upscale_by_factor.value = 1.2" in script
    assert "connect Source.output.image to Upscale.input.value" in script


def test_recipe_serialization_preserves_declared_ordered_mask_lists() -> None:
    """A surface-declared list remains authored Sugar data in exact order."""

    region: JsonObject = {
        "cube_id": "test/region.cube",
        "version": "1.0.0",
        "nodes": {
            "load_mask_batch": {
                "class_type": "TestNode",
                "inputs": {"image": ["first.png", "second.png"]},
            }
        },
        "inputs": {},
        "outputs": {"output.mask": "load_mask_batch"},
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                _surface_control("load_mask_batch", "image", value_type="object")
            ],
        },
    }
    workflow = SimpleNamespace(
        stack_order=["Region"],
        cubes={"Region": _cube_state("Region", region)},
        global_overrides={},
        global_override_selections={},
        override_control_states={},
    )

    script = RecipeIoService(
        recipe_repository=_UnusedRecipeRepository()
    ).serialize_workflow_to_sugar_script(workflow)

    assert 'set Region.load_mask_batch.image = ["first.png", "second.png"]' in script


def test_recipe_serialization_preserves_widget_backed_subgraph_inputs() -> None:
    """A visible subgraph widget must reach Sugar even without a surface entry."""

    sampler: JsonObject = {
        "cube_id": "test/text-to-image.cube",
        "version": "1.0.0",
        "nodes": {
            "ksampler": {
                "class_type": "subgraph-ksampler",
                "label": "KSampler",
                "inputs": {
                    "model": ["checkpoint", 0],
                    "batch_size": 2,
                },
            },
            "checkpoint": {
                "class_type": "TestCheckpoint",
                "inputs": {},
            },
        },
        "inputs": {},
        "outputs": {"output.image": "ksampler"},
        "surface": {"default_flavor_id": "default", "controls": []},
        "subgraphs": [
            {
                "id": "subgraph-ksampler",
                "inputs": [
                    {"name": "model", "linkIds": [10], "type": "MODEL"},
                    {"name": "batch_size", "linkIds": [11], "type": "INT"},
                ],
                "links": [
                    {
                        "id": 10,
                        "origin_id": -10,
                        "origin_slot": 0,
                        "target_id": 2,
                        "target_slot": 0,
                        "type": "MODEL",
                    },
                    {
                        "id": 11,
                        "origin_id": -10,
                        "origin_slot": 1,
                        "target_id": 3,
                        "target_slot": 0,
                        "type": "INT",
                    },
                ],
                "nodes": [
                    {
                        "id": 2,
                        "inputs": [
                            {"name": "model", "link": 10, "type": "MODEL"},
                        ],
                    },
                    {
                        "id": 3,
                        "inputs": [
                            {
                                "name": "batch_size",
                                "link": 11,
                                "type": "INT",
                                "widget": {"name": "batch_size"},
                            },
                        ],
                    },
                ],
            }
        ],
    }
    workflow = SimpleNamespace(
        stack_order=["Image"],
        cubes={"Image": _cube_state("Image", sampler)},
        global_overrides={},
        global_override_selections={},
        override_control_states={},
    )

    script = RecipeIoService(
        recipe_repository=_UnusedRecipeRepository()
    ).serialize_workflow_to_sugar_script(workflow)

    assert "set Image.KSampler.batch_size = 2" in script
    assert "set Image.KSampler.model" not in script
