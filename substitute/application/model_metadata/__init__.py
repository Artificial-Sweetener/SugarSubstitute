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

"""Expose model metadata application services and port contracts."""

from __future__ import annotations

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    BackendModelCatalogChangeEvent,
    BackendModelCatalogChangedEntry,
    BackendModelDownloadJob,
    ModelDownloadStatus,
    STANDARD_THUMBNAIL_ROLE,
)
from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
    BackendModelCatalogChangeGateway,
    CivitaiMetadataGateway,
    ModelMetadataCatalogRepository,
    ModelMetadataCatalogQueryRepository,
    ModelMetadataProgressSink,
    ModelMetadataRefreshEvent,
    ModelMetadataUpdateSink,
    ModelThumbnailRepository,
    RefreshCancellationToken,
    ThumbnailAssetRepository,
)
from substitute.application.model_metadata.model_catalog_service import (
    ModelCatalogItem,
    ModelCatalogLookup,
    ModelCatalogService,
    ModelCatalogSnapshot,
    ModelThumbnailVariant,
)
from substitute.application.model_metadata.model_catalog_snapshot_store import (
    ModelCatalogSnapshotStore,
)
from substitute.application.model_metadata.model_choice_catalog_index import (
    DEFAULT_RICH_CHOICE_MODEL_KINDS,
    ModelChoiceCatalogIndex,
)
from substitute.application.model_metadata.model_family_resolver import (
    ModelFamily,
    model_family_associations_for_catalog_item,
    resolve_model_families_for_catalog_item,
)
from substitute.application.model_metadata.model_field_kind_resolver import (
    model_kind_for_field,
)
from substitute.application.model_metadata.prompt_preset_scope_resolver import (
    PromptPresetScopeOption,
    exact_model_association_for_catalog_item,
    prompt_preset_listing_associations_for_catalog_item,
    prompt_preset_scope_options_for_catalog_item,
)
from substitute.application.model_metadata.refresh_service import (
    DEFAULT_MODEL_KINDS,
    ModelMetadataRefreshService,
    ModelMetadataRefreshSummary,
)
from substitute.application.model_metadata.manual_refresh_service import (
    ManualModelMetadataRefreshRequest,
    ManualModelMetadataRefreshResult,
    ManualModelMetadataRefreshService,
    ManualModelMetadataRefreshStatus,
)
from substitute.application.model_metadata.output_thumbnail_service import (
    SetModelThumbnailFromOutputRequest,
    SetModelThumbnailFromOutputResult,
    SetModelThumbnailFromOutputService,
    SetModelThumbnailFromOutputStatus,
)
from substitute.application.model_metadata.rich_choice_models import (
    RichChoiceItem,
    RichChoiceResolution,
    RichChoiceSource,
)
from substitute.application.model_metadata.rich_choice_resolver import (
    ResolvedRichChoiceSource,
    RichChoiceContext,
    RichChoiceResolver,
)
from substitute.application.model_metadata.scoped_metadata_refresh_service import (
    DEFAULT_SCOPED_METADATA_BATCH_SIZE,
    ScopedMetadataRefreshService,
)

__all__ = [
    "BANNER_THUMBNAIL_ROLE",
    "BackendModelMetadataGateway",
    "BackendModelCatalogChangeGateway",
    "BackendModelCatalogChangeEvent",
    "BackendModelCatalogChangedEntry",
    "BackendModelDownloadJob",
    "CivitaiMetadataGateway",
    "DEFAULT_MODEL_KINDS",
    "DEFAULT_RICH_CHOICE_MODEL_KINDS",
    "DEFAULT_SCOPED_METADATA_BATCH_SIZE",
    "ModelCatalogItem",
    "ModelCatalogLookup",
    "ModelCatalogService",
    "ModelCatalogSnapshot",
    "ModelCatalogSnapshotStore",
    "ModelChoiceCatalogIndex",
    "ModelDownloadStatus",
    "ManualModelMetadataRefreshRequest",
    "ManualModelMetadataRefreshResult",
    "ManualModelMetadataRefreshService",
    "ManualModelMetadataRefreshStatus",
    "ModelFamily",
    "ModelMetadataCatalogRepository",
    "ModelMetadataCatalogQueryRepository",
    "ModelMetadataProgressSink",
    "ModelMetadataRefreshEvent",
    "ModelMetadataRefreshService",
    "ModelMetadataRefreshSummary",
    "ModelMetadataUpdateSink",
    "ModelThumbnailRepository",
    "ModelThumbnailVariant",
    "model_family_associations_for_catalog_item",
    "model_kind_for_field",
    "PromptPresetScopeOption",
    "exact_model_association_for_catalog_item",
    "prompt_preset_listing_associations_for_catalog_item",
    "prompt_preset_scope_options_for_catalog_item",
    "RefreshCancellationToken",
    "ResolvedRichChoiceSource",
    "RichChoiceContext",
    "RichChoiceItem",
    "RichChoiceResolution",
    "RichChoiceResolver",
    "RichChoiceSource",
    "resolve_model_families_for_catalog_item",
    "ScopedMetadataRefreshService",
    "SetModelThumbnailFromOutputRequest",
    "SetModelThumbnailFromOutputResult",
    "SetModelThumbnailFromOutputService",
    "SetModelThumbnailFromOutputStatus",
    "STANDARD_THUMBNAIL_ROLE",
    "ThumbnailAssetRepository",
]
