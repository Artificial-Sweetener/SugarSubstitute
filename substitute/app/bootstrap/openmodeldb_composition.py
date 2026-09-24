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

"""Compose OpenModelDB catalog enrichment and portable recovery adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.app.bootstrap.persistent_cache_composition import (
    build_openmodeldb_catalog,
)
from substitute.application.cache_lifecycle import PreparedCacheCatalog
from substitute.infrastructure.model_recommendations.cached_thumbnail_fetcher import (
    RecommendationThumbnailPreparer,
)
from substitute.infrastructure.model_suggestions import (
    OpenModelDbCatalogClient,
    OpenModelDbModelCatalogProvider,
    OpenModelDbRecipeAcquirer,
    OpenModelDbRecipeRecoveryGateway,
    OpenModelDbThumbnailFetcher,
    OpenModelDbThumbnailMetadataStore,
    require_openmodeldb_download_url,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import ModelArtifactDestinationPolicy


@dataclass(frozen=True, slots=True)
class OpenModelDbRuntime:
    """Carry one shared catalog and its exact-hash application adapters."""

    catalog: OpenModelDbCatalogClient
    catalog_provider: OpenModelDbModelCatalogProvider
    recovery_gateway: OpenModelDbRecipeRecoveryGateway
    recipe_acquirer: OpenModelDbRecipeAcquirer | None


def build_openmodeldb_runtime(
    *,
    prepared_caches: PreparedCacheCatalog,
    thumbnail_preparer: RecommendationThumbnailPreparer,
    thumbnail_store: OpenModelDbThumbnailMetadataStore,
    model_root: Path | None,
) -> OpenModelDbRuntime:
    """Build OpenModelDB adapters around one governed cached catalog."""

    catalog = build_openmodeldb_catalog(prepared_caches)
    recipe_acquirer = (
        OpenModelDbRecipeAcquirer(
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                download_url_validator=require_openmodeldb_download_url,
                allowed_extensions=(".safetensors", ".pth"),
            ),
            destinations=ModelArtifactDestinationPolicy(model_root),
        )
        if model_root is not None
        else None
    )
    return OpenModelDbRuntime(
        catalog=catalog,
        catalog_provider=OpenModelDbModelCatalogProvider(
            catalog=catalog,
            thumbnail_fetcher=OpenModelDbThumbnailFetcher(),
            thumbnail_preparer=thumbnail_preparer,
            thumbnail_store=thumbnail_store,
        ),
        recovery_gateway=OpenModelDbRecipeRecoveryGateway(catalog),
        recipe_acquirer=recipe_acquirer,
    )


__all__ = ["OpenModelDbRuntime", "build_openmodeldb_runtime"]
