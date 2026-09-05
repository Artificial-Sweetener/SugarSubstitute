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

"""Capture exact live model-card identity and rendered recommendation evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtWidgets import QApplication

from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.onboarding import OnboardingWindow
from substitute.presentation.onboarding.onboarding_recommendation_pages import (
    RecommendationPortrait,
)
from tools.install_experience_capture import (
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)
from tools.install_experience_navigation import (
    click_installer_control,
    wait_for_installer_condition,
    wait_for_installer_page,
)


def capture_live_recommendation_page(*, artifact_root: Path) -> dict[str, object]:
    """Capture recommendation loading, settlement, revisit, and family identity."""

    from tools.install_experience_onboarding import OnboardingCheckSession

    session = OnboardingCheckSession(
        install_root=artifact_root / "live-civitai" / "synthetic-install",
        install_root_locked=True,
        live_model_discovery=True,
    )
    window = session.window
    prepare_opaque_dark_capture_surface(window)
    window.show()
    QApplication.processEvents()
    try:
        wait_for_installer_page(window, "OnboardingTargetModePage")
        click_installer_control(window, "OnboardingPrimaryButton")
        wait_for_installer_page(window, "OnboardingManagedLocalPage")
        click_installer_control(window, "OnboardingPrimaryButton")
        wait_for_installer_page(window, "OnboardingExistingModelsQuestionPage")
        click_installer_control(window, "OnboardingNoExistingModelsButton")
        wait_for_installer_page(window, "OnboardingModelRecommendationPage")
        wait_for_installer_condition(
            lambda: len(window.model_recommendation_page.visible_cards()) == 3,
            description="three live CivitAI recommendation cards",
            timeout_seconds=30.0,
        )
        QApplication.processEvents()
        portraits = window.model_recommendation_page.findChildren(
            RecommendationPortrait
        )
        loading_path = artifact_root / "live-civitai" / "loading.png"
        loading_path.parent.mkdir(parents=True, exist_ok=True)
        save_opaque_dark_widget_capture(window, loading_path)
        wait_for_installer_condition(
            lambda: all(
                card.thumbnail is not None or card.thumbnail_failed
                for page in session.controller.model_session.state.recommendation_pages
                for card in page.cards
            ),
            description="all live CivitAI recommendation thumbnails",
            timeout_seconds=90.0,
        )
        settled_path = artifact_root / "live-civitai" / "settled.png"
        save_opaque_dark_widget_capture(window, settled_path)
        state = session.controller.model_session.state
        settled_pages = state.recommendation_pages
        settled_identity = recommendation_identity(window)
        recommendation_page = state.recommendation_pages[
            state.recommendation_page_index
        ]
        click_installer_control(window, "OnboardingBackButton")
        wait_for_installer_page(window, "OnboardingExistingModelsQuestionPage")
        click_installer_control(window, "OnboardingNoExistingModelsButton")
        wait_for_installer_page(window, "OnboardingModelRecommendationPage")
        wait_for_installer_condition(
            lambda: all(
                not card.portrait.thumbnail_is_loading()
                for card in window.model_recommendation_page.visible_cards()
            ),
            description="stable revisited CivitAI recommendation thumbnails",
        )
        if (
            session.controller.model_session.state.recommendation_pages
            is not settled_pages
            or recommendation_identity(window) != settled_identity
        ):
            raise RuntimeError(
                "Back/Continue changed a settled live CivitAI recommendation."
            )
        revisit_path = artifact_root / "live-civitai" / "settled-revisit.png"
        save_opaque_dark_widget_capture(window, revisit_path)
        click_installer_control(window, "OnboardingRecommendationSkipButton")
        wait_for_installer_condition(
            lambda: (
                window.model_recommendation_page.current_family() is ModelFamilyId.ANIMA
            ),
            description="live Anima recommendation page",
        )
        wait_for_installer_condition(
            lambda: all(
                not card.portrait.thumbnail_is_loading()
                for card in window.model_recommendation_page.visible_cards()
            ),
            description="settled live Anima recommendation thumbnails",
            timeout_seconds=90.0,
        )
        anima_path = artifact_root / "live-civitai" / "anima-settled.png"
        save_opaque_dark_widget_capture(window, anima_path)
        anima_page = session.controller.model_session.state.recommendation_pages[1]
        anima_portraits = tuple(
            card.portrait for card in window.model_recommendation_page.visible_cards()
        )
        return {
            "family": recommendation_page.family_id.value,
            "models": [_card_identity(card) for card in recommendation_page.cards[:3]],
            "loading_screenshot": str(loading_path),
            "settled_screenshot": str(settled_path),
            "revisited_screenshot": str(revisit_path),
            "anima_models": [_card_identity(card) for card in anima_page.cards[:3]],
            "anima_screenshot": str(anima_path),
            "source_heights": [
                portrait.source_size().height() for portrait in portraits
            ],
            "anima_source_heights": [
                portrait.source_size().height() for portrait in anima_portraits
            ],
            "side_effect_audit": session.audit.forbidden_counts(),
        }
    finally:
        session.close()
        QApplication.processEvents()


def recommendation_identity(window: OnboardingWindow) -> tuple[object, ...]:
    """Return exact provider and image bytes retained across page navigation."""

    return tuple(
        (
            page.family_id,
            card.recommendation.model_id,
            card.recommendation.version_id,
            card.recommendation.thumbnail_image_id,
            card.recommendation.thumbnail_url,
            None if card.thumbnail is None else card.thumbnail.storage_key,
            (
                None
                if card.thumbnail is None
                else hashlib.sha256(card.thumbnail.payload).hexdigest()
            ),
        )
        for page in window._controller.model_session.state.recommendation_pages
        for card in page.cards
    )


def _card_identity(card: RecommendationCardAsset) -> dict[str, object]:
    """Return user-visible provider identity for one recommendation card state."""

    recommendation = card.recommendation
    return {
        "model_name": recommendation.model_name,
        "version_id": recommendation.version_id,
        "thumbnail_image_id": recommendation.thumbnail_image_id,
        "thumbnail_url": recommendation.thumbnail_url,
    }


__all__ = ["capture_live_recommendation_page", "recommendation_identity"]
