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

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    IndeterminateProgressRing,
    RadioButton,
)

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind
from sugarsubstitute_shared.localization import app_text
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelInstallFile,
    ModelInstallPlan,
    ModelRecommendation,
)
from substitute.presentation.onboarding.model_onboarding_session import (
    ModelOnboardingSession,
)
from substitute.presentation.onboarding.onboarding_existing_model_page import (
    ExistingModelsFolderQuestionPage,
)
from substitute.presentation.onboarding.onboarding_model_download_review_page import (
    DownloadCartCard,
    ModelDownloadReviewPage,
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
from substitute.presentation.onboarding.onboarding_preference_pages import (
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

    folder.set_model_picker_visible(True, allow_default=False)
    folder.managed_model_browse_button.click()

    assert browse_requests == [True]
    assert folder.managed_model_default_button.isHidden()
    folder.close()
    question.close()


def test_existing_model_question_copy_does_not_assume_comfyui_layout() -> None:
    """Describe a neutral existing models folder for future linked layouts."""

    ensure_qt_application()
    existing = ExistingModelsFolderQuestionPage()
    assert existing.findChildren(RadioButton) == []
    assert existing.findChildren(OnboardingSectionPanel) == []
    assert "ComfyUI models folder" not in existing.hero_panel.description_label.text()
    existing.close()


def test_no_existing_models_removes_entire_model_folder_section() -> None:
    """Reflow the folder page to output-only content without an orphan panel."""

    ensure_qt_application()
    folder = FolderSetupPage()

    folder.set_model_picker_visible(False, allow_default=False)

    assert folder.managed_model_section.isHidden()
    assert folder.model_path_block.isHidden()
    assert not folder.output_section.isHidden()
    assert folder.hero_panel.description_label.text() == (
        "Substitute saves finished images here. The default keeps them with your "
        "Substitute files."
    )
    folder.close()


def test_recommendation_page_renders_three_large_portrait_cards_and_own_model_choice() -> (
    None
):
    """Show three portrait cards and one coherent provide-your-own choice."""

    ensure_qt_application()
    page = ModelRecommendationPage()
    cards = tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 4))

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
    assert len(checkboxes) == 3
    assert not any(checkbox.isChecked() for checkbox in checkboxes)
    assert all(checkbox.accessibleName() for checkbox in checkboxes)
    assert len(portraits) == 3
    assert not any(portrait.thumbnail_is_loading() for portrait in portraits)
    assert all(portrait.width() * 5 == portrait.height() * 4 for portrait in portraits)
    assert all(portrait.source_size().height() >= 960 for portrait in portraits)
    assert page.own_model_checkbox.text() == "I'll provide my own SDXL model"
    assert not page.own_model_checkbox.isChecked()
    assert "Illustrious" in page.family_label.text()
    card_text = " ".join(
        label.text() for label in page.card_host.findChildren(QLabel) if label.text()
    )
    assert "creator" not in card_text
    assert "popular this month" not in card_text
    assert "version" not in card_text
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

    assert page.own_model_checkbox.isChecked()
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
    assert len(loading_cards) == 3
    assert len(loading_rings) == 3
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
    assert page.own_model_choice.isHidden()
    page.close()


def test_download_review_is_an_editable_thumbnail_cart() -> None:
    """Present selected models as removable exact-thumbnail checkout cards."""

    ensure_qt_application()
    page = ModelDownloadReviewPage()
    model_root = Path("E:/models")
    plan = ModelInstallPlan(
        model_root=model_root,
        files=(
            _install_file(
                display_name="One obsession",
                file_name="oneObsession_v24.safetensors",
                size_bytes=6_500_000_000,
                destination_dir=model_root / "checkpoints",
            ),
        ),
        available_bytes=244_800_000_000,
    )

    card = _card(ModelFamilyId.SDXL, 1)
    page.set_plan(plan, (card,))

    rows = page.findChildren(DownloadCartCard)
    visible_text = " ".join(
        label.text() for label in page.findChildren(QLabel) if label.text()
    )
    assert len(rows) == 1
    assert "Required components" not in visible_text
    assert "E:/models" not in visible_text
    assert "E:\\models" not in visible_text
    assert page.summary_panel.total_label.text() == "6.1 GiB"
    assert not page.summary_panel.isHidden()
    page.close()


def test_two_model_checkout_centers_cards_and_portraits_without_overflow() -> None:
    """Keep the common two-model cart centered and internally aligned."""

    application = ensure_qt_application()
    page = ModelDownloadReviewPage()
    page.resize(980, 520)
    model_root = Path("E:/models")
    plan = ModelInstallPlan(
        model_root=model_root,
        files=(
            _install_file(
                display_name="One obsession",
                file_name="oneObsession_v24.safetensors",
                size_bytes=6_500_000_000,
                destination_dir=model_root / "checkpoints",
            ),
            _install_file(
                family=ModelFamilyId.ANIMA,
                model_id=201,
                version_id=2010,
                display_name="Anima",
                file_name="anima.safetensors",
                size_bytes=3_900_000_000,
                destination_dir=model_root / "diffusion_models",
            ),
        ),
        available_bytes=244_800_000_000,
    )
    page.set_plan(
        plan,
        (
            _card(ModelFamilyId.SDXL, 1),
            _card(ModelFamilyId.ANIMA, 1),
        ),
    )
    page.show()
    application.processEvents()

    cards = page.findChildren(DownloadCartCard)
    assert len(cards) == 2
    for card in cards:
        card_center = card.mapToGlobal(card.rect().center()).x()
        portrait_center = card.portrait.mapToGlobal(card.portrait.rect().center()).x()
        assert abs(card_center - portrait_center) <= 1
    cards_left = cards[0].mapToGlobal(cards[0].rect().topLeft()).x()
    cards_right = cards[-1].mapToGlobal(cards[-1].rect().topRight()).x()
    card_group_center = (cards_left + cards_right) // 2
    page_center = page.mapToGlobal(page.rect().center()).x()
    assert abs(card_group_center - page_center) <= 1
    assert page.sizeHint().height() <= 520
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


def _install_file(
    *,
    family: ModelFamilyId = ModelFamilyId.SDXL,
    model_id: int = 101,
    version_id: int = 1010,
    display_name: str,
    file_name: str,
    size_bytes: int,
    destination_dir: Path,
) -> ModelInstallFile:
    """Return one exact planned file for download-review presentation tests."""

    return ModelInstallFile(
        family_id=family,
        artifact_kind=ModelArtifactKind.CHECKPOINTS,
        model_id=model_id,
        version_id=version_id,
        display_name=display_name,
        file_name=file_name,
        source_url="https://example.invalid/model",
        sha256="0" * 64,
        size_bytes=size_bytes,
        destination_dir=destination_dir,
    )
