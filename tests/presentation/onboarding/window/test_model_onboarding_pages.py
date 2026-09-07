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

"""Verify the user-facing SDXL and Anima onboarding surfaces."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    IndeterminateProgressRing,
    RadioButton,
    TransparentToolButton,
)

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
)
from sugarsubstitute_shared.localization import app_text
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelRecommendation,
)
from substitute.presentation.onboarding.model_onboarding_session import (
    ModelOnboardingSession,
)
from substitute.presentation.onboarding.onboarding_existing_model_page import (
    ExistingModelsFolderQuestionPage,
)
from substitute.presentation.onboarding.onboarding_recommendation_pages import (
    ModelRecommendationPage,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingSectionPanel,
)
from substitute.presentation.onboarding.onboarding_folder_setup_page import (
    FolderSetupPage,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from tests.support.qt.lifecycle import ensure_qt_application


def test_existing_folder_question_leaves_branch_actions_to_stable_footer() -> None:
    """Keep the focal question free of select-then-continue controls."""

    ensure_qt_application()
    question = ExistingModelsFolderQuestionPage()
    folder = FolderSetupPage()
    browse_requests: list[bool] = []
    folder.managed_model_browse_requested.connect(lambda: browse_requests.append(True))
    assert question.findChildren(OnboardingSectionPanel) == []
    assert question.findChildren(QCheckBox) == []
    assert question.content_column.maximumWidth() == 520

    folder.configure_model_picker(allow_default=True)
    folder.managed_model_browse_button.click()

    assert browse_requests == [True]
    assert not folder.managed_model_default_button.isHidden()
    folder.close()
    question.close()


def test_existing_model_question_names_supported_shared_folder_layouts() -> None:
    """Name every supported shared models-folder source without extra controls."""

    ensure_qt_application()
    existing = ExistingModelsFolderQuestionPage()
    assert existing.findChildren(RadioButton) == []
    assert existing.findChildren(OnboardingSectionPanel) == []
    assert existing.hero_panel.description_label.text() == (
        "Use an existing ComfyUI, AUTOMATIC1111 WebUI, Forge, reForge, or NeoForge "
        "models folder without moving its files."
    )
    existing.close()


def test_folder_page_exposes_one_shared_models_folder_choice() -> None:
    """Keep WebUI detection behind the single models-folder field."""

    ensure_qt_application()
    folder = FolderSetupPage()

    folder.configure_model_picker(allow_default=True)

    assert not folder.managed_model_section.isHidden()
    assert not folder.model_path_block.isHidden()
    assert not folder.output_section.isHidden()
    assert folder.findChild(QWidget, "OnboardingWebUiModelsRootEdit") is None
    assert folder.hero_panel.description_label.text() == (
        "Use the suggested models folder or choose one already used by another WebUI."
    )
    folder.close()


def test_recommendation_page_renders_centered_five_by_two_family_choices() -> None:
    """Show eight compact models plus import and bring-your-own choices."""

    ensure_qt_application()
    page = ModelRecommendationPage()
    cards = tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 9))

    page.set_recommendations(
        FamilyRecommendationPage(ModelFamilyId.SDXL, cards),
        selected_version_ids=frozenset(),
        use_own_model=False,
    )

    checkboxes = [
        checkbox
        for checkbox in page.findChildren(QCheckBox)
        if checkbox.objectName().startswith("OnboardingRecommendationSelect_")
    ]
    portraits = page.findChildren(RecommendationPortrait)
    assert len(checkboxes) == 8
    assert not any(checkbox.isChecked() for checkbox in checkboxes)
    assert all(checkbox.accessibleName() for checkbox in checkboxes)
    assert len(portraits) == 8
    assert not any(portrait.thumbnail_is_loading() for portrait in portraits)
    assert all(portrait.width() == 184 for portrait in portraits)
    assert all(portrait.height() == 200 for portrait in portraits)
    assert all(portrait.source_size().height() >= 960 for portrait in portraits)
    assert page.card_grid.count() == 10
    import_item = page.card_grid.itemAtPosition(1, 3)
    own_item = page.card_grid.itemAtPosition(1, 4)
    assert import_item is not None and import_item.widget() is page.import_card
    assert own_item is not None and own_item.widget() is page.own_model_card
    assert page.own_model_card.title_label.text() == "No thanks,\nI’ll bring my own"
    assert not bool(page.own_model_card.property("selected"))
    assert page.hero_panel.title_label.text() == "Popular Illustrious SDXL models"
    assert page.findChild(QWidget, "OnboardingRecommendationFamily") is None
    provider_buttons = [card.link_button for card in page.visible_cards()]
    assert all(isinstance(button, TransparentToolButton) for button in provider_buttons)
    assert all(not button.icon().isNull() for button in provider_buttons)
    assert all(
        bool(button.property("onboardingProviderAction")) for button in provider_buttons
    )
    assert all(
        button.cursor().shape() == Qt.CursorShape.PointingHandCursor
        for button in provider_buttons
    )
    card_text = " ".join(
        label.text() for label in page.card_host.findChildren(QLabel) if label.text()
    )
    assert "creator" not in card_text
    assert "popular this month" not in card_text
    assert "version" not in card_text
    page.close()


def test_recommendation_page_owns_provider_loading_and_recovery_states() -> None:
    """Keep CivitAI progress and failure on the page the action belongs to."""

    ensure_qt_application()
    page = ModelRecommendationPage()

    page.show_loading(ModelFamilyId.SDXL)

    assert page.current_family() is ModelFamilyId.SDXL
    loading_cards = page.card_host.findChildren(
        QFrame,
        "OnboardingRecommendationLoadingCard",
    )
    loading_rings = page.card_host.findChildren(
        IndeterminateProgressRing,
        "OnboardingRecommendationLoadingBusy",
    )
    assert len(loading_cards) == 10
    assert len(loading_rings) == 10
    assert all(not ring.isHidden() for ring in loading_rings)
    assert all(
        ring.accessibleName() == "Loading recommendations…" for ring in loading_rings
    )
    assert page.loading_row.isHidden()
    assert not page.card_host.isHidden()

    page.show_failure(
        ModelFamilyId.SDXL,
        app_text("CivitAI recommendations could not be loaded. Try again or go back."),
    )

    assert page.loading_ring.isHidden()
    assert "could not be loaded" in page.loading_status.text()
    assert page.card_host.isHidden()
    page.close()


def test_model_session_preserves_loaded_selections_and_rejects_stale_ids() -> None:
    """Keep explicit choices across pages without accepting detached card signals."""

    session = ModelOnboardingSession(
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
    )
    session.answer_existing_folder(False)
    session.select_missing_families(frozenset())
    pages = (
        FamilyRecommendationPage(ModelFamilyId.SDXL, (_card(ModelFamilyId.SDXL, 1),)),
        FamilyRecommendationPage(ModelFamilyId.ANIMA, (_card(ModelFamilyId.ANIMA, 1),)),
    )

    assert session.accept_recommendations(pages)
    assert session.set_version_selected(1010, True)
    session.set_page_index(1)
    assert not session.set_version_selected(9999, True)
    session.set_page_index(0)

    assert session.state.selected_version_ids == {1010}
    assert tuple(item.model_id for item in session.selected_recommendations()) == (101,)


def test_model_session_reuses_exact_cards_when_reentering_the_same_flow() -> None:
    """Keep model, version, image identity, order, and payload across Back/Continue."""

    session = ModelOnboardingSession(
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
    )
    session.answer_existing_folder(False)
    session.select_missing_families(frozenset())
    pages = (
        FamilyRecommendationPage(
            ModelFamilyId.SDXL,
            tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 4)),
        ),
        FamilyRecommendationPage(
            ModelFamilyId.ANIMA,
            tuple(_card(ModelFamilyId.ANIMA, rank) for rank in range(1, 4)),
        ),
    )
    assert session.accept_recommendations(pages)
    first_thumbnail = pages[0].cards[0].thumbnail
    assert first_thumbnail is not None
    assert session.accept_thumbnail(1010, first_thumbnail)
    settled_pages = session.state.recommendation_pages
    settled_identity = tuple(
        (
            card.recommendation.model_id,
            card.recommendation.version_id,
            card.recommendation.thumbnail_image_id,
            card.recommendation.thumbnail_url,
            card.thumbnail,
        )
        for page in settled_pages
        for card in page.cards
    )

    session.answer_existing_folder(False)
    assert session.select_missing_families(frozenset()) == (
        ModelFamilyId.SDXL,
        ModelFamilyId.ANIMA,
    )

    assert session.has_loaded_recommendations()
    assert session.state.recommendation_pages is settled_pages
    assert (
        tuple(
            (
                card.recommendation.model_id,
                card.recommendation.version_id,
                card.recommendation.thumbnail_image_id,
                card.recommendation.thumbnail_url,
                card.thumbnail,
            )
            for page in session.state.recommendation_pages
            for card in page.cards
        )
        == settled_identity
    )


def test_shared_model_page_versions_keep_selections_and_thumbnails_independent() -> (
    None
):
    """Never merge SDXL and Anima cards that share one CivitAI model page."""

    session = ModelOnboardingSession(
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
    )
    session.answer_existing_folder(False)
    session.select_missing_families(frozenset())
    shared_model_id = 934764
    sdxl = _card_with_identity(
        family=ModelFamilyId.SDXL,
        model_id=shared_model_id,
        version_id=2851583,
    )
    anima = _card_with_identity(
        family=ModelFamilyId.ANIMA,
        model_id=shared_model_id,
        version_id=3248362,
    )
    pages = (
        FamilyRecommendationPage(ModelFamilyId.SDXL, (sdxl,)),
        FamilyRecommendationPage(ModelFamilyId.ANIMA, (anima,)),
    )
    assert session.accept_recommendations(pages)

    assert session.set_version_selected(sdxl.recommendation.version_id, True)
    assert session.accept_thumbnail(
        anima.recommendation.version_id,
        _thumbnail(ModelFamilyId.ANIMA, 2),
    )

    state = session.state
    assert state.selected_version_ids == {sdxl.recommendation.version_id}
    assert state.recommendation_pages[0].cards[0].thumbnail is None
    assert state.recommendation_pages[1].cards[0].thumbnail is not None
    assert session.selected_recommendations() == (sdxl.recommendation,)


def test_imported_models_persist_per_family_and_join_the_editable_checkout() -> None:
    """Retain accepted CivitAI links across family navigation and review ordering."""

    session = ModelOnboardingSession(
        flow_mode=OnboardingFlowMode.FIRST_RUN,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
    )
    session.answer_existing_folder(False)
    session.select_missing_families(frozenset())
    pages = (
        FamilyRecommendationPage(
            ModelFamilyId.SDXL,
            tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 9)),
        ),
        FamilyRecommendationPage(
            ModelFamilyId.ANIMA,
            tuple(_card(ModelFamilyId.ANIMA, rank) for rank in range(1, 9)),
        ),
    )
    assert session.accept_recommendations(pages)
    imported = _card_with_identity(
        family=ModelFamilyId.SDXL,
        model_id=999,
        version_id=9990,
    )

    assert session.replace_current_family_imports((imported,))
    session.set_page_index(1)
    session.set_page_index(0)

    assert session.state.recommendation_pages[0].imported_cards == (imported,)
    assert session.state.recommendation_pages[1].imported_cards == ()
    assert session.state.selected_version_ids == {9990}
    assert session.selected_cards() == (imported,)


def _card(family: ModelFamilyId, rank: int) -> RecommendationCardAsset:
    """Return one Qt-ready deterministic recommendation card."""

    model_id = (100 if family is ModelFamilyId.SDXL else 200) + rank
    return RecommendationCardAsset(
        recommendation=ModelRecommendation(
            family_id=family,
            model_id=model_id,
            version_id=model_id * 10,
            model_name=f"{family.value} model {rank}",
            version_name=f"v{rank}",
            creator="creator",
            file_name=f"model-{rank}.safetensors",
            size_bytes=2 * 1024**3,
            sha256=f"{model_id:064x}",
            download_url=f"https://civitai.com/api/download/models/{model_id * 10}",
            model_page_url=f"https://civitai.com/models/{model_id}",
            thumbnail_image_id=model_id * 100,
            thumbnail_url=f"https://image.civitai.com/{model_id}.png",
            popularity_rank=rank,
        ),
        thumbnail=_thumbnail(family, rank),
    )


def _card_with_identity(
    *,
    family: ModelFamilyId,
    model_id: int,
    version_id: int,
) -> RecommendationCardAsset:
    """Return a pending card with explicit provider model and version identity."""

    return RecommendationCardAsset(
        recommendation=ModelRecommendation(
            family_id=family,
            model_id=model_id,
            version_id=version_id,
            model_name="Shared model page",
            version_name=f"version-{version_id}",
            creator="creator",
            file_name=f"model-{version_id}.safetensors",
            size_bytes=2 * 1024**3,
            sha256=f"{version_id:064x}",
            download_url=f"https://civitai.com/api/download/models/{version_id}",
            model_page_url=(
                f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
            ),
            thumbnail_image_id=version_id * 10,
            thumbnail_url=f"https://image.civitai.com/{version_id}.png",
            popularity_rank=1,
        )
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
