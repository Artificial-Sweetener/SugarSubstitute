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

"""Verify metadata-first recommendation page construction."""

from __future__ import annotations

from pathlib import Path

from substitute.application.execution import CancellationSource
from substitute.application.model_recommendations import (
    ModelOnboardingApplicationService,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelFamilyScanResult,
    ModelFamilyScanStatus,
    ModelRecommendation,
    ModelRecommendationQuery,
)


class _Scanner:
    """Return a fixed safe scan result."""

    def scan(self, root: Path, **_kwargs: object) -> ModelFamilyScanResult:
        """Return a confidently empty result for delegation coverage."""

        return ModelFamilyScanResult(
            root,
            ModelFamilyScanStatus.COMPLETED,
            (),
            0,
            0,
            0,
        )


class _Gateway:
    """Return six family-specific provider-ordered recommendation candidates."""

    def discover(
        self,
        query: ModelRecommendationQuery,
        **_kwargs: object,
    ) -> tuple[ModelRecommendation, ...]:
        """Build deterministic cards for the requested exact family."""

        return tuple(_recommendation(query.family_id, rank) for rank in range(1, 7))


class _Thumbnails:
    """Return prepared assets except for one configured model."""

    def __init__(self, failed_model_id: int | None = None) -> None:
        """Store the optional model whose image cannot be prepared."""

        self._failed_model_id = failed_model_id
        self.calls: list[int] = []

    def fetch(self, recommendation: ModelRecommendation) -> ThumbnailAsset:
        """Return one Qt-ready payload or the expected recoverable failure."""

        self.calls.append(recommendation.model_id)
        if recommendation.model_id == self._failed_model_id:
            raise ValueError("undecodable thumbnail")
        return ThumbnailAsset(
            storage_key=f"thumbnail:{recommendation.model_id}",
            width=1,
            height=1,
            qt_format=5,
            bytes_per_line=4,
            content_format="qt-argb32-premultiplied-v1",
            payload=b"\0\0\0\0",
        )


def test_service_returns_top_metadata_before_loading_thumbnails() -> None:
    """Make three-card pages visible before any image transport begins."""

    thumbnails = _Thumbnails()
    service = ModelOnboardingApplicationService(
        scanner=_Scanner(),
        gateway=_Gateway(),
        thumbnail_fetcher=thumbnails,
    )

    pages = service.recommend(
        (ModelFamilyId.SDXL, ModelFamilyId.ANIMA),
        cancellation=CancellationSource(generation=1),
    )

    assert tuple(page.family_id for page in pages) == (
        ModelFamilyId.SDXL,
        ModelFamilyId.ANIMA,
    )
    assert [card.recommendation.popularity_rank for card in pages[0].cards] == [1, 2, 3]
    assert [card.recommendation.popularity_rank for card in pages[1].cards] == [1, 2, 3]
    assert all(card.thumbnail is None for page in pages for card in page.cards)
    assert thumbnails.calls == []

    thumbnail = service.fetch_thumbnail(
        pages[0].cards[0].recommendation,
        cancellation=CancellationSource(generation=2),
    )

    assert thumbnail.payload
    assert thumbnails.calls == [101]


def test_service_stops_before_provider_access_when_cancelled() -> None:
    """A superseded family choice must not populate any later page."""

    cancellation = CancellationSource(generation=1)
    cancellation.cancel(reason="selection_changed")
    service = ModelOnboardingApplicationService(
        scanner=_Scanner(),
        gateway=_Gateway(),
        thumbnail_fetcher=_Thumbnails(),
    )

    assert (
        service.recommend(
            (ModelFamilyId.SDXL,),
            cancellation=cancellation,
        )
        == ()
    )


def _recommendation(family: ModelFamilyId, rank: int) -> ModelRecommendation:
    """Return one safe deterministic provider recommendation."""

    model_id = (100 if family is ModelFamilyId.SDXL else 200) + rank
    return ModelRecommendation(
        family_id=family,
        model_id=model_id,
        version_id=model_id * 10,
        model_name=f"model {model_id}",
        version_name="v1",
        creator="creator",
        file_name=f"model-{model_id}.safetensors",
        size_bytes=1024,
        sha256=f"{model_id:064x}",
        download_url=f"https://civitai.com/api/download/models/{model_id * 10}",
        model_page_url=f"https://civitai.com/models/{model_id}",
        thumbnail_image_id=model_id * 100,
        thumbnail_url=f"https://image.civitai.com/{model_id}.png",
        popularity_rank=rank,
    )
