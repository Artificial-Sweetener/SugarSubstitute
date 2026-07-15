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

"""Build fast local lookup indexes for recipe model resolution."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.model_metadata import ModelCatalogLookup


@dataclass(frozen=True, slots=True)
class LocalRecipeModel:
    """Represent a locally installed model usable for recipe resolution."""

    kind: str
    backend_value: str
    display_name: str
    relative_path: str
    sha256: str | None


class RecipeModelResolutionIndex:
    """Index local model catalog items by literal value and SHA256."""

    def __init__(self, models: tuple[LocalRecipeModel, ...]) -> None:
        """Build lookup tables from local model records."""

        self._by_value = {
            (model.kind, model.backend_value.casefold()): model for model in models
        }
        self._by_hash = {
            (model.kind, model.sha256.upper()): model
            for model in models
            if model.sha256
        }

    @classmethod
    def from_catalog(
        cls,
        catalog: ModelCatalogLookup,
        *,
        kinds: tuple[str, ...],
    ) -> RecipeModelResolutionIndex:
        """Build a local model resolution index for the requested model kinds."""

        models: list[LocalRecipeModel] = []
        for kind in kinds:
            for item in catalog.list_models(kind):
                models.append(
                    LocalRecipeModel(
                        kind=item.kind,
                        backend_value=item.backend_value,
                        display_name=item.display_name,
                        relative_path=item.relative_path,
                        sha256=item.sha256.upper() if item.sha256 else None,
                    )
                )
        return cls(tuple(models))

    def find_literal(self, *, kind: str, value: str) -> LocalRecipeModel | None:
        """Return a local model whose backend value exactly matches the recipe."""

        return self._by_value.get((kind, value.casefold()))

    def find_hash(self, *, kind: str, sha256: str) -> LocalRecipeModel | None:
        """Return a local model whose SHA256 matches the recipe hash."""

        return self._by_hash.get((kind, sha256.upper()))


__all__ = ["LocalRecipeModel", "RecipeModelResolutionIndex"]
