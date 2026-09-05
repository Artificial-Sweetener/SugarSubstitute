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

"""Verify metadata-first onboarding thumbnail orchestration."""

from __future__ import annotations

from pathlib import Path

from substitute.application.execution import CancellationToken
from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelFamilyScanResult,
    ModelRecommendation,
)
from substitute.presentation.onboarding.model_onboarding_coordinator import (
    ModelOnboardingCoordinator,
)
from tests.support.execution import QueuedTaskSubmitter
from tests.support.qt.lifecycle import ensure_qt_application


class _ModelService:
    """Return fixed metadata and independently requested thumbnails."""

    def __init__(
        self,
        pages: FamilyRecommendationPage | tuple[FamilyRecommendationPage, ...],
    ) -> None:
        """Store the pages returned by the recommendation request."""

        self._pages = pages if isinstance(pages, tuple) else (pages,)

    def scan(
        self,
        root: Path,
        *,
        cancellation: CancellationToken,
    ) -> ModelFamilyScanResult:
        """Reject unused scan requests in this focused orchestration test."""

        _ = (root, cancellation)
        raise AssertionError("scan is outside this test")

    def recommend(
        self,
        families: tuple[ModelFamilyId, ...],
        *,
        cancellation: CancellationToken,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> tuple[FamilyRecommendationPage, ...]:
        """Return the fixed page when queued work is executed directly."""

        _ = (families, cancellation, excluded_sha256)
        return self._pages

    def fetch_thumbnail(
        self,
        recommendation: ModelRecommendation,
        *,
        cancellation: CancellationToken,
    ) -> ThumbnailAsset:
        """Return one fixed image payload for direct task execution."""

        _ = (recommendation, cancellation)
        return _thumbnail()


def test_metadata_is_published_before_thumbnail_tasks_settle() -> None:
    """Show the page while every portrait image request remains pending."""

    ensure_qt_application()
    page = FamilyRecommendationPage(
        ModelFamilyId.SDXL,
        tuple(RecommendationCardAsset(_recommendation(rank)) for rank in range(1, 4)),
    )
    submitter = QueuedTaskSubmitter()
    coordinator = ModelOnboardingCoordinator(
        service=_ModelService(page),
        submitter=submitter,
        close_submitter=lambda: None,
    )
    metadata_events: list[tuple[FamilyRecommendationPage, ...]] = []
    thumbnail_events: list[int] = []
    coordinator.recommendation_finished.connect(
        lambda _generation, pages: metadata_events.append(pages)
    )
    coordinator.thumbnail_finished.connect(
        lambda _generation, version_id, _asset: thumbnail_events.append(version_id)
    )

    coordinator.start_recommendations((ModelFamilyId.SDXL,))
    assert len(submitter.handles) == 1

    submitter.handles[0].complete_success((page,))

    assert metadata_events == [(page,)]
    assert thumbnail_events == []
    assert len(submitter.handles) == 4

    submitter.handles[1].complete_success(_thumbnail())

    assert thumbnail_events == [1010]
    coordinator.shutdown()


def test_thumbnail_completions_identify_exact_versions_on_a_shared_model_page() -> None:
    """Keep concurrent family thumbnails distinct when their model ID is shared."""

    ensure_qt_application()
    shared_model_id = 934764
    pages = (
        FamilyRecommendationPage(
            ModelFamilyId.SDXL,
            (
                RecommendationCardAsset(
                    _recommendation_with_identity(
                        family=ModelFamilyId.SDXL,
                        model_id=shared_model_id,
                        version_id=2851583,
                    )
                ),
            ),
        ),
        FamilyRecommendationPage(
            ModelFamilyId.ANIMA,
            (
                RecommendationCardAsset(
                    _recommendation_with_identity(
                        family=ModelFamilyId.ANIMA,
                        model_id=shared_model_id,
                        version_id=3248362,
                    )
                ),
            ),
        ),
    )
    submitter = QueuedTaskSubmitter()
    coordinator = ModelOnboardingCoordinator(
        service=_ModelService(pages),
        submitter=submitter,
        close_submitter=lambda: None,
    )
    thumbnail_events: list[int] = []
    coordinator.thumbnail_finished.connect(
        lambda _generation, version_id, _asset: thumbnail_events.append(version_id)
    )

    coordinator.start_recommendations((ModelFamilyId.SDXL, ModelFamilyId.ANIMA))
    submitter.handles[0].complete_success(pages)
    submitter.handles[1].complete_success(_thumbnail())
    submitter.handles[2].complete_success(_thumbnail())

    assert thumbnail_events == [2851583, 3248362]
    coordinator.shutdown()


def _recommendation(rank: int) -> ModelRecommendation:
    """Return one pending SDXL recommendation."""

    model_id = 100 + rank
    return ModelRecommendation(
        family_id=ModelFamilyId.SDXL,
        model_id=model_id,
        version_id=model_id * 10,
        model_name=f"Model {rank}",
        version_name="v1",
        creator="creator",
        file_name=f"model-{rank}.safetensors",
        size_bytes=1024,
        sha256=f"{model_id:064x}",
        download_url=f"https://civitai.com/api/download/models/{model_id * 10}",
        model_page_url=f"https://civitai.com/models/{model_id}",
        thumbnail_image_id=model_id * 100,
        thumbnail_url=f"https://image.civitai.com/{model_id}.png",
        popularity_rank=rank,
    )


def _recommendation_with_identity(
    *,
    family: ModelFamilyId,
    model_id: int,
    version_id: int,
) -> ModelRecommendation:
    """Return one exact-version recommendation from a shared model page."""

    return ModelRecommendation(
        family_id=family,
        model_id=model_id,
        version_id=version_id,
        model_name="Shared model page",
        version_name=f"version-{version_id}",
        creator="creator",
        file_name=f"model-{version_id}.safetensors",
        size_bytes=1024,
        sha256=f"{version_id:064x}",
        download_url=f"https://civitai.com/api/download/models/{version_id}",
        model_page_url=(
            f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
        ),
        thumbnail_image_id=version_id * 10,
        thumbnail_url=f"https://image.civitai.com/{version_id}.png",
        popularity_rank=1,
    )


def _thumbnail() -> ThumbnailAsset:
    """Return one minimal prepared thumbnail payload."""

    return ThumbnailAsset(
        storage_key="thumbnail:101",
        width=1,
        height=1,
        qt_format=5,
        bytes_per_line=4,
        content_format="qt-argb32-premultiplied-v1",
        payload=b"\0\0\0\0",
    )
