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

"""Adapt CivitAI recommendations to provider-neutral picker suggestions."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from substitute.application.model_recommendations import (
    RecommendationThumbnailFetcher,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelRecommendation,
    ModelRecommendationAccess,
    ModelRecommendationAccessPolicy,
    ModelRecommendationQuery,
    SUPPORTED_MODEL_FAMILIES,
)
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionAccessPolicy,
    ModelSuggestionContext,
    ModelSuggestionReference,
)
from substitute.infrastructure.model_recommendations import (
    CivitaiFamilyRecommendationGateway,
)
from sugarsubstitute_shared.model_acquisition import (
    AcquisitionResult,
    CancellationProbe,
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery import DiscoveredModel


class CivitaiModelSuggestionProvider:
    """Provide family-compatible CivitAI suggestions and verified acquisition."""

    provider_id = "civitai"

    def __init__(
        self,
        *,
        recommendations: CivitaiFamilyRecommendationGateway,
        thumbnails: RecommendationThumbnailFetcher,
        acquisition: ModelAcquisitionService,
    ) -> None:
        """Store the existing CivitAI recommendation and transfer owners."""

        self._recommendations = recommendations
        self._thumbnails = thumbnails
        self._acquisition = acquisition

    def supports(self, context: ModelSuggestionContext) -> bool:
        """Return whether the family catalog expects this artifact role."""

        try:
            family = SUPPORTED_MODEL_FAMILIES.get(context.family_id)
        except ValueError:
            return False
        return family.primary_artifact_kind is context.artifact_kind

    def suggest(
        self,
        context: ModelSuggestionContext,
        *,
        access_policy: ModelSuggestionAccessPolicy,
        limit: int,
        excluded_sha256: frozenset[str],
    ) -> tuple[ModelSuggestion, ...]:
        """Return exact-family CivitAI results under the requested access policy."""

        recommendation_policy = (
            ModelRecommendationAccessPolicy.PUBLIC_ONLY
            if access_policy is ModelSuggestionAccessPolicy.PUBLIC_ONLY
            else ModelRecommendationAccessPolicy.INCLUDE_AUTHENTICATED
        )
        recommendations = self._recommendations.discover(
            ModelRecommendationQuery(
                context.family_id,
                access_policy=recommendation_policy,
            ),
            limit=limit,
            excluded_sha256=excluded_sha256,
        )
        return tuple(self._as_suggestion(context, item) for item in recommendations)

    def browse_url(self, context: ModelSuggestionContext) -> str:
        """Return a family-filtered public CivitAI browse URL."""

        family = SUPPORTED_MODEL_FAMILIES.get(context.family_id)
        query = urlencode(
            {
                "types": family.civitai.model_type,
                "baseModels": family.civitai.recommendation_base_model,
                "sort": "Most Downloaded",
                "period": "Month",
            }
        )
        return f"https://civitai.com/models?{query}"

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Fetch a governed CivitAI thumbnail for one owned suggestion."""

        return self._thumbnails.fetch(self._as_recommendation(suggestion))

    def acquire(
        self,
        suggestion: ModelSuggestion,
        *,
        destination: Path,
        cancellation: CancellationProbe | None,
    ) -> AcquisitionResult:
        """Acquire one suggestion through the hardened CivitAI transfer primitive."""

        reference = suggestion.reference
        return self._acquisition.acquire(
            DiscoveredModel(
                artifact_kind=suggestion.context.artifact_kind,
                model_id=int(reference.model_id),
                version_id=int(reference.version_id),
                model_name=suggestion.model_name,
                version_name=suggestion.version_name,
                creator=suggestion.creator,
                base_model=suggestion.context.family_id.value,
                file_name=suggestion.file_name,
                size_bytes=suggestion.size_bytes,
                sha256=suggestion.sha256,
                download_url=suggestion.download_url,
                model_page_url=suggestion.model_page_url,
                thumbnail_url=suggestion.thumbnail_url,
                provider_rank=suggestion.provider_rank,
            ),
            destination_dir=destination,
            cancellation=cancellation,
        )

    def _as_suggestion(
        self,
        context: ModelSuggestionContext,
        recommendation: ModelRecommendation,
    ) -> ModelSuggestion:
        """Project a CivitAI recommendation into provider-neutral semantics."""

        return ModelSuggestion(
            reference=ModelSuggestionReference(
                provider_id=self.provider_id,
                provider_name="CivitAI",
                model_id=str(recommendation.model_id),
                version_id=str(recommendation.version_id),
                thumbnail_id=str(recommendation.thumbnail_image_id),
            ),
            context=context,
            model_name=recommendation.model_name,
            version_name=recommendation.version_name,
            creator=recommendation.creator,
            file_name=recommendation.file_name,
            size_bytes=recommendation.size_bytes,
            sha256=recommendation.sha256,
            download_url=recommendation.download_url,
            model_page_url=recommendation.model_page_url,
            thumbnail_url=recommendation.thumbnail_url,
            provider_rank=recommendation.popularity_rank,
            access=(
                ModelSuggestionAccess.PUBLIC
                if recommendation.access is ModelRecommendationAccess.PUBLIC
                else ModelSuggestionAccess.API_KEY_REQUIRED
            ),
        )

    @staticmethod
    def _as_recommendation(suggestion: ModelSuggestion) -> ModelRecommendation:
        """Adapt an owned suggestion to the existing thumbnail fetch contract."""

        reference = suggestion.reference
        if (
            reference.provider_id != "civitai"
            or suggestion.thumbnail_url is None
            or reference.thumbnail_id is None
            or not reference.thumbnail_id.isdigit()
        ):
            raise ValueError("CivitAI suggestion has no usable thumbnail.")
        return ModelRecommendation(
            family_id=suggestion.context.family_id,
            model_id=int(reference.model_id),
            version_id=int(reference.version_id),
            model_name=suggestion.model_name,
            version_name=suggestion.version_name,
            creator=suggestion.creator,
            file_name=suggestion.file_name,
            size_bytes=suggestion.size_bytes,
            sha256=suggestion.sha256,
            download_url=suggestion.download_url,
            model_page_url=suggestion.model_page_url,
            thumbnail_image_id=int(reference.thumbnail_id),
            thumbnail_url=suggestion.thumbnail_url,
            popularity_rank=suggestion.provider_rank,
            access=(
                ModelRecommendationAccess.PUBLIC
                if suggestion.access is ModelSuggestionAccess.PUBLIC
                else ModelRecommendationAccess.API_KEY_REQUIRED
            ),
        )


__all__ = ["CivitaiModelSuggestionProvider"]
