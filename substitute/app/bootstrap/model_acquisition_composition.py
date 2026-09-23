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

"""Compose model discovery, update, and provider acquisition adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.app.bootstrap.model_suggestion_composition import (
    compose_model_suggestion_service,
)
from substitute.app.bootstrap.openmodeldb_composition import (
    OpenModelDbRuntime,
    build_openmodeldb_runtime,
)
from substitute.application.cache_lifecycle import PreparedCacheCatalog
from substitute.application.civitai import (
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.model_suggestions import ModelSuggestionService
from substitute.infrastructure.model_recommendations.cached_thumbnail_fetcher import (
    RecommendationThumbnailPreparer,
)
from substitute.infrastructure.model_suggestions import (
    OpenModelDbThumbnailMetadataStore,
)
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_updates import ModelUpdateAcquisitionService


@dataclass(frozen=True, slots=True)
class ModelAcquisitionRuntime:
    """Carry the model acquisition services composed for one managed root."""

    openmodeldb: OpenModelDbRuntime
    updates: ModelUpdateAcquisitionService | None
    suggestions: ModelSuggestionService | None


def build_model_acquisition_runtime(
    *,
    model_root: Path | None,
    prepared_caches: PreparedCacheCatalog,
    credentials: CivitaiCredentialService,
    preferences: CivitaiPreferenceService,
    thumbnail_preparer: RecommendationThumbnailPreparer,
    thumbnail_store: OpenModelDbThumbnailMetadataStore,
) -> ModelAcquisitionRuntime:
    """Build exact-hash acquisition services for the active model root."""

    openmodeldb = build_openmodeldb_runtime(
        prepared_caches=prepared_caches,
        thumbnail_preparer=thumbnail_preparer,
        thumbnail_store=thumbnail_store,
        model_root=model_root,
    )
    updates = (
        ModelUpdateAcquisitionService(
            model_root=model_root,
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                api_key_provider=credentials.load_api_key,
            ),
        )
        if model_root is not None
        else None
    )
    return ModelAcquisitionRuntime(
        openmodeldb=openmodeldb,
        updates=updates,
        suggestions=compose_model_suggestion_service(
            model_root=model_root,
            credentials=credentials,
            preferences=preferences,
            thumbnails=thumbnail_preparer,
            thumbnail_assets=thumbnail_store,
            openmodeldb_catalog=openmodeldb.catalog,
        ),
    )


__all__ = ["ModelAcquisitionRuntime", "build_model_acquisition_runtime"]
