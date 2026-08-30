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

"""Verify PNG-embedded recipe persistence behavior."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, PngImagePlugin
import pytest

from substitute.infrastructure.persistence import FileRecipeRepository


def _write_png_recipe(path: Path) -> None:
    """Write the smallest PNG carrying one Sugar recipe metadata field."""

    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("sugar_script", "use Text To Image")
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(path, pnginfo=metadata)


def test_file_recipe_repository_loads_png_embedded_recipe(tmp_path: Path) -> None:
    """Load an embedded Sugar script and preserve PNG document identity."""

    png_path = tmp_path / "recipe.png"
    _write_png_recipe(png_path)

    loaded = FileRecipeRepository().load_recipe_document(png_path)

    assert loaded.source_kind == "png"
    assert loaded.source_path == png_path
    assert loaded.sugar_script_text == "use Text To Image"


def test_file_recipe_repository_detects_embedded_recipe_metadata(
    tmp_path: Path,
) -> None:
    """Recognize an image carrying Sugar metadata without loading a document."""

    png_path = tmp_path / "recipe.png"
    _write_png_recipe(png_path)

    assert FileRecipeRepository().has_embedded_recipe_script(png_path) is True


def test_file_recipe_repository_rejects_plain_png_recipe_load(tmp_path: Path) -> None:
    """Fail closed for images that do not carry Sugar recipe metadata."""

    png_path = tmp_path / "plain.png"
    Image.new("RGB", (2, 2), color=(0, 0, 0)).save(png_path)
    repository = FileRecipeRepository()

    assert repository.has_embedded_recipe_script(png_path) is False
    with pytest.raises(ValueError, match="No embedded recipe found in PNG metadata."):
        repository.load_recipe_document(png_path)
