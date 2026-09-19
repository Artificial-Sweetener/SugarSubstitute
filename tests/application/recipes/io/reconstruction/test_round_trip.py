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

"""Verify the public recipe service preserves semantic workflow state on disk."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from substitute.application.recipes import RecipeIoService
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.workflow import WorkflowState
from substitute.infrastructure.persistence.file_recipe_repository import (
    FileRecipeRepository,
)
from tests.application.recipes.io.serialization.support import (
    _canonical_test_cube_state,
)


def test_public_recipe_save_and_load_round_trip_semantic_workflow(
    tmp_path: Path,
) -> None:
    """Save and reload Cubes, links, overrides, controls, and Unicode as one contract."""

    source = WorkflowState(
        cubes={
            "主役": _canonical_test_cube_state(
                cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
                version="1.2.3",
                alias="主役",
                original_cube={},
                buffer={
                    "nodes": {
                        "prompt": {
                            "class_type": "CLIPTextEncode",
                            "inputs": {"text": "星空の猫 🐈"},
                        },
                        "sampler": {
                            "class_type": "KSampler",
                            "inputs": {"seed": 4815162342},
                        },
                    }
                },
                field_control_states={
                    "sampler": {"seed": SeedControlState(SeedMode.FIXED)}
                },
            ),
            "Upscale": _canonical_test_cube_state(
                cube_id="Artificial-Sweetener/Base-Cubes/Diffusion Upscale.cube",
                version="2.0.0",
                alias="Upscale",
                original_cube={},
                buffer={
                    "nodes": {
                        "source": {
                            "class_type": "ImageScale",
                            "inputs": {"scale_by": 1.5},
                            "node_link": {
                                "from_cube": "主役",
                                "from_node": "sampler",
                            },
                        }
                    },
                },
                bypassed=True,
                output_persistence_enabled=False,
            ),
        },
        stack_order=["主役", "Upscale"],
        global_overrides={"seed": {"value": 99, "mode": "global"}},
        global_override_selections={"seed": True, "scheduler": False},
        override_control_states={"seed": SeedControlState(SeedMode.FIXED)},
    )
    destination = tmp_path / "Semantic Workflow.sugar"
    service = RecipeIoService(recipe_repository=FileRecipeRepository())

    service.save_workflow_recipe(
        destination,
        workflow_name="Semantic Workflow",
        workflow=source,
    )
    loaded = service.load_and_parse_recipe_document(destination)
    parsed = loaded.parsed_script
    hero_nodes = cast(dict[str, object], parsed.buffers["主役"]["nodes"])
    hero_prompt = cast(dict[str, object], hero_nodes["prompt"])
    hero_inputs = cast(dict[str, object], hero_prompt["inputs"])
    upscale_nodes = cast(dict[str, object], parsed.buffers["Upscale"]["nodes"])
    upscale_source = cast(dict[str, object], upscale_nodes["source"])

    assert parsed.project_name == "Semantic Workflow"
    assert tuple(parsed.buffers) == ("主役", "Upscale")
    assert parsed.buffers["主役"]["cube_id"] == source.cubes["主役"].cube_id
    assert parsed.buffers["主役"]["version"] == "1.2.3"
    assert hero_inputs["text"] == "星空の猫 🐈"
    assert upscale_source["node_link"] == {
        "from_cube": "主役",
        "from_node": "sampler",
    }
    assert parsed.buffers["Upscale"]["bypassed"] is True
    assert parsed.buffers["Upscale"]["save_outputs"] is False
    assert parsed.global_overrides == source.global_overrides
    assert parsed.global_override_selections == source.global_override_selections
    assert parsed.field_control_states_by_alias == {
        "主役": {"sampler": {"seed": SeedControlState(SeedMode.FIXED)}}
    }
    assert parsed.override_control_states == source.override_control_states
