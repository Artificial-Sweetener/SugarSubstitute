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

"""Verify model-family identity, order, and extension contracts."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import render_application_text
from sugarsubstitute_shared.model_discovery import ModelArtifactKind

from substitute.application.model_recommendations import model_family_presentation
from substitute.domain.model_recommendations import (
    CivitaiFamilyMapping,
    FamilyDetectionPolicy,
    ModelFamilyDefinition,
    ModelFamilyId,
    ModelRecommendationQuery,
    ModelStylePreference,
    SUPPORTED_MODEL_FAMILIES,
    SupportedModelFamilyCatalog,
)


def test_supported_families_have_exact_product_order_and_provider_mappings() -> None:
    """Keep SDXL first and Anima second with exact CivitAI base-model values."""

    families = SUPPORTED_MODEL_FAMILIES.families()

    assert [family.family_id for family in families] == [
        ModelFamilyId.SDXL,
        ModelFamilyId.ANIMA,
    ]
    assert [family.civitai.recommendation_base_model for family in families] == [
        "Illustrious",
        "Anima",
    ]
    assert all(family.civitai.model_type == "Checkpoint" for family in families)
    assert families[0].primary_artifact_kind is ModelArtifactKind.CHECKPOINTS
    assert families[1].primary_artifact_kind is ModelArtifactKind.DIFFUSION_MODELS
    assert SUPPORTED_MODEL_FAMILIES.missing_from(frozenset({ModelFamilyId.SDXL})) == (
        ModelFamilyId.ANIMA,
    )
    assert (
        render_application_text(model_family_presentation(families[0].family_id).name)
        == "SDXL"
    )
    assert (
        render_application_text(model_family_presentation(families[1].family_id).name)
        == "Anima"
    )


def test_family_identity_is_not_an_artifact_kind() -> None:
    """Prevent storage roles from becoming product-facing family choices again."""

    family_values = {family.value for family in ModelFamilyId}
    artifact_values = {artifact.value for artifact in ModelArtifactKind}

    assert family_values.isdisjoint(artifact_values)


def test_styles_do_not_change_family_identity() -> None:
    """Keep creative preferences as independent recommendation facets."""

    query = ModelRecommendationQuery(
        family_id=ModelFamilyId.ANIMA,
        styles=frozenset(
            {ModelStylePreference.ILLUSTRATION, ModelStylePreference.ANIME_STYLE}
        ),
    )

    assert query.family_id is ModelFamilyId.ANIMA
    assert ModelStylePreference.ANIME_STYLE in query.styles


def test_future_family_is_a_catalog_definition_not_a_page_type() -> None:
    """Admit future catalog additions without changing flow structure."""

    future = ModelFamilyDefinition(
        family_id=ModelFamilyId.FLUX_2,
        catalog_order=30,
        civitai=CivitaiFamilyMapping("Flux.2 D", "Checkpoint"),
        detection=FamilyDetectionPolicy(
            ModelArtifactKind.DIFFUSION_MODELS,
            frozenset({"flux.2"}),
            ("model.diffusion_model.double_blocks.",),
        ),
        primary_artifact_kind=ModelArtifactKind.DIFFUSION_MODELS,
    )

    catalog = SupportedModelFamilyCatalog((future,))

    assert catalog.families() == (future,)
