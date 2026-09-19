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

"""Verify governed persistence and reuse of onboarding thumbnails."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from substitute.domain.model_recommendations import ModelFamilyId, ModelRecommendation
from substitute.infrastructure.model_recommendations import (
    CachedRecommendationThumbnailFetcher,
    CivitaiThumbnailFetcher,
    ThumbnailResponse,
)
from substitute.infrastructure.persistence.model_thumbnail_store import (
    ModelThumbnailStore,
)
from substitute.infrastructure.persistence import SqliteModelThumbnailAssetStore
from tests.support.qt.lifecycle import ensure_qt_application


def test_cached_fetcher_persists_prepared_asset_and_avoids_second_request(
    tmp_path: Path,
) -> None:
    """Use the registered model-thumbnail format as the recommendation cache."""

    ensure_qt_application()
    encoded = _png_payload(tmp_path)
    calls: list[str] = []

    def transport(url: str, **_kwargs: object) -> ThumbnailResponse:
        """Return one deterministic image and record provider access."""

        calls.append(url)
        return ThumbnailResponse("image/png", encoded)

    asset_store = SqliteModelThumbnailAssetStore(tmp_path / "model-thumbnails")
    fetcher = CachedRecommendationThumbnailFetcher(
        fetcher=CivitaiThumbnailFetcher(transport=transport),
        preparer=ModelThumbnailStore(variant_sizes=(1024,)),
        asset_store=asset_store,
    )
    recommendation = _recommendation()

    first = fetcher.fetch(recommendation)
    second = fetcher.fetch(recommendation)

    assert first == second
    assert first.storage_key == f"{'A' * 64}:standard:1024"
    assert first.width <= 1024
    assert first.height <= 1024
    assert first.payload
    assert calls == [recommendation.thumbnail_url]
    cached_result = asset_store.result_for_sha256(recommendation.sha256)
    assert cached_result is not None
    assert cached_result.selection_policy == "civitai-thumbnail:sfw_only:v1"


def test_cached_fetcher_rejects_undecodable_image_without_cache_record(
    tmp_path: Path,
) -> None:
    """Never persist provider bytes that Qt cannot decode as an image."""

    asset_store = SqliteModelThumbnailAssetStore(tmp_path / "model-thumbnails")
    fetcher = CachedRecommendationThumbnailFetcher(
        fetcher=CivitaiThumbnailFetcher(
            transport=lambda *_args, **_kwargs: ThumbnailResponse(
                "image/png", b"not-an-image"
            )
        ),
        preparer=ModelThumbnailStore(variant_sizes=(256,)),
        asset_store=asset_store,
    )

    try:
        fetcher.fetch(_recommendation())
    except ValueError:
        pass
    else:
        raise AssertionError("Undecodable provider image was accepted.")

    assert asset_store.result_for_sha256("a" * 64) is None


def _png_payload(tmp_path: Path) -> bytes:
    """Encode one deterministic source image through Qt."""

    image = QImage(640, 360, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#6C5CE7"))
    image_path = tmp_path / "source.png"
    assert image.save(str(image_path))
    return image_path.read_bytes()


def _recommendation() -> ModelRecommendation:
    """Return one valid exact-family recommendation identity."""

    return ModelRecommendation(
        family_id=ModelFamilyId.SDXL,
        model_id=1,
        version_id=2,
        model_name="Example SDXL",
        version_name="v1",
        creator="creator",
        file_name="example.safetensors",
        size_bytes=1024,
        sha256="a" * 64,
        download_url="https://civitai.com/api/download/models/2",
        model_page_url="https://civitai.com/models/1?modelVersionId=2",
        thumbnail_image_id=20,
        thumbnail_url="https://image.civitai.com/example.png",
        popularity_rank=1,
    )
