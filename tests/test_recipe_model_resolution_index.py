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

"""Tests for fast local recipe model lookup indexes."""

from __future__ import annotations

from substitute.application.model_metadata import ModelCatalogItem
from substitute.application.recipes import RecipeModelResolutionIndex


class _Catalog:
    """Return deterministic model catalog items for index tests."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store model items by kind."""

        self._items = items

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return catalog items for one kind."""

        return tuple(item for item in self._items if item.kind == kind)

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return refreshed catalog items for one kind."""

        return self.list_models(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation in the test double."""

        _ = kind


def test_recipe_model_resolution_index_finds_literal_value() -> None:
    """Literal recipe model values should resolve from the local catalog."""

    index = RecipeModelResolutionIndex.from_catalog(
        _Catalog((_item("checkpoints", "SDXL/base.safetensors", "A" * 64),)),
        kinds=("checkpoints",),
    )

    result = index.find_literal(
        kind="checkpoints",
        value="sdxl/BASE.safetensors",
    )

    assert result is not None
    assert result.backend_value == "SDXL/base.safetensors"


def test_recipe_model_resolution_index_finds_same_hash_local_model() -> None:
    """Hash lookup should resolve renamed local models by kind and SHA256."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    index = RecipeModelResolutionIndex.from_catalog(
        _Catalog((_item("loras", "Installed/renamed.safetensors", sha256),)),
        kinds=("loras",),
    )

    result = index.find_hash(kind="loras", sha256=sha256.lower())

    assert result is not None
    assert result.backend_value == "Installed/renamed.safetensors"


def test_recipe_model_resolution_index_rejects_kind_mismatch() -> None:
    """Hash lookup must not cross model-kind boundaries."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    index = RecipeModelResolutionIndex.from_catalog(
        _Catalog((_item("vae", "same.safetensors", sha256),)),
        kinds=("vae",),
    )

    assert index.find_hash(kind="checkpoints", sha256=sha256) is None


def _item(kind: str, value: str, sha256: str | None) -> ModelCatalogItem:
    """Build one model catalog item with irrelevant presentation fields defaulted."""

    return ModelCatalogItem(
        kind=kind,
        display_name=value,
        display_subtitle=None,
        backend_value=value,
        relative_path=value,
        folder="",
        basename=value,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=value.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=value.casefold(),
        sha256=sha256,
    )
