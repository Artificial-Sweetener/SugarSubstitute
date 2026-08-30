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

"""Contract tests for checkpoint model-family resolution."""

from __future__ import annotations

from substitute.application.model_metadata import (
    ModelCatalogItem,
    model_family_associations_for_catalog_item,
    resolve_model_families_for_catalog_item,
)
from substitute.domain.user_presets import UserPresetAssociationScope


def test_base_model_sdxl_resolves_sdxl_family() -> None:
    """SDXL base metadata should resolve to the broad SDXL family."""

    families = resolve_model_families_for_catalog_item(_item(base_model="SDXL"))

    assert [(family.key, family.label) for family in families] == [("sdxl", "SDXL")]


def test_base_model_sdxl_version_resolves_sdxl_family() -> None:
    """SDXL 1.0 base metadata should normalize to the SDXL family."""

    families = resolve_model_families_for_catalog_item(_item(base_model="SDXL 1.0"))

    assert [(family.key, family.label) for family in families] == [("sdxl", "SDXL")]


def test_base_model_illustrious_resolves_illustrious_family() -> None:
    """Illustrious base metadata should resolve to the Illustrious family."""

    families = resolve_model_families_for_catalog_item(_item(base_model="Illustrious"))

    assert [(family.key, family.label) for family in families] == [
        ("illustrious", "Illustrious")
    ]


def test_base_model_anima_resolves_anima_family() -> None:
    """Anima metadata should resolve the family used by diffusion-model presets."""

    families = resolve_model_families_for_catalog_item(_item(base_model="Anima"))

    assert [(family.key, family.label) for family in families] == [("anima", "Anima")]


def test_display_name_noobai_resolves_when_base_model_is_missing() -> None:
    """Provider display names should resolve curated families when base is absent."""

    families = resolve_model_families_for_catalog_item(
        _item(display_name="NoobAI XL vPred", base_model=None)
    )

    assert [(family.key, family.label) for family in families] == [("noobai", "NoobAI")]


def test_display_name_noobai_resolves_when_base_model_is_broad() -> None:
    """Specific display-name families should supplement broad base metadata."""

    families = resolve_model_families_for_catalog_item(
        _item(display_name="Noob AI XL", base_model="SDXL")
    )

    family_pairs = [(family.key, family.label) for family in families]
    assert ("sdxl", "SDXL") in family_pairs
    assert ("noobai", "NoobAI") in family_pairs


def test_unknown_metadata_returns_no_family() -> None:
    """Unknown checkpoint metadata should not create speculative families."""

    assert resolve_model_families_for_catalog_item(_item(display_name="Other")) == ()


def test_family_associations_use_model_family_scope_and_civitai_provider() -> None:
    """Preset associations should use family keys rather than version ids."""

    associations = model_family_associations_for_catalog_item(
        _item(base_model="Illustrious")
    )

    assert len(associations) == 1
    assert associations[0].scope is UserPresetAssociationScope.MODEL_FAMILY
    assert associations[0].provider == "civitai"
    assert associations[0].key == "illustrious"
    assert associations[0].label == "Illustrious"


def _item(
    *,
    display_name: str = "Example",
    base_model: str | None = None,
    tags: tuple[str, ...] = (),
) -> ModelCatalogItem:
    """Return one model catalog item for resolver tests."""

    return ModelCatalogItem(
        kind="checkpoints",
        display_name=display_name,
        display_subtitle=None,
        backend_value="models/example.safetensors",
        relative_path="models/example.safetensors",
        folder="models",
        basename="example",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=base_model,
        trained_words=(),
        tags=tags,
        model_page_url=None,
        collision_key="example",
        collision_count=1,
        has_collision=False,
        search_text=display_name,
    )
