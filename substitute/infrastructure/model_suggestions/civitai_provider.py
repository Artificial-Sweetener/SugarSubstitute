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
from substitute.application.model_metadata import CivitaiMetadataGateway
from substitute.application.model_suggestions import CURATED_UPSCALERS
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_metadata import (
    CivitaiDownloadAccess,
    CivitaiFile,
    CivitaiLookupStatus,
    CivitaiThumbnailPolicy,
)
from substitute.domain.model_recommendations import (
    ModelRecommendation,
    ModelRecommendationAccess,
    ModelRecommendationAccessPolicy,
    ModelRecommendationQuery,
    SUPPORTED_MODEL_FAMILIES,
)
from substitute.domain.model_suggestions import (
    ModelAcquisitionOffer,
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
from sugarsubstitute_shared.model_discovery import DiscoveredModel, ModelArtifactKind

from .openmodeldb_catalog import OpenModelDbCatalogClient, OpenModelDbResource


class CivitaiModelSuggestionProvider:
    """Provide family-compatible CivitAI suggestions and verified acquisition."""

    provider_id = "civitai"

    def __init__(
        self,
        *,
        recommendations: CivitaiFamilyRecommendationGateway,
        thumbnails: RecommendationThumbnailFetcher,
        acquisition: ModelAcquisitionService,
        upscaler_catalog: OpenModelDbCatalogClient | None = None,
        metadata: CivitaiMetadataGateway | None = None,
        thumbnail_policy: CivitaiThumbnailPolicy | None = None,
    ) -> None:
        """Store the existing CivitAI recommendation and transfer owners."""

        self._recommendations = recommendations
        self._thumbnails = thumbnails
        self._acquisition = acquisition
        self._upscaler_catalog = upscaler_catalog
        self._metadata = metadata
        self._thumbnail_policy = thumbnail_policy

    def supports(self, context: ModelSuggestionContext) -> bool:
        """Return whether the family catalog expects this artifact role."""

        if context.artifact_kind is ModelArtifactKind.UPSCALE_MODELS:
            return self._upscaler_catalog is not None and self._metadata is not None
        if context.family_id is None:
            return False
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

        if context.artifact_kind is ModelArtifactKind.UPSCALE_MODELS:
            return self._suggest_upscalers(
                context,
                access_policy=access_policy,
                limit=limit,
                excluded_sha256=excluded_sha256,
            )
        family_id = context.family_id
        if family_id is None:
            return ()
        recommendation_policy = (
            ModelRecommendationAccessPolicy.PUBLIC_ONLY
            if access_policy is ModelSuggestionAccessPolicy.PUBLIC_ONLY
            else ModelRecommendationAccessPolicy.INCLUDE_AUTHENTICATED
        )
        recommendations = self._recommendations.discover(
            ModelRecommendationQuery(
                family_id,
                access_policy=recommendation_policy,
            ),
            limit=limit,
            excluded_sha256=excluded_sha256,
        )
        return tuple(self._as_suggestion(context, item) for item in recommendations)

    def browse_url(self, context: ModelSuggestionContext) -> str:
        """Return a family-filtered public CivitAI browse URL."""

        if context.artifact_kind is ModelArtifactKind.UPSCALE_MODELS:
            return "https://civitai.com/models?types=Upscaler"
        if context.family_id is None:
            raise ValueError("CivitAI family browsing requires a model family.")
        family = SUPPORTED_MODEL_FAMILIES.get(context.family_id)
        mapping = family.civitai
        if mapping is None:
            raise ValueError("The selected model family is not available from CivitAI.")
        query = urlencode(
            {
                "types": mapping.model_type,
                "baseModels": mapping.recommendation_base_model,
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
        offer: ModelAcquisitionOffer,
        *,
        destination: Path,
        cancellation: CancellationProbe | None,
    ) -> AcquisitionResult:
        """Acquire one suggestion through the hardened CivitAI transfer primitive."""

        reference = offer.reference
        return self._acquisition.acquire(
            DiscoveredModel(
                artifact_kind=suggestion.context.artifact_kind,
                model_id=int(reference.model_id),
                version_id=int(reference.version_id),
                model_name=suggestion.model_name,
                version_name=suggestion.version_name,
                creator=suggestion.creator,
                base_model=(
                    suggestion.context.family_id.value
                    if suggestion.context.family_id is not None
                    else None
                ),
                file_name=offer.file_name,
                size_bytes=offer.size_bytes,
                sha256=suggestion.sha256,
                download_url=offer.download_url,
                model_page_url=offer.model_page_url,
                thumbnail_url=offer.thumbnail_url,
                provider_rank=offer.provider_rank,
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
            context=context,
            model_name=recommendation.model_name,
            version_name=recommendation.version_name,
            creator=recommendation.creator,
            sha256=recommendation.sha256,
            offers=(
                ModelAcquisitionOffer(
                    reference=ModelSuggestionReference(
                        provider_id=self.provider_id,
                        provider_name="CivitAI",
                        model_id=str(recommendation.model_id),
                        version_id=str(recommendation.version_id),
                        thumbnail_id=str(recommendation.thumbnail_image_id),
                    ),
                    file_name=recommendation.file_name,
                    size_bytes=recommendation.size_bytes,
                    download_url=recommendation.download_url,
                    model_page_url=recommendation.model_page_url,
                    thumbnail_url=recommendation.thumbnail_url,
                    provider_rank=recommendation.popularity_rank,
                    access=(
                        ModelSuggestionAccess.PUBLIC
                        if recommendation.access is ModelRecommendationAccess.PUBLIC
                        else ModelSuggestionAccess.API_KEY_REQUIRED
                    ),
                ),
            ),
        )

    def _suggest_upscalers(
        self,
        context: ModelSuggestionContext,
        *,
        access_policy: ModelSuggestionAccessPolicy,
        limit: int,
        excluded_sha256: frozenset[str],
    ) -> tuple[ModelSuggestion, ...]:
        """Return CivitAI offers for reviewed exact OpenModelDB artifacts."""

        catalog_source = self._upscaler_catalog
        metadata = self._metadata
        thumbnail_policy = self._thumbnail_policy
        if catalog_source is None or metadata is None or thumbnail_policy is None:
            return ()
        catalog = catalog_source.load()
        excluded = {value.casefold() for value in excluded_sha256}
        suggestions: list[ModelSuggestion] = []
        for rank, curated in enumerate(CURATED_UPSCALERS, start=1):
            model = catalog.model(curated.model_id)
            if model is None:
                continue
            resource = model.preferred_resource()
            if resource is None or resource.sha256 in excluded:
                continue
            lookup = metadata.lookup_model_version_by_hash(resource.sha256)
            if lookup.status is not CivitaiLookupStatus.FOUND or lookup.version is None:
                continue
            version = lookup.version
            file = _civitai_upscaler_file(version.files, resource)
            if file is None or file.download_url is None:
                continue
            access = _download_access(metadata, version.model_version_id)
            if (
                access_policy is ModelSuggestionAccessPolicy.PUBLIC_ONLY
                and access is not CivitaiDownloadAccess.PUBLIC
            ):
                continue
            thumbnail = thumbnail_policy.select(version).image
            suggestions.append(
                ModelSuggestion(
                    context=context,
                    model_name=version.model_name or model.name,
                    version_name=version.version_name or model.name,
                    creator=version.creator_username or model.author,
                    sha256=resource.sha256,
                    offers=(
                        ModelAcquisitionOffer(
                            reference=ModelSuggestionReference(
                                provider_id=self.provider_id,
                                provider_name="CivitAI",
                                model_id=str(version.model_id),
                                version_id=str(version.model_version_id),
                                thumbnail_id=(
                                    str(thumbnail.image_id)
                                    if thumbnail is not None
                                    and thumbnail.image_id is not None
                                    else None
                                ),
                            ),
                            file_name=file.name,
                            size_bytes=resource.size_bytes,
                            download_url=file.download_url,
                            model_page_url=version.model_page_url,
                            thumbnail_url=(
                                thumbnail.url if thumbnail is not None else None
                            ),
                            provider_rank=rank,
                            access=(
                                ModelSuggestionAccess.PUBLIC
                                if access is CivitaiDownloadAccess.PUBLIC
                                else ModelSuggestionAccess.API_KEY_REQUIRED
                            ),
                        ),
                    ),
                )
            )
            if len(suggestions) == limit:
                break
        return tuple(suggestions)

    @staticmethod
    def _as_recommendation(suggestion: ModelSuggestion) -> ModelRecommendation:
        """Adapt an owned suggestion to the existing thumbnail fetch contract."""

        offer = suggestion.primary_offer
        reference = offer.reference
        family_id = suggestion.context.family_id
        if (
            reference.provider_id != "civitai"
            or family_id is None
            or offer.thumbnail_url is None
            or reference.thumbnail_id is None
            or not reference.thumbnail_id.isdigit()
        ):
            raise ValueError("CivitAI suggestion has no usable thumbnail.")
        return ModelRecommendation(
            family_id=family_id,
            model_id=int(reference.model_id),
            version_id=int(reference.version_id),
            model_name=suggestion.model_name,
            version_name=suggestion.version_name,
            creator=suggestion.creator,
            file_name=offer.file_name,
            size_bytes=offer.size_bytes,
            sha256=suggestion.sha256,
            download_url=offer.download_url,
            model_page_url=offer.model_page_url,
            thumbnail_image_id=int(reference.thumbnail_id),
            thumbnail_url=offer.thumbnail_url,
            popularity_rank=offer.provider_rank,
            access=(
                ModelRecommendationAccess.PUBLIC
                if offer.access is ModelSuggestionAccess.PUBLIC
                else ModelRecommendationAccess.API_KEY_REQUIRED
            ),
        )


__all__ = ["CivitaiModelSuggestionProvider"]


def _civitai_upscaler_file(
    files: tuple[CivitaiFile, ...], resource: OpenModelDbResource
) -> CivitaiFile | None:
    """Return a scan-clean CivitAI file matching the exact curated artifact."""

    matching = tuple(
        file
        for file in files
        if _civitai_file_sha256(file) == resource.sha256
        and file.download_url is not None
        and Path(file.name).suffix.casefold() in {".pth", ".pt", ".safetensors"}
        and file.virus_scan_result is not None
        and file.virus_scan_result.casefold() == "success"
        and (
            Path(file.name).suffix.casefold() == ".safetensors"
            or (
                file.pickle_scan_result is not None
                and file.pickle_scan_result.casefold() == "success"
            )
        )
    )
    return (
        sorted(matching, key=lambda item: (not item.primary, item.name))[0]
        if matching
        else None
    )


def _civitai_file_sha256(file: CivitaiFile) -> str | None:
    """Return one normalized CivitAI file SHA-256."""

    value = file.hashes.get("SHA256")
    return value.casefold() if isinstance(value, str) else None


def _download_access(
    metadata: CivitaiMetadataGateway, model_version_id: int
) -> CivitaiDownloadAccess:
    """Return explicit CivitAI access metadata when the adapter supports it."""

    lookup = getattr(metadata, "model_version_download_access", None)
    if not callable(lookup):
        return CivitaiDownloadAccess.UNKNOWN
    value = lookup(model_version_id)
    return (
        value
        if isinstance(value, CivitaiDownloadAccess)
        else CivitaiDownloadAccess.UNKNOWN
    )
