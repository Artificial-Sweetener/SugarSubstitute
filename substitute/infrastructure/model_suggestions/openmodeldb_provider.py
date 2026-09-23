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

"""Adapt curated OpenModelDB upscalers to provider-neutral suggestions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

from substitute.application.model_suggestions import CURATED_UPSCALERS
from substitute.domain.model_metadata import (
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailAsset,
)
from substitute.domain.model_suggestions import (
    ModelAcquisitionOffer,
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionAccessPolicy,
    ModelSuggestionContext,
    ModelSuggestionReference,
)
from substitute.infrastructure.model_recommendations.cached_thumbnail_fetcher import (
    RecommendationThumbnailAssetStore,
    RecommendationThumbnailPreparer,
)
from sugarsubstitute_shared.model_acquisition import (
    AcquisitionResult,
    CancellationProbe,
    ModelAcquisitionError,
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery import DiscoveredModel, ModelArtifactKind
from sugarsubstitute_shared.tls import SystemTrustTlsContext

from .openmodeldb_catalog import (
    OpenModelDbCatalogClient,
    OpenModelDbModel,
    OpenModelDbResource,
)

_THUMBNAIL_CACHE_SIZES = (1024, 512, 256, 128)
_MAXIMUM_THUMBNAIL_BYTES = 5 * 1024 * 1024
_THUMBNAIL_POLICY = "openmodeldb:provider-curated-unrated:v1"
_THUMBNAIL_HOSTS = frozenset({"openmodeldb.info", "i.slow.pics"})
_DIRECT_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "huggingface.co",
        "objectstorage.us-phoenix-1.oraclecloud.com",
        "raw.githubusercontent.com",
    }
)

ThumbnailTransport = Callable[[str, float, int], bytes]


class OpenModelDbThumbnailFetcher:
    """Fetch bounded thumbnails from the catalog's reviewed image hosts."""

    def __init__(
        self,
        *,
        transport: ThumbnailTransport | None = None,
        timeout_seconds: float = 10.0,
        maximum_bytes: int = _MAXIMUM_THUMBNAIL_BYTES,
    ) -> None:
        """Store bounded image transport policy."""

        if timeout_seconds <= 0 or maximum_bytes < 1:
            raise ValueError("Thumbnail transport limits must be positive.")
        self._transport = transport or _fetch_thumbnail
        self._timeout_seconds = timeout_seconds
        self._maximum_bytes = maximum_bytes

    def fetch(self, url: str) -> bytes:
        """Return one bounded image from a reviewed HTTPS thumbnail host."""

        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in _THUMBNAIL_HOSTS
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Thumbnail URL is outside reviewed OpenModelDB hosts.")
        return self._transport(url, self._timeout_seconds, self._maximum_bytes)


class CachedOpenModelDbThumbnailFetcher:
    """Prepare and reuse OpenModelDB thumbnails in the governed model cache."""

    def __init__(
        self,
        *,
        fetcher: OpenModelDbThumbnailFetcher,
        preparer: RecommendationThumbnailPreparer,
        asset_store: RecommendationThumbnailAssetStore,
    ) -> None:
        """Store transport, Qt preparation, and cache collaborators."""

        self._fetcher = fetcher
        self._preparer = preparer
        self._asset_store = asset_store

    def fetch(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Return the cached or newly prepared primary OpenModelDB thumbnail."""

        offer = suggestion.primary_offer
        if offer.thumbnail_url is None:
            raise ValueError("OpenModelDB suggestion has no thumbnail.")
        return self.fetch_exact(
            sha256=suggestion.sha256,
            thumbnail_url=offer.thumbnail_url,
        )

    def fetch_exact(self, *, sha256: str, thumbnail_url: str) -> ThumbnailAsset:
        """Return a cached or newly prepared exact-hash OpenModelDB thumbnail."""

        cached = self._read_largest_cached_thumbnail(sha256)
        if cached is not None:
            return cached
        payload = self._fetcher.fetch(thumbnail_url)
        prepared = self._preparer.cache_local_thumbnail(
            sha256=sha256,
            image=payload,
            source="openmodeldb",
            source_label=thumbnail_url,
            selection_policy=_THUMBNAIL_POLICY,
        )
        if prepared is None:
            raise ValueError("OpenModelDB thumbnail could not be prepared.")
        self._asset_store.replace(sha256, prepared)
        cached = self._read_largest_cached_thumbnail(sha256)
        if cached is None:
            raise OSError("Prepared OpenModelDB thumbnail was not persisted.")
        return cached

    def _read_largest_cached_thumbnail(self, sha256: str) -> ThumbnailAsset | None:
        """Return the largest standard variant produced by the active preparer."""

        for size in _THUMBNAIL_CACHE_SIZES:
            storage_key = f"{sha256.upper()}:{STANDARD_THUMBNAIL_ROLE}:{size}"
            cached = self._asset_store.read_thumbnail_asset(storage_key)
            if cached is not None:
                return cached
        return None


class OpenModelDbSuggestionProvider:
    """Provide reviewed OpenModelDB upscalers and verified acquisition."""

    provider_id = "openmodeldb"

    def __init__(
        self,
        *,
        catalog: OpenModelDbCatalogClient,
        thumbnails: CachedOpenModelDbThumbnailFetcher,
        acquisition: ModelAcquisitionService,
    ) -> None:
        """Store catalog, preview, and transfer owners."""

        self._catalog = catalog
        self._thumbnails = thumbnails
        self._acquisition = acquisition

    def supports(self, context: ModelSuggestionContext) -> bool:
        """Return whether this provider owns the upscale-model role."""

        return context.artifact_kind is ModelArtifactKind.UPSCALE_MODELS

    def suggest(
        self,
        context: ModelSuggestionContext,
        *,
        access_policy: ModelSuggestionAccessPolicy,
        limit: int,
        excluded_sha256: frozenset[str],
    ) -> tuple[ModelSuggestion, ...]:
        """Return reviewed OpenModelDB entries with supported direct resources."""

        _ = access_policy
        if not self.supports(context) or limit < 1:
            return ()
        catalog = self._catalog.load()
        excluded = {value.casefold() for value in excluded_sha256}
        suggestions: list[ModelSuggestion] = []
        for rank, curated in enumerate(CURATED_UPSCALERS, start=1):
            model = catalog.model(curated.model_id)
            resource = _acquirable_resource(model)
            if model is None or resource is None or resource.sha256 in excluded:
                continue
            suggestions.append(_suggestion(context, model, resource, rank=rank))
            if len(suggestions) == limit:
                break
        return tuple(suggestions)

    def browse_url(self, context: ModelSuggestionContext) -> str:
        """Return OpenModelDB's upscale-model catalog."""

        if not self.supports(context):
            raise ValueError("OpenModelDB does not support this model role.")
        return "https://openmodeldb.info/"

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Fetch the governed primary OpenModelDB thumbnail."""

        return self._thumbnails.fetch(suggestion)

    def acquire(
        self,
        suggestion: ModelSuggestion,
        offer: ModelAcquisitionOffer,
        *,
        destination: Path,
        cancellation: CancellationProbe | None,
    ) -> AcquisitionResult:
        """Acquire one exact OpenModelDB resource through the hardened transfer."""

        if offer.reference.provider_id != self.provider_id:
            raise ValueError("OpenModelDB cannot acquire another provider's offer.")
        numeric_identity = int(suggestion.sha256[:8], 16)
        return self._acquisition.acquire(
            DiscoveredModel(
                artifact_kind=ModelArtifactKind.UPSCALE_MODELS,
                model_id=numeric_identity,
                version_id=numeric_identity,
                model_name=suggestion.model_name,
                version_name=suggestion.version_name,
                creator=suggestion.creator,
                base_model=None,
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


def require_openmodeldb_download_url(value: str) -> None:
    """Allow only reviewed direct HTTPS hosts used by OpenModelDB resources."""

    parsed = urlparse(value)
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or hostname not in _DIRECT_DOWNLOAD_HOSTS
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ModelAcquisitionError(
            "OpenModelDB resource does not use a supported direct download host."
        )


def _suggestion(
    context: ModelSuggestionContext,
    model: OpenModelDbModel,
    resource: OpenModelDbResource,
    *,
    rank: int,
) -> ModelSuggestion:
    """Project one catalog resource into provider-neutral semantics."""

    offer = ModelAcquisitionOffer(
        reference=ModelSuggestionReference(
            provider_id="openmodeldb",
            provider_name="OpenModelDB",
            model_id=model.model_id,
            version_id=resource.sha256,
            thumbnail_id=model.thumbnail_url,
        ),
        file_name=_resource_file_name(model, resource),
        size_bytes=resource.size_bytes,
        download_url=resource.urls[0],
        model_page_url=model.model_page_url,
        thumbnail_url=model.thumbnail_url,
        provider_rank=rank,
        access=ModelSuggestionAccess.PUBLIC,
    )
    return ModelSuggestion(
        context=context,
        model_name=model.name,
        version_name=_version_name(model),
        creator=model.author,
        sha256=resource.sha256,
        offers=(offer,),
    )


def _acquirable_resource(
    model: OpenModelDbModel | None,
) -> OpenModelDbResource | None:
    """Return the preferred resource with a supported direct URL."""

    if model is None:
        return None
    for resource_type in ("safetensors", "pth"):
        for resource in model.resources:
            if resource.resource_type != resource_type:
                continue
            for url in resource.urls:
                try:
                    require_openmodeldb_download_url(url)
                except ModelAcquisitionError:
                    continue
                return replace(resource, urls=(url,))
    return None


def _resource_file_name(
    model: OpenModelDbModel,
    resource: OpenModelDbResource,
) -> str:
    """Return a provider file name, falling back to the stable model id."""

    file_name = resource.file_name
    if file_name == f"model.{resource.resource_type}":
        return f"{model.model_id}.{resource.resource_type}"
    return file_name


def _version_name(model: OpenModelDbModel) -> str:
    """Return concise architecture and scale metadata for the card subtitle."""

    parts = tuple(
        part
        for part in (
            f"{model.scale}×" if model.scale is not None else None,
            model.architecture.upper() if model.architecture is not None else None,
        )
        if part is not None
    )
    return " · ".join(parts) or "Upscaler"


def _fetch_thumbnail(url: str, timeout: float, maximum_bytes: int) -> bytes:
    """Fetch and validate one bounded OpenModelDB image response."""

    request = urllib.request.Request(
        url,
        headers={"Accept": "image/*", "User-Agent": "SugarSubstitute/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(  # noqa: S310 - caller validates exact HTTPS host.
        request,
        timeout=timeout,
        context=SystemTrustTlsContext.create(),
    ) as response:
        content_type = response.headers.get_content_type()
        declared = response.headers.get("Content-Length")
        if not content_type.casefold().startswith("image/"):
            raise ValueError("OpenModelDB thumbnail response is not an image.")
        if declared is not None and int(declared) > maximum_bytes:
            raise ValueError("OpenModelDB thumbnail exceeds the size limit.")
        raw_payload = response.read(maximum_bytes + 1)
        if not isinstance(raw_payload, bytes):
            raise ValueError("OpenModelDB thumbnail response returned invalid bytes.")
        payload = raw_payload
    if not payload or len(payload) > maximum_bytes:
        raise ValueError("OpenModelDB thumbnail size is outside policy.")
    return payload


__all__ = [
    "CachedOpenModelDbThumbnailFetcher",
    "OpenModelDbSuggestionProvider",
    "OpenModelDbThumbnailFetcher",
    "require_openmodeldb_download_url",
]
