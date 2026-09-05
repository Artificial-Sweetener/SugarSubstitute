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

"""Verify onboarding model-decision session behavior."""

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
)
from substitute.domain.model_recommendations import ModelFamilyId, ModelRecommendation
from substitute.presentation.onboarding.model_onboarding_session import (
    ModelOnboardingSession,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingFlowMode,
    OnboardingTargetMode,
)


def test_model_session_keeps_download_and_provide_my_own_choices_exclusive() -> None:
    """Persist one coherent family decision while moving backward and forward."""

    session = _session()
    pages = (
        FamilyRecommendationPage(ModelFamilyId.SDXL, (_card(ModelFamilyId.SDXL),)),
        FamilyRecommendationPage(ModelFamilyId.ANIMA, (_card(ModelFamilyId.ANIMA),)),
    )
    assert session.accept_recommendations(pages)

    session.set_current_family_declined(True)
    assert session.current_family_is_declined()
    assert not session.current_family_has_selection()

    assert session.set_version_selected(1010, True)
    assert session.current_family_has_selection()
    assert not session.current_family_is_declined()

    session.set_current_family_declined(True)
    assert not session.current_family_has_selection()
    assert session.current_family_is_declined()


def test_model_session_rejects_stale_family_page_order() -> None:
    """Never populate a changed family selection with an older async result."""

    session = _session()
    session.select_missing_families(frozenset({ModelFamilyId.SDXL}))

    accepted = session.accept_recommendations(
        (FamilyRecommendationPage(ModelFamilyId.SDXL, ()),)
    )

    assert not accepted
    assert session.state.recommendation_pages == ()


def _session() -> ModelOnboardingSession:
    """Return a session positioned at model recommendations."""

    session = ModelOnboardingSession(
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
    )
    session.answer_existing_folder(False)
    session.select_missing_families(frozenset())
    return session


def _card(family: ModelFamilyId) -> RecommendationCardAsset:
    """Return one deterministic recommendation card."""

    model_id = 101 if family is ModelFamilyId.SDXL else 201
    return RecommendationCardAsset(
        recommendation=ModelRecommendation(
            family_id=family,
            model_id=model_id,
            version_id=model_id * 10,
            model_name=f"{family.value} model",
            version_name="v1",
            creator="creator",
            file_name="model.safetensors",
            size_bytes=2 * 1024**3,
            sha256=f"{model_id:064x}",
            download_url=f"https://civitai.com/api/download/models/{model_id * 10}",
            model_page_url=f"https://civitai.com/models/{model_id}",
            thumbnail_image_id=model_id * 100,
            thumbnail_url=f"https://image.civitai.com/{model_id}.png",
            popularity_rank=1,
        )
    )
