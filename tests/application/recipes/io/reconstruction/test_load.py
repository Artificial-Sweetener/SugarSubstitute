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

"""Verify recipe document loading and SugarScript reconstruction."""

from __future__ import annotations

from pathlib import Path

from substitute.application.ports.recipe_repository import LoadedRecipeDocument
from substitute.application.recipes import RecipeIoService


class _FakeRecipeRepository:
    """Return one deterministic saved recipe document."""

    def __init__(self) -> None:
        """Initialize source-path capture."""

        self.loaded_path: Path | None = None

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Return a canonical source document with global override state."""

        self.loaded_path = path
        return LoadedRecipeDocument(
            sugar_script_text=(
                'use "Artificial-Sweetener/Base-Cubes/Text to Image.cube" as A\n'
                "set *.*.seed = 7\n"
                '# global_override_selection {"key":"seed","selected":true}\n'
            ),
            source_path=path,
            source_kind="text",
        )

    def has_embedded_recipe_script(self, path: Path) -> bool:
        """Provide protocol completeness without PNG behavior."""

        _ = path
        return False

    def save_recipe_document(
        self,
        path: Path,
        *,
        project_name: str,
        sugar_script_text: str,
    ) -> None:
        """Provide protocol completeness for the load-only owner."""

        _ = path, project_name, sugar_script_text


def test_recipe_io_service_load_and_parse_orchestration() -> None:
    """Preserve source metadata and parsed buffers when loading recipes."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    source_path = Path("E:/recipes/loaded.sugar")

    parsed_recipe = service.load_and_parse_recipe_document(source_path)

    assert repository.loaded_path == source_path
    assert parsed_recipe.loaded_document.source_path == source_path
    assert parsed_recipe.parsed_script.global_overrides["seed"]["value"] == 7
    assert parsed_recipe.parsed_script.global_override_selections == {"seed": True}
    assert (
        parsed_recipe.parsed_script.buffers["A"]["cube_id"]
        == "Artificial-Sweetener/Base-Cubes/Text to Image.cube"
    )
