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

"""Verify compact model-download review cards, totals, and viewport fit."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel, QWidget

from sugarsubstitute_shared.model_discovery import ModelArtifactKind
from sugarsubstitute_shared.presentation.localization import render_application_text
from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelInstallFile,
    ModelInstallPlan,
    ModelRecommendation,
)
from substitute.presentation.onboarding.onboarding_model_download_review_page import (
    DownloadCartCard,
    ModelDownloadReviewPage,
    download_action_text,
)
from substitute.presentation.onboarding.onboarding_page_stage import OnboardingPageStage
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail
from tests.support.qt.lifecycle import ensure_qt_application


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

    page.set_plan(plan, (_card(ModelFamilyId.SDXL, 1),))

    cards = page.findChildren(DownloadCartCard)
    visible_text = " ".join(
        label.text() for label in page.findChildren(QLabel) if label.text()
    )
    assert len(cards) == 1
    assert "Required components" not in visible_text
    assert "E:/models" not in visible_text
    assert "E:\\models" not in visible_text
    assert page.summary_panel.total_label.text() == "6.1 GiB"
    assert not page.summary_panel.isHidden()
    assert cards[0].size().toTuple() == (204, 220)
    assert cards[0].portrait.size().toTuple() == (184, 200)
    assert cards[0].portrait.accessibleDescription() == "SDXL  ·  6.1 GiB"
    assert cards[0].remove_button.accessibleName() == "Remove One obsession"
    assert bool(cards[0].remove_button.property("onboardingCardRemove"))
    assert cards[0].remove_button.cursor().shape() == Qt.CursorShape.PointingHandCursor
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
        (_card(ModelFamilyId.SDXL, 1), _card(ModelFamilyId.ANIMA, 1)),
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
    assert page.sizeHint().height() <= 548
    page.close()


def test_nine_model_checkout_matches_picker_density_and_keeps_totals_in_hero() -> None:
    """Fit the supported cart in a centered five-column grid without hiding cost."""

    application = ensure_qt_application()
    page = ModelDownloadReviewPage()
    host = QWidget()
    host.resize(1104, 548)
    stage = OnboardingPageStage(host)
    stage.setGeometry(host.rect())
    stage.add_page(page)
    model_root = Path("E:/models")
    files = tuple(
        _install_file(
            model_id=100 + rank,
            version_id=(100 + rank) * 10,
            display_name=f"Model {rank}",
            file_name=f"model-{rank}.safetensors",
            size_bytes=1_000_000_000,
            destination_dir=model_root / "checkpoints",
        )
        for rank in range(1, 10)
    )
    plan = ModelInstallPlan(
        model_root=model_root,
        files=files,
        available_bytes=244_800_000_000,
    )
    page.set_plan(
        plan,
        tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 10)),
    )
    stage.show_page(page)
    host.show()
    application.processEvents()
    stage.refresh_current_page_height()
    application.processEvents()

    cards = page.findChildren(DownloadCartCard)
    assert len(cards) == 9
    assert len({card.parentWidget() for card in cards}) == 2
    assert all(card.size().toTuple() == (204, 220) for card in cards)
    assert all(card.portrait.size().toTuple() == (184, 200) for card in cards)
    assert all("MiB" in card.portrait.accessibleDescription() for card in cards)
    assert not stage.verticalScrollBar().isVisible()
    bottom_row = cards[5:]
    row_left = bottom_row[0].mapToGlobal(bottom_row[0].rect().topLeft()).x()
    row_right = bottom_row[-1].mapToGlobal(bottom_row[-1].rect().topRight()).x()
    row_center = (row_left + row_right) // 2
    page_center = page.mapToGlobal(page.rect().center()).x()
    assert abs(row_center - page_center) <= 1
    assert page.summary_panel.parentWidget() is page.hero_panel
    assert page.summary_panel.total_label.text() == "8.4 GiB"
    assert page.summary_panel.accessibleDescription() == str(model_root)
    assert render_application_text(download_action_text(plan)) == (
        "Download 9 models · 8.4 GiB"
    )
    assert page.sizeHint().height() <= 550
    host.close()


def test_large_checkout_scrolls_only_cards_and_keeps_summary_locked() -> None:
    """Keep checkout totals fixed while a large model cart scrolls beneath them."""

    application = ensure_qt_application()
    page = ModelDownloadReviewPage()
    host = QWidget()
    host.resize(1104, 548)
    stage = OnboardingPageStage(host)
    stage.setGeometry(host.rect())
    stage.add_page(page)
    model_root = Path("E:/models")
    files = tuple(
        _install_file(
            model_id=100 + rank,
            version_id=(100 + rank) * 10,
            display_name=f"Model {rank}",
            file_name=f"model-{rank}.safetensors",
            size_bytes=1_000_000_000,
            destination_dir=model_root / "checkpoints",
        )
        for rank in range(1, 17)
    )
    plan = ModelInstallPlan(
        model_root=model_root,
        files=files,
        available_bytes=244_800_000_000,
    )
    page.set_plan(
        plan,
        tuple(_card(ModelFamilyId.SDXL, rank) for rank in range(1, 17)),
    )
    stage.show_page(page)
    host.show()
    application.processEvents()
    stage.refresh_current_page_height()
    application.processEvents()

    summary_top = page.summary_panel.mapToGlobal(
        page.summary_panel.rect().topLeft()
    ).y()
    assert stage.verticalScrollBar().maximum() == 0
    assert page.cards_scroll.verticalScrollBar().maximum() > 0

    page.cards_scroll.verticalScrollBar().setValue(
        page.cards_scroll.verticalScrollBar().maximum()
    )
    application.processEvents()

    assert (
        page.summary_panel.mapToGlobal(page.summary_panel.rect().topLeft()).y()
        == summary_top
    )
    host.close()


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
