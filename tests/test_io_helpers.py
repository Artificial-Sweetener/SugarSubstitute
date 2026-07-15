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

"""Characterization tests for Phase 6 recipe persistence utilities and contracts."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, PngImagePlugin

from substitute.application.recipes import RecipeIoService
from substitute.domain.workflow import CubeState
from substitute.infrastructure.persistence.image_naming import (
    get_next_bucket_run_number,
    get_next_image_counter,
)
from substitute.infrastructure.persistence import FileRecipeRepository


def test_get_next_image_counter(tmp_path: Path) -> None:
    """Counter helper should return max existing index + 1 for workflow prefix."""

    output_dir = tmp_path
    (output_dir / "001_my_flow_x.png").write_text("", encoding="utf-8")
    (output_dir / "005_my_flow_y.png").write_text("", encoding="utf-8")
    (output_dir / "003_other_flow.png").write_text("", encoding="utf-8")

    assert get_next_image_counter("My Flow", str(output_dir)) == 6


def test_get_next_bucket_run_number(tmp_path: Path) -> None:
    """Bucket counter helper should return max leading image index plus one."""

    output_dir = tmp_path
    (output_dir / "001_my_flow_x.png").write_text("", encoding="utf-8")
    (output_dir / "005_other_flow_y.png").write_text("", encoding="utf-8")
    (output_dir / "not_a_run.png").write_text("", encoding="utf-8")

    assert get_next_bucket_run_number(str(output_dir)) == 6


class DummyWorkflow:
    """Minimal workflow shape consumed by `RecipeIoService` serialization."""

    def __init__(self, cubes: dict, stack_order: list[str], global_overrides=None):
        self.cubes = cubes
        self.stack_order = stack_order
        self.global_overrides = global_overrides or {}


def test_recipe_io_service_save_writes_and_creates_backups(tmp_path: Path) -> None:
    """Recipe save should persist headered script and rotate versions on rewrites."""

    file_path = tmp_path / "recipe.sugar"
    cube_buffer = {
        "cube_id": "Text To Image",
        "nodes": {"positive_prompt": {"inputs": {"prompt_template": "hello world"}}},
    }
    cube_state = CubeState(
        cube_id="Text To Image",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer=cube_buffer,
    )
    workflow = DummyWorkflow(
        {"A": cube_state},
        ["A"],
        global_overrides={"seed": {"value": 1, "mode": "global"}},
    )
    service = RecipeIoService(recipe_repository=FileRecipeRepository())

    service.save_workflow_recipe(
        file_path,
        workflow_name="My Workflow",
        workflow=workflow,
    )
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "# Project: My Workflow" in content
    assert "set *.*.seed = 1" in content

    service.save_workflow_recipe(
        file_path,
        workflow_name="My Workflow",
        workflow=workflow,
    )
    versions_dir = file_path.parent / "versions"
    backups = sorted(versions_dir.glob("recipe*.*"))
    assert len(backups) == 1
    assert backups[0].suffix == ".sugar"

    workflow.global_overrides["seed"]["value"] = 2
    service.save_workflow_recipe(
        file_path,
        workflow_name="My Workflow",
        workflow=workflow,
    )
    assert all(path.suffix == ".sugar" for path in versions_dir.glob("recipe*.*"))


def test_file_recipe_repository_loads_png_embedded_recipe(tmp_path: Path) -> None:
    """PNG recipe load should return `png` source kind and embedded Sugar text."""

    png_path = tmp_path / "recipe.png"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("sugar_script", "use Text To Image")
    image = Image.new("RGB", (2, 2), color=(255, 0, 0))
    image.save(png_path, pnginfo=metadata)

    repository = FileRecipeRepository()
    loaded = repository.load_recipe_document(png_path)

    assert loaded.source_kind == "png"
    assert loaded.source_path == png_path
    assert loaded.sugar_script_text == "use Text To Image"


def test_file_recipe_repository_sniffs_png_embedded_recipe(tmp_path: Path) -> None:
    """PNG metadata sniffing should detect recipe-bearing images cheaply."""

    png_path = tmp_path / "recipe.png"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("sugar_script", "use Text To Image")
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(png_path, pnginfo=metadata)

    repository = FileRecipeRepository()

    assert repository.has_embedded_recipe_script(png_path) is True


def test_file_recipe_repository_sniffs_plain_png_as_not_recipe(
    tmp_path: Path,
) -> None:
    """PNG metadata sniffing should not accept images without Sugar metadata."""

    png_path = tmp_path / "plain.png"
    Image.new("RGB", (2, 2), color=(0, 0, 0)).save(png_path)

    repository = FileRecipeRepository()

    assert repository.has_embedded_recipe_script(png_path) is False


def test_file_recipe_repository_rejects_png_without_embedded_recipe(
    tmp_path: Path,
) -> None:
    """PNG recipe load should fail closed when sugar metadata is absent."""

    png_path = tmp_path / "recipe.png"
    image = Image.new("RGB", (2, 2), color=(0, 0, 0))
    image.save(png_path)
    repository = FileRecipeRepository()

    try:
        repository.load_recipe_document(png_path)
    except ValueError as error:
        assert "No embedded recipe found in PNG metadata." in str(error)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError when PNG metadata lacks sugar_script")
