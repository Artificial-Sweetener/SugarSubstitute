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

"""Verify recipe document classification and destination policy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.ports.recipe_repository import LoadedRecipeDocument
from substitute.application.recipes import RecipeIoService


class _FakeRecipeRepository:
    """Provide deterministic recipe storage behavior for document policy tests."""

    def __init__(self) -> None:
        """Initialize empty operation capture."""

        self.saved: list[tuple[Path, str, str]] = []
        self.loaded_path: Path | None = None

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Return a deterministic recipe document for protocol completeness."""

        self.loaded_path = path
        return LoadedRecipeDocument(
            sugar_script_text="",
            source_path=path,
            source_kind="text",
        )

    def has_embedded_recipe_script(self, path: Path) -> bool:
        """Report whether one named fixture path carries embedded metadata."""

        return path.name == "embedded.png"

    def save_recipe_document(
        self,
        path: Path,
        *,
        project_name: str,
        sugar_script_text: str,
    ) -> None:
        """Record one save request."""

        self.saved.append((path, project_name, sugar_script_text))


def test_recipe_io_service_classifies_text_recipe_paths() -> None:
    """Accept only native Sugar text recipe paths."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    sugar = service.classify_recipe_document(Path("E:/recipes/demo.sugar"))
    sugar_txt = service.classify_recipe_document(Path("E:/recipes/demo.sugar.txt"))
    txt = service.classify_recipe_document(Path("E:/recipes/demo.txt"))

    assert sugar.supported is True
    assert sugar.source_kind == "text"
    assert sugar_txt.supported is False
    assert sugar_txt.source_kind is None
    assert txt.supported is False
    assert txt.source_kind is None


def test_recipe_io_service_classifies_png_by_embedded_recipe_metadata() -> None:
    """Accept PNG recipes only when repository metadata confirms one."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    embedded = service.classify_recipe_document(Path("E:/recipes/embedded.png"))
    plain = service.classify_recipe_document(Path("E:/recipes/plain.png"))

    assert embedded.supported is True
    assert embedded.source_kind == "png"
    assert embedded.reason == "png_embedded_recipe"
    assert plain.supported is False
    assert plain.source_kind is None
    assert plain.reason == "png_without_embedded_recipe"


def test_recipe_io_service_rejects_unsupported_recipe_drop_paths() -> None:
    """Reject non-recipe extensions before any parse work begins."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    classified = service.classify_recipe_document(Path("E:/images/plain.jpg"))

    assert classified.supported is False
    assert classified.source_kind is None
    assert classified.reason == "unsupported_extension"


def test_build_default_recipe_path_uses_script_scoped_recipe_location(
    tmp_path: Path,
) -> None:
    """Build default paths inside their workflow-named script directory."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    destination = service.build_default_recipe_path("Recipe One", tmp_path)

    assert destination == (tmp_path / "Recipe One" / "Recipe One.sugar").resolve()


def test_validate_recipe_destination_accepts_paths_outside_script_root(
    tmp_path: Path,
) -> None:
    """Permit an explicitly selected destination outside the script root."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    destination = service.validate_recipe_destination(
        tmp_path.parent / "external.sugar"
    )

    assert destination == (tmp_path.parent / "external.sugar").resolve()


def test_validate_recipe_destination_rejects_directory_paths(tmp_path: Path) -> None:
    """Reject directories as workflow recipe destinations."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    try:
        service.validate_recipe_destination(tmp_path)
    except ValueError as error:
        assert "Workflow recipe" in str(error)
    else:  # pragma: no cover - assertion path only
        raise AssertionError(
            "Expected recipe destination validation to reject directory"
        )


def test_validate_recipe_destination_rejects_unsupported_extensions(
    tmp_path: Path,
) -> None:
    """Reject destination suffixes outside the Sugar recipe format."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    try:
        service.validate_recipe_destination(tmp_path / "recipe.json")
    except ValueError as error:
        assert ".sugar" in str(error)
    else:  # pragma: no cover - assertion path only
        raise AssertionError("Expected recipe destination validation to reject suffix")


def test_save_workflow_recipe_to_default_path_returns_saved_destination(
    tmp_path: Path,
) -> None:
    """Persist the default recipe destination and return its resolved path."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    workflow = SimpleNamespace(stack_order=[], cubes={}, global_overrides={})

    destination = service.save_workflow_recipe_to_default_path(
        "Recipe Two",
        workflow,
        tmp_path,
    )

    assert destination == (tmp_path / "Recipe Two" / "Recipe Two.sugar").resolve()
    assert len(repository.saved) == 1
    saved_path, project_name, recipe_text = repository.saved[0]
    assert saved_path == destination
    assert project_name == "Recipe Two"
    assert recipe_text.strip() == ""
