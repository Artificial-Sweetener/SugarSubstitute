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

"""Prepare and reuse recommendation thumbnails in the governed model cache."""

from __future__ import annotations

from typing import Protocol

from substitute.domain.model_metadata import (
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailAsset,
    ThumbnailStoreResult,
)
from substitute.domain.model_recommendations import ModelRecommendation

from .thumbnail_fetcher import CivitaiThumbnailFetcher

_RECOMMENDATION_THUMBNAIL_SIZE = 1024
_SELECTION_POLICY = "civitai-thumbnail:sfw_only:v1"


class RecommendationThumbnailPreparer(Protocol):
    """Prepare Qt-ready variants from one bounded local image payload."""

    def cache_local_thumbnail(
        self,
        *,
        sha256: str,
        image: object | None,
        source: str,
        source_label: str,
        source_path: str | None = None,
        source_width: int | None = None,
        source_height: int | None = None,
        selection_policy: str = "user_selected_output_canvas",
    ) -> ThumbnailStoreResult | None:
        """Prepare thumbnail assets without owning persistent storage."""


class RecommendationThumbnailAssetStore(Protocol):
    """Read and atomically replace governed model-thumbnail cache assets."""

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one prepared cached asset when present."""

    def replace(self, sha256: str, thumbnail: ThumbnailStoreResult | None) -> None:
        """Replace every cached thumbnail variant for one model hash."""


class CachedRecommendationThumbnailFetcher:
    """Fetch bounded CivitAI bytes once and return a reusable Qt-ready asset."""

    def __init__(
        self,
        *,
        fetcher: CivitaiThumbnailFetcher,
        preparer: RecommendationThumbnailPreparer,
        asset_store: RecommendationThumbnailAssetStore,
    ) -> None:
        """Store bounded transport, Qt preparation, and persistent cache owners."""

        self._fetcher = fetcher
        self._preparer = preparer
        self._asset_store = asset_store

    def fetch(self, recommendation: ModelRecommendation) -> ThumbnailAsset:
        """Return one cached or newly prepared safe recommendation thumbnail."""

        storage_key = _storage_key(recommendation.sha256)
        cached = self._asset_store.read_thumbnail_asset(storage_key)
        if cached is not None:
            return cached
        encoded_payload = self._fetcher.fetch(recommendation.thumbnail_url)
        prepared = self._preparer.cache_local_thumbnail(
            sha256=recommendation.sha256,
            image=encoded_payload,
            source="civitai",
            source_label=recommendation.thumbnail_url,
            selection_policy=_SELECTION_POLICY,
        )
        if prepared is None:
            raise ValueError("Recommendation thumbnail could not be prepared.")
        self._asset_store.replace(recommendation.sha256, prepared)
        cached = self._asset_store.read_thumbnail_asset(storage_key)
        if cached is None:
            raise OSError("Prepared recommendation thumbnail was not persisted.")
        return cached


def _storage_key(sha256: str) -> str:
    """Return the existing model-thumbnail cache key for the standard variant."""

    return (
        f"{sha256.upper()}:{STANDARD_THUMBNAIL_ROLE}:{_RECOMMENDATION_THUMBNAIL_SIZE}"
    )


__all__ = [
    "CachedRecommendationThumbnailFetcher",
    "RecommendationThumbnailAssetStore",
    "RecommendationThumbnailPreparer",
]
