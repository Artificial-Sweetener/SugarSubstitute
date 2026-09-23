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

"""Route onboarding model recommendations across supported providers."""

from __future__ import annotations

from typing import Protocol, cast
from urllib.parse import urlparse

from substitute.application.model_recommendations.onboarding_service import (
    FamilyRecommendationGateway,
    RecommendationThumbnailFetcher,
)
from substitute.application.model_suggestions import CURATED_UPSCALERS
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelRecommendation,
    ModelRecommendationQuery,
)
from substitute.infrastructure.model_suggestions.openmodeldb_catalog import (
    OpenModelDbCatalogClient,
    OpenModelDbModel,
    OpenModelDbResource,
)
from substitute.infrastructure.model_suggestions.openmodeldb_provider import (
    CachedOpenModelDbThumbnailFetcher,
    require_openmodeldb_download_url,
)
from substitute.infrastructure.model_recommendations.civitai_payload_parser import (
    model_page_identity,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionError


class _CivitaiUpscalerResolver(Protocol):
    """Describe the explicit CivitAI upscaler-link boundary."""

    def resolve_upscaler_page(self, url: str) -> ModelRecommendation | None:
        """Return one verified upscaler from a provider model page."""


class ProviderRecommendationGateway:
    """Prefer OpenModelDB for upscalers and CivitAI for generation families."""

    def __init__(
        self,
        *,
        civitai: FamilyRecommendationGateway,
        openmodeldb: OpenModelDbCatalogClient,
    ) -> None:
        """Store provider-specific metadata gateways."""

        self._civitai = civitai
        self._openmodeldb = openmodeldb

    def discover(
        self,
        query: ModelRecommendationQuery,
        *,
        limit: int = 5,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> tuple[ModelRecommendation, ...]:
        """Return curated OpenModelDB upscalers or ordinary CivitAI models."""

        if query.family_id is not ModelFamilyId.UPSCALERS:
            return self._civitai.discover(
                query,
                limit=limit,
                excluded_sha256=excluded_sha256,
            )
        excluded = {value.casefold() for value in excluded_sha256}
        catalog = self._openmodeldb.load()
        recommendations: list[ModelRecommendation] = []
        for rank, curated in enumerate(CURATED_UPSCALERS, start=1):
            model = catalog.model(curated.model_id)
            resource = _preferred_resource(model)
            if model is None or resource is None or resource.sha256 in excluded:
                continue
            recommendations.append(_recommendation(model, resource, rank=rank))
            if len(recommendations) == limit:
                break
        return tuple(recommendations)

    def resolve_model_page(
        self,
        family_id: ModelFamilyId,
        url: str,
    ) -> ModelRecommendation | None:
        """Resolve explicit provider pages for the requested onboarding family."""

        if family_id is not ModelFamilyId.UPSCALERS:
            return self._civitai.resolve_model_page(family_id, url)
        parsed = urlparse(url.strip())
        if parsed.hostname in {
            "civitai.com",
            "www.civitai.com",
            "civitai.red",
            "www.civitai.red",
        }:
            model_page_identity(url)
            return cast(_CivitaiUpscalerResolver, self._civitai).resolve_upscaler_page(
                url
            )
        if (
            parsed.scheme != "https"
            or parsed.hostname != "openmodeldb.info"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
        ):
            raise ValueError("Expected an OpenModelDB model page URL.")
        parts = tuple(part for part in parsed.path.split("/") if part)
        if len(parts) != 2 or parts[0] != "models":
            raise ValueError("Expected an OpenModelDB model page URL.")
        model = self._openmodeldb.load().model(parts[1])
        resource = _preferred_resource(model)
        if model is None or resource is None:
            return None
        return _recommendation(model, resource, rank=1)


class ProviderRecommendationThumbnailFetcher:
    """Route onboarding thumbnails to their provider-specific cache adapter."""

    def __init__(
        self,
        *,
        civitai: RecommendationThumbnailFetcher,
        openmodeldb: CachedOpenModelDbThumbnailFetcher,
    ) -> None:
        """Store provider-specific bounded thumbnail fetchers."""

        self._civitai = civitai
        self._openmodeldb = openmodeldb

    def fetch(self, recommendation: ModelRecommendation) -> ThumbnailAsset:
        """Return a cached thumbnail from the recommendation's provider."""

        if recommendation.provider_id == "openmodeldb":
            if recommendation.thumbnail_url is None:
                raise ValueError("The OpenModelDB model has no preview image.")
            return self._openmodeldb.fetch_exact(
                sha256=recommendation.sha256,
                thumbnail_url=recommendation.thumbnail_url,
            )
        return self._civitai.fetch(recommendation)


def _preferred_resource(
    model: OpenModelDbModel | None,
) -> OpenModelDbResource | None:
    """Return the preferred exact resource with one allowed direct URL."""

    if model is None:
        return None
    for resource_type in ("safetensors", "pth"):
        for resource in model.resources:
            if resource.resource_type != resource_type:
                continue
            if any(_supported_url(url) for url in resource.urls):
                return resource
    return None


def _supported_url(url: str) -> bool:
    """Return whether one OpenModelDB resource URL passes acquisition policy."""

    try:
        require_openmodeldb_download_url(url)
    except ModelAcquisitionError:
        return False
    return True


def _recommendation(
    model: OpenModelDbModel,
    resource: OpenModelDbResource,
    *,
    rank: int,
) -> ModelRecommendation:
    """Adapt one exact OpenModelDB resource to onboarding recommendation data."""

    download_url = next(url for url in resource.urls if _supported_url(url))
    identity = int(resource.sha256[:12], 16)
    version_name = " · ".join(
        part
        for part in (
            f"{model.scale}×" if model.scale is not None else None,
            model.architecture.upper() if model.architecture else None,
        )
        if part is not None
    )
    return ModelRecommendation(
        family_id=ModelFamilyId.UPSCALERS,
        model_id=identity,
        version_id=identity,
        model_name=model.name,
        version_name=version_name or "Upscaler",
        creator=model.author,
        file_name=(
            f"{model.model_id}.{resource.resource_type}"
            if resource.file_name == f"model.{resource.resource_type}"
            else resource.file_name
        ),
        size_bytes=resource.size_bytes,
        sha256=resource.sha256.upper(),
        download_url=download_url,
        model_page_url=model.model_page_url,
        thumbnail_image_id=identity,
        thumbnail_url=model.thumbnail_url,
        popularity_rank=rank,
        provider_id="openmodeldb",
        provider_name="OpenModelDB",
    )


__all__ = [
    "ProviderRecommendationGateway",
    "ProviderRecommendationThumbnailFetcher",
]
