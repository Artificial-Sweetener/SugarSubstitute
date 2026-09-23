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

"""Expose external model-suggestion provider adapters."""

from substitute.infrastructure.model_suggestions.civitai_provider import (
    CivitaiModelSuggestionProvider,
)
from substitute.infrastructure.model_suggestions.openmodeldb_catalog import (
    OpenModelDbCatalogClient,
)
from substitute.infrastructure.model_suggestions.openmodeldb_model_catalog import (
    OpenModelDbModelCatalogProvider,
    OpenModelDbThumbnailMetadataStore,
)
from substitute.infrastructure.model_suggestions.openmodeldb_recipe_recovery import (
    OpenModelDbRecipeRecoveryGateway,
)
from substitute.infrastructure.model_suggestions.openmodeldb_recipe_acquisition import (
    OpenModelDbRecipeAcquirer,
)
from substitute.infrastructure.model_suggestions.openmodeldb_provider import (
    CachedOpenModelDbThumbnailFetcher,
    OpenModelDbSuggestionProvider,
    OpenModelDbThumbnailFetcher,
    require_openmodeldb_download_url,
)

__all__ = [
    "CachedOpenModelDbThumbnailFetcher",
    "CivitaiModelSuggestionProvider",
    "OpenModelDbCatalogClient",
    "OpenModelDbModelCatalogProvider",
    "OpenModelDbThumbnailMetadataStore",
    "OpenModelDbRecipeRecoveryGateway",
    "OpenModelDbRecipeAcquirer",
    "OpenModelDbSuggestionProvider",
    "OpenModelDbThumbnailFetcher",
    "require_openmodeldb_download_url",
]
