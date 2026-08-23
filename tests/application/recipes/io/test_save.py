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

"""Verify application recipe save behavior."""

from __future__ import annotations

from pathlib import Path

from substitute.application.recipes import RecipeIoService
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.infrastructure.persistence import FileRecipeRepository


def test_recipe_io_service_save_writes_recipe_and_creates_backups(
    tmp_path: Path,
) -> None:
    """Persist a headered recipe and retain prior saves as Sugar backups."""

    file_path = tmp_path / "recipe.sugar"
    cube_buffer: JsonObject = {
        "cube_id": "Text To Image",
        "version": "1.0.0",
        "nodes": {
            "positive_prompt": {
                "class_type": "CLIPTextEncode",
                "inputs": {"prompt_template": "hello world"},
            }
        },
        "inputs": {},
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                {
                    "control_id": "positive_prompt.prompt_template",
                    "symbol": "positive_prompt",
                    "input_name": "prompt_template",
                    "label": "Prompt",
                    "class_type": "CLIPTextEncode",
                    "value_type": "string",
                }
            ],
        },
    }
    cube_state = CubeState(
        cube_id="Text To Image",
        version="1.0.0",
        alias="A",
        original_cube=cube_buffer,
        buffer=cube_buffer,
    )
    workflow = WorkflowState(
        cubes={"A": cube_state},
        stack_order=["A"],
        global_overrides={"seed": {"value": 1, "mode": "global"}},
    )
    service = RecipeIoService(recipe_repository=FileRecipeRepository())

    service.save_workflow_recipe(
        file_path,
        workflow_name="My Workflow",
        workflow=workflow,
    )

    assert file_path.exists()
    assert "# Project: My Workflow" in file_path.read_text(encoding="utf-8")
    assert "set *.*.seed = 1" in file_path.read_text(encoding="utf-8")

    service.save_workflow_recipe(
        file_path,
        workflow_name="My Workflow",
        workflow=workflow,
    )
    versions_directory = file_path.parent / "versions"
    backups = sorted(versions_directory.glob("recipe*.*"))
    assert len(backups) == 1
    assert backups[0].suffix == ".sugar"

    workflow.global_overrides["seed"]["value"] = 2
    service.save_workflow_recipe(
        file_path,
        workflow_name="My Workflow",
        workflow=workflow,
    )

    assert all(path.suffix == ".sugar" for path in versions_directory.glob("recipe*.*"))
