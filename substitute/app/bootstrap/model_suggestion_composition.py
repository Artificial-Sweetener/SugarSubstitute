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

"""Compose provider-neutral model suggestions for managed workspaces."""

from __future__ import annotations

from pathlib import Path

from substitute.application.civitai import (
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.model_suggestions import (
    ModelSuggestionEngine,
    ModelSuggestionService,
)
from substitute.domain.model_metadata import CivitaiThumbnailPolicy
from substitute.infrastructure.model_recommendations import (
    CachedRecommendationThumbnailFetcher,
    CivitaiFamilyRecommendationGateway,
    CivitaiThumbnailFetcher,
)
from substitute.infrastructure.model_recommendations.cached_thumbnail_fetcher import (
    RecommendationThumbnailAssetStore,
    RecommendationThumbnailPreparer,
)
from substitute.infrastructure.model_suggestions import CivitaiModelSuggestionProvider
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import ModelArtifactDestinationPolicy


def compose_model_suggestion_service(
    *,
    model_root: Path | None,
    credentials: CivitaiCredentialService,
    preferences: CivitaiPreferenceService,
    thumbnails: RecommendationThumbnailPreparer,
    thumbnail_assets: RecommendationThumbnailAssetStore,
) -> ModelSuggestionService | None:
    """Build discovery only where acquired artifacts have a managed destination."""

    if model_root is None:
        return None
    acquisition = ModelAcquisitionService(
        allowed_roots=(model_root,),
        api_key_provider=credentials.load_api_key,
    )
    provider = CivitaiModelSuggestionProvider(
        recommendations=CivitaiFamilyRecommendationGateway(
            api_key_provider=credentials.load_api_key,
            thumbnail_policy_provider=lambda: CivitaiThumbnailPolicy(
                preferences.load_preferences().thumbnail_safety_policy
            ),
        ),
        thumbnails=CachedRecommendationThumbnailFetcher(
            fetcher=CivitaiThumbnailFetcher(),
            preparer=thumbnails,
            asset_store=thumbnail_assets,
        ),
        acquisition=acquisition,
    )
    return ModelSuggestionService(
        destinations=ModelArtifactDestinationPolicy(model_root),
        engine=ModelSuggestionEngine((provider,)),
    )


__all__ = ["compose_model_suggestion_service"]
