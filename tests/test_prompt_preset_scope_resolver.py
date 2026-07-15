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

"""Contract tests for prompt preset scope resolution from model metadata."""

from __future__ import annotations

from substitute.application.model_metadata import (
    ModelCatalogItem,
    exact_model_association_for_catalog_item,
    prompt_preset_listing_associations_for_catalog_item,
    prompt_preset_scope_options_for_catalog_item,
)
from substitute.domain.user_presets import (
    GLOBAL_PRESET_ASSOCIATION,
    UserPresetAssociationScope,
)


def test_scope_options_include_global_family_and_provider_version() -> None:
    """Prompt scope options should prefer CivitAI model-version identity."""

    options = prompt_preset_scope_options_for_catalog_item(
        _item(
            display_name="Wrong Long Provider Name",
            display_subtitle="Version Alpha",
            base_model="Illustrious",
            provider_name="civitai",
            provider_model_id="100",
            provider_model_version_id="200",
        ),
        model_kind="checkpoints",
    )

    assert [option.title for option in options] == [
        "Global",
        "Illustrious",
        "Checkpoint",
    ]
    assert options[1].full_label == "Base model: Illustrious"
    assert (
        options[2].full_label == "Checkpoint: Wrong Long Provider Name - Version Alpha"
    )
    assert options[2].association.scope is (
        UserPresetAssociationScope.PROVIDER_MODEL_VERSION
    )
    assert options[2].association.provider == "civitai"
    assert options[2].association.key == "200"


def test_listing_associations_are_specific_to_broad() -> None:
    """Menu listing should request exact, family, then global presets."""

    associations = prompt_preset_listing_associations_for_catalog_item(
        _item(
            base_model="Illustrious",
            provider_name="civitai",
            provider_model_version_id="200",
        )
    )

    assert [association.scope for association in associations] == [
        UserPresetAssociationScope.PROVIDER_MODEL_VERSION,
        UserPresetAssociationScope.MODEL_FAMILY,
        UserPresetAssociationScope.GLOBAL,
    ]


def test_exact_checkpoint_scope_falls_back_to_local_model_key() -> None:
    """Provider-less checkpoints should still have a stable local exact scope."""

    association = exact_model_association_for_catalog_item(
        _item(backend_value=r"models\local.safetensors", provider_name=None)
    )

    assert association is not None
    assert association.scope is UserPresetAssociationScope.LOCAL_MODEL
    assert association.provider == "local"
    assert association.key == "models/local.safetensors"


def test_scope_options_without_checkpoint_still_include_global() -> None:
    """The save dialog should always have a global option."""

    options = prompt_preset_scope_options_for_catalog_item(None, model_kind=None)

    assert len(options) == 1
    assert options[0].association == GLOBAL_PRESET_ASSOCIATION


def test_diffusion_model_scope_uses_accurate_exact_model_label() -> None:
    """Standalone diffusion models should not be labeled as checkpoints."""

    options = prompt_preset_scope_options_for_catalog_item(
        _item(),
        model_kind="diffusion_models",
    )

    assert options[-1].title == "Diffusion model"
    assert options[-1].full_label == "Diffusion model: Example"


def _item(
    *,
    display_name: str = "Example",
    display_subtitle: str | None = None,
    backend_value: str = "models/example.safetensors",
    relative_path: str | None = None,
    base_model: str | None = None,
    provider_name: str | None = None,
    provider_model_id: str | None = None,
    provider_model_version_id: str | None = None,
) -> ModelCatalogItem:
    """Return one model catalog item for prompt scope tests."""

    resolved_relative_path = (
        relative_path if relative_path is not None else backend_value
    )
    return ModelCatalogItem(
        kind="checkpoints",
        display_name=display_name,
        display_subtitle=display_subtitle,
        backend_value=backend_value,
        relative_path=resolved_relative_path,
        folder="models",
        basename="example",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=base_model,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key="example",
        collision_count=1,
        has_collision=False,
        search_text=display_name,
        provider_name=provider_name,
        provider_model_id=provider_model_id,
        provider_model_version_id=provider_model_version_id,
        provider_model_name=display_name if provider_name is not None else None,
        provider_model_version_name=display_subtitle,
    )
