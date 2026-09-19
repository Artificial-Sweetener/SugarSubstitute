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

"""Verify contained model-link import and reusable family presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QWidget

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
    RecommendationLinkResult,
    RecommendationLinkStatus,
    model_family_presentation,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import ModelFamilyId, ModelRecommendation
from substitute.presentation.onboarding.onboarding_recommendation_pages import (
    ModelRecommendationPage,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from tests.support.qt.lifecycle import ensure_qt_application


def test_civitai_import_is_a_contained_installer_overlay_not_a_window() -> None:
    """Keep model-link onboarding inside the current installer surface."""

    application = ensure_qt_application()
    host = QWidget()
    host.resize(960, 640)
    page = ModelRecommendationPage(host)
    page.set_recommendations(
        FamilyRecommendationPage(
            ModelFamilyId.ANIMA,
            tuple(_card(ModelFamilyId.ANIMA, rank) for rank in range(1, 9)),
        ),
        selected_version_ids=frozenset(),
        use_own_model=False,
    )
    host.show()
    browse_urls: list[str] = []
    page.link_requested.connect(browse_urls.append)
    page.import_card.activated.emit()
    application.processEvents()

    overlay = page._import_overlay
    assert overlay is not None
    assert overlay.parent() is host
    assert overlay.geometry() == host.rect()
    assert host.rect().contains(overlay.panel.geometry())
    assert not overlay.isWindow()
    assert host.findChildren(QDialog) == []
    assert "community-made image models" in overlay.description_label.text()
    overlay.browse_button.click()
    assert browse_urls == [
        "https://civitai.com/search/models?baseModel=Anima&modelType=Checkpoint"
    ]
    host.close()


def test_civitai_import_previews_remove_models_and_summarizes_them_in_card_nine() -> (
    None
):
    """Preview accepted identities and keep individual removal inside the workflow."""

    application = ensure_qt_application()
    host = QWidget()
    host.resize(960, 640)
    page = ModelRecommendationPage(host)
    curated = tuple(_card(ModelFamilyId.ANIMA, rank) for rank in range(1, 9))
    imported = RecommendationCardAsset(
        _recommendation(
            family=ModelFamilyId.ANIMA,
            model_id=999,
            version_id=9990,
        ),
        thumbnail=_thumbnail(ModelFamilyId.ANIMA, 9),
    )
    page.set_recommendations(
        FamilyRecommendationPage(ModelFamilyId.ANIMA, curated),
        selected_version_ids=frozenset(),
        use_own_model=False,
    )
    host.show()
    page.import_card.activated.emit()
    application.processEvents()
    overlay = page._import_overlay
    assert overlay is not None

    overlay.show_checking()
    assert not overlay.check_button.isEnabled()
    overlay.set_results(
        (
            RecommendationLinkResult(
                source_url=imported.recommendation.model_page_url,
                status=RecommendationLinkStatus.READY,
                card=imported,
            ),
        )
    )
    assert overlay.check_button.isEnabled()
    assert overlay.findChild(QWidget, "OnboardingModelLinkReadyRow") is not None
    assert "Compatible with this model family" not in {
        label.text() for label in overlay.findChildren(QLabel)
    }
    remove = overlay.findChild(QWidget, "OnboardingModelLinkRemove_9990")
    assert remove is not None
    QTest.mouseClick(remove, Qt.MouseButton.LeftButton)
    application.processEvents()
    assert not overlay.add_button.isEnabled()

    page.set_recommendations(
        FamilyRecommendationPage(
            ModelFamilyId.ANIMA,
            curated,
            imported_cards=(imported,),
        ),
        selected_version_ids=frozenset({9990}),
        use_own_model=False,
    )
    assert page.import_card.title_label.text() == "1 model added"
    assert not page.import_card.preview_mosaic.isHidden()
    assert page.import_card.icon.isHidden()
    assert len(page.visible_cards()) == 8

    accepted: list[tuple[RecommendationCardAsset, ...]] = []
    overlay.models_accepted.connect(accepted.append)
    overlay.open_for(
        ModelFamilyId.ANIMA,
        model_family_presentation(ModelFamilyId.ANIMA),
        (imported,),
    )
    remove_existing = overlay.findChild(
        QWidget,
        "OnboardingModelLinkRemove_9990",
    )
    assert remove_existing is not None
    QTest.mouseClick(remove_existing, Qt.MouseButton.LeftButton)
    assert overlay.add_button.isEnabled()
    assert overlay.add_button.text() == "Save changes"
    QTest.mouseClick(overlay.add_button, Qt.MouseButton.LeftButton)
    assert accepted == [()]
    host.close()


def test_recommendation_page_reuses_family_copy_for_future_catalog_entries() -> None:
    """Keep the ten-choice composition reusable beyond the first two families."""

    ensure_qt_application()
    page = ModelRecommendationPage()
    page.set_recommendations(
        FamilyRecommendationPage(
            ModelFamilyId.FLUX_2,
            tuple(_card(ModelFamilyId.FLUX_2, rank) for rank in range(1, 9)),
        ),
        selected_version_ids=frozenset(),
        use_own_model=False,
    )

    assert page.card_grid.count() == 10
    assert page.hero_panel.title_label.text() == "Popular FLUX.2 models"
    assert page.findChild(QWidget, "OnboardingRecommendationFamily") is None
    assert page.own_model_card.title_label.text() == "No thanks,\nI’ll bring my own"
    page.close()


def test_recommendation_choices_are_keyboard_operable() -> None:
    """Toggle portrait model choices with the keyboard through native controls."""

    application = ensure_qt_application()
    recommendations = ModelRecommendationPage()
    recommendations.set_recommendations(
        FamilyRecommendationPage(
            ModelFamilyId.ANIMA,
            tuple(_card(ModelFamilyId.ANIMA, rank) for rank in range(1, 4)),
        ),
        selected_version_ids=frozenset(),
        use_own_model=False,
    )
    recommendations.show()
    choice = recommendations.findChild(
        QCheckBox,
        "OnboardingRecommendationSelect_2010",
    )
    assert choice is not None
    choice.setFocus()
    QTest.keyClick(choice, Qt.Key.Key_Space)
    application.processEvents()

    assert choice.isChecked()
    assert "anima" in choice.accessibleName().casefold()
    recommendations.close()


def test_recommendation_no_download_path_is_a_selection_not_an_action_button() -> None:
    """Keep the provide-my-own path inside the choice model and out of page actions."""

    ensure_qt_application()
    page = ModelRecommendationPage()
    page.set_recommendations(
        FamilyRecommendationPage(
            ModelFamilyId.SDXL,
            tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 4)),
        ),
        selected_version_ids=frozenset(),
        use_own_model=True,
    )

    assert bool(page.own_model_card.property("selected"))
    assert page.findChild(QWidget, "OnboardingRecommendationSkipButton") is None
    assert page.findChild(QWidget, "OnboardingFindOwnModelsButton") is None
    page.close()


def test_recommendation_cards_show_immediately_while_thumbnails_load() -> None:
    """Keep all choices usable while each portrait image arrives independently."""

    ensure_qt_application()
    page = ModelRecommendationPage()
    loaded_cards = tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 4))
    pending_cards = tuple(
        RecommendationCardAsset(card.recommendation) for card in loaded_cards
    )

    page.set_recommendations(
        FamilyRecommendationPage(ModelFamilyId.SDXL, pending_cards),
        selected_version_ids=frozenset(),
        use_own_model=False,
    )

    portraits = page.findChildren(RecommendationPortrait)
    first_thumbnail = loaded_cards[0].thumbnail
    assert first_thumbnail is not None
    assert len(portraits) == 3
    assert all(portrait.thumbnail_is_loading() for portrait in portraits)
    assert all(not portrait.loading_label.isHidden() for portrait in portraits)
    assert all(portrait.source_size().isEmpty() for portrait in portraits)
    assert page.set_thumbnail(1010, first_thumbnail)
    assert not portraits[0].thumbnail_is_loading()
    assert portraits[0].loading_label.isHidden()
    assert portraits[0].source_size().height() >= 960
    assert page.set_thumbnail_unavailable(1020)
    assert portraits[1].thumbnail_is_unavailable()
    assert portraits[1].loading_label.isHidden()
    assert portraits[2].thumbnail_is_loading()
    assert page.card_grid.count() == 10
    page.close()


def _card(family: ModelFamilyId, rank: int) -> RecommendationCardAsset:
    """Return one Qt-ready deterministic recommendation card."""

    model_id = (100 if family is ModelFamilyId.SDXL else 200) + rank
    return RecommendationCardAsset(
        _recommendation(
            family=family,
            model_id=model_id,
            version_id=model_id * 10,
            rank=rank,
        ),
        thumbnail=_thumbnail(family, rank),
    )


def _recommendation(
    *,
    family: ModelFamilyId,
    model_id: int,
    version_id: int,
    rank: int = 1,
) -> ModelRecommendation:
    """Return one recommendation with explicit provider identity."""

    return ModelRecommendation(
        family_id=family,
        model_id=model_id,
        version_id=version_id,
        model_name=f"{family.value} model {rank}",
        version_name=f"v{rank}",
        creator="creator",
        file_name=f"model-{rank}.safetensors",
        size_bytes=2 * 1024**3,
        sha256=f"{version_id:064x}",
        download_url=f"https://civitai.com/api/download/models/{version_id}",
        model_page_url=f"https://civitai.com/models/{model_id}",
        thumbnail_image_id=model_id * 100,
        thumbnail_url=f"https://image.civitai.com/{model_id}.png",
        popularity_rank=rank,
    )


def _thumbnail(family: ModelFamilyId, rank: int) -> ThumbnailAsset:
    """Return one valid Qt thumbnail asset."""

    image = QImage(800, 1200, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#6C5CE7" if family is ModelFamilyId.SDXL else "#00B894"))
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=f"test:{family.value}:{rank}",
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )
