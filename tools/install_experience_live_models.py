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

"""Compose real provider discovery for the interactive installer smoke."""

from __future__ import annotations

from PySide6.QtCore import QObject

from substitute.application.model_recommendations import (
    ExistingModelFamilyScanner,
    ModelOnboardingApplicationService,
)
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.persistent_cache_composition import (
    build_openmodeldb_catalog,
    build_recommendation_thumbnail_cache,
)
from substitute.app.bootstrap.persistent_cache_runtime import PersistentCacheRuntime
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_model_thumbnail_submitter,
    create_onboarding_model_submitter,
)
from substitute.domain.model_metadata import STANDARD_THUMBNAIL_ROLE, ThumbnailAsset
from substitute.domain.model_recommendations import ModelRecommendation
from substitute.infrastructure.model_recommendations import (
    CachedRecommendationThumbnailFetcher,
    CivitaiFamilyRecommendationGateway,
    CivitaiThumbnailFetcher,
    ProviderRecommendationGateway,
    ProviderRecommendationThumbnailFetcher,
)
from substitute.infrastructure.model_suggestions import (
    CachedOpenModelDbThumbnailFetcher,
    OpenModelDbThumbnailFetcher,
)
from substitute.infrastructure.persistence.model_thumbnail_store import (
    ModelThumbnailStore,
)
from substitute.presentation.onboarding.model_onboarding_coordinator import (
    ModelOnboardingCoordinator,
)

_THUMBNAIL_SIZE = 1024


class TransientRecommendationThumbnailFetcher:
    """Prepare live CivitAI thumbnails in memory without persistent cache writes."""

    def __init__(
        self,
        *,
        fetcher: CivitaiThumbnailFetcher | None = None,
        preparer: ModelThumbnailStore | None = None,
    ) -> None:
        """Create the bounded transport and in-memory Qt image preparer."""

        self._fetcher = fetcher or CivitaiThumbnailFetcher()
        self._preparer = preparer or ModelThumbnailStore(
            variant_sizes=(_THUMBNAIL_SIZE,)
        )

    def fetch(self, recommendation: ModelRecommendation) -> ThumbnailAsset:
        """Return one validated Qt-ready asset without writing it to disk."""

        if recommendation.thumbnail_url is None:
            raise ValueError("Recommendation has no preview image.")
        payload = self._fetcher.fetch(recommendation.thumbnail_url)
        prepared = self._preparer.cache_local_thumbnail(
            sha256=recommendation.sha256,
            image=payload,
            source="civitai",
            source_label=recommendation.thumbnail_url,
            selection_policy="interactive-installer-smoke:sfw_only:v1",
        )
        if prepared is None:
            raise ValueError("Recommendation thumbnail could not be prepared.")
        storage_key = (
            f"{recommendation.sha256.upper()}:{STANDARD_THUMBNAIL_ROLE}:"
            f"{_THUMBNAIL_SIZE}"
        )
        for asset in prepared.assets:
            if asset.storage_key == storage_key:
                return asset
        raise ValueError("Prepared recommendation thumbnail is missing its UI asset.")


def create_live_model_onboarding_coordinator(
    *,
    runtime: ExecutionRuntime,
    cache_runtime: PersistentCacheRuntime,
    parent: QObject,
) -> ModelOnboardingCoordinator:
    """Build live provider discovery while leaving install effects synthetic."""

    request_submitter = create_onboarding_model_submitter(runtime, parent)
    thumbnail_submitter = create_onboarding_model_thumbnail_submitter(runtime, parent)
    thumbnail_cache = build_recommendation_thumbnail_cache(cache_runtime)
    return ModelOnboardingCoordinator(
        service=ModelOnboardingApplicationService(
            scanner=ExistingModelFamilyScanner(),
            gateway=ProviderRecommendationGateway(
                civitai=CivitaiFamilyRecommendationGateway(),
                openmodeldb=build_openmodeldb_catalog(cache_runtime.prepared),
            ),
            thumbnail_fetcher=ProviderRecommendationThumbnailFetcher(
                civitai=CachedRecommendationThumbnailFetcher(
                    fetcher=CivitaiThumbnailFetcher(),
                    preparer=thumbnail_cache.preparer,
                    asset_store=thumbnail_cache.assets,
                ),
                openmodeldb=CachedOpenModelDbThumbnailFetcher(
                    fetcher=OpenModelDbThumbnailFetcher(),
                    preparer=thumbnail_cache.preparer,
                    asset_store=thumbnail_cache.assets,
                ),
            ),
        ),
        request_submitter=request_submitter,
        close_request_submitter=request_submitter.close,
        thumbnail_submitter=thumbnail_submitter,
        close_thumbnail_submitter=thumbnail_submitter.close,
        parent=parent,
    )


__all__ = [
    "TransientRecommendationThumbnailFetcher",
    "create_live_model_onboarding_coordinator",
]
