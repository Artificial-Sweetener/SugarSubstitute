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

"""Enrich installed upscalers from OpenModelDB exact-hash catalog matches."""

from __future__ import annotations

import logging
from typing import Protocol

from substitute.application.model_metadata import (
    ModelCatalogProviderMatch,
    ModelProviderLink,
)
from substitute.domain.model_metadata import ThumbnailStoreResult
from substitute.infrastructure.model_recommendations.cached_thumbnail_fetcher import (
    RecommendationThumbnailAssetStore,
    RecommendationThumbnailPreparer,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind

from .openmodeldb_catalog import OpenModelDbCatalogClient, OpenModelDbCatalogError
from .openmodeldb_provider import OpenModelDbThumbnailFetcher

_LOGGER = logging.getLogger(__name__)
_THUMBNAIL_POLICY = "openmodeldb:exact-hash-unrated:v1"


class OpenModelDbThumbnailMetadataStore(RecommendationThumbnailAssetStore, Protocol):
    """Persist and query prepared OpenModelDB thumbnail metadata."""

    def result_for_sha256(self, sha256: str) -> ThumbnailStoreResult | None:
        """Return prepared thumbnail metadata without loading image payloads."""


class OpenModelDbModelCatalogProvider:
    """Resolve OpenModelDB display metadata for installed upscaler hashes."""

    def __init__(
        self,
        *,
        catalog: OpenModelDbCatalogClient,
        thumbnail_fetcher: OpenModelDbThumbnailFetcher,
        thumbnail_preparer: RecommendationThumbnailPreparer,
        thumbnail_store: OpenModelDbThumbnailMetadataStore,
    ) -> None:
        """Store exact-hash catalog and governed thumbnail collaborators."""

        self._catalog = catalog
        self._thumbnail_fetcher = thumbnail_fetcher
        self._thumbnail_preparer = thumbnail_preparer
        self._thumbnail_store = thumbnail_store

    def match(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> ModelCatalogProviderMatch | None:
        """Return OpenModelDB metadata only for an exact upscaler hash match."""

        if kind != ModelArtifactKind.UPSCALE_MODELS.value:
            return None
        normalized_sha256 = sha256.strip().casefold()
        try:
            catalog_match = self._catalog.load().resource_for_sha256(normalized_sha256)
        except OpenModelDbCatalogError as error:
            _LOGGER.warning(
                "OpenModelDB installed-model enrichment is unavailable",
                extra={"kind": kind, "sha256": normalized_sha256.upper()},
                exc_info=error,
            )
            return None
        if catalog_match is None:
            return None
        model, resource = catalog_match
        thumbnail = self._thumbnail_store.result_for_sha256(normalized_sha256)
        if thumbnail is None and model.thumbnail_url is not None:
            thumbnail = self._prepare_thumbnail(
                sha256=normalized_sha256,
                thumbnail_url=model.thumbnail_url,
            )
        version_parts = tuple(
            part
            for part in (
                f"{model.scale}×" if model.scale is not None else None,
                model.architecture.upper() if model.architecture else None,
            )
            if part is not None
        )
        return ModelCatalogProviderMatch(
            link=ModelProviderLink(
                provider_id="openmodeldb",
                provider_name="OpenModelDB",
                model_id=model.model_id,
                version_id=resource.sha256,
                model_page_url=model.model_page_url,
            ),
            model_name=model.name,
            version_name=" · ".join(version_parts) or None,
            tags=model.tags,
            thumbnail=thumbnail,
        )

    def _prepare_thumbnail(
        self,
        *,
        sha256: str,
        thumbnail_url: str,
    ) -> ThumbnailStoreResult | None:
        """Fetch and persist one bounded provider thumbnail best-effort."""

        try:
            payload = self._thumbnail_fetcher.fetch(thumbnail_url)
            prepared = self._thumbnail_preparer.cache_local_thumbnail(
                sha256=sha256,
                image=payload,
                source="openmodeldb",
                source_label=thumbnail_url,
                selection_policy=_THUMBNAIL_POLICY,
            )
            if prepared is not None:
                self._thumbnail_store.replace(sha256, prepared)
            return prepared
        except (OSError, ValueError) as error:
            _LOGGER.warning(
                "OpenModelDB thumbnail enrichment failed",
                extra={"sha256": sha256.upper(), "thumbnail_url": thumbnail_url},
                exc_info=error,
            )
            return None


__all__ = [
    "OpenModelDbModelCatalogProvider",
    "OpenModelDbThumbnailMetadataStore",
]
