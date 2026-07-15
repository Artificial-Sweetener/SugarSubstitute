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

"""Expose model metadata domain contracts and policies."""

from __future__ import annotations

from substitute.domain.model_metadata.models import (
    BackendCapabilities,
    BackendCubeLibraryCapabilities,
    BackendFingerprint,
    BackendFingerprintJob,
    BackendFingerprintJobEntry,
    BackendHashLookupMatch,
    BackendHashLookupResult,
    BackendLocalPreview,
    BackendModelCatalogEntry,
    BackendModelDownloadJob,
    BackendModelDownloadResult,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    BackendSugarCompileCapabilities,
    BANNER_THUMBNAIL_HEIGHT,
    BANNER_THUMBNAIL_ROLE,
    BANNER_THUMBNAIL_SIZE,
    BANNER_THUMBNAIL_WIDTH,
    CivitaiFile,
    CivitaiImage,
    CivitaiLookupResult,
    CivitaiModelVersion,
    LocalModelEvidence,
    STANDARD_THUMBNAIL_ROLE,
    ModelMetadataCacheRecord,
    ThumbnailSelection,
    ThumbnailAsset,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.domain.model_metadata.change_events import (
    MODEL_CATALOG_CHANGE_EVENT_TYPE,
    MODEL_CATALOG_CHANGE_SCHEMA_VERSION,
    BackendModelCatalogChangeEvent,
    BackendModelCatalogChangedEntry,
    BackendModelCatalogChangedFile,
    BackendModelCatalogChangedSource,
    parse_backend_model_catalog_change_event,
)
from substitute.domain.model_metadata.statuses import (
    BackendHashLookupStatus,
    CivitaiLookupStatus,
    FingerprintStatus,
    JobStatus,
    ModelDownloadStatus,
    ThumbnailSelectionStatus,
)
from substitute.domain.model_metadata.thumbnail_policy import (
    CivitaiThumbnailPolicy,
    FirstSfwThumbnailPolicy,
)

__all__ = [
    "BackendCapabilities",
    "BackendCubeLibraryCapabilities",
    "BackendFingerprint",
    "BackendFingerprintJob",
    "BackendFingerprintJobEntry",
    "BackendHashLookupMatch",
    "BackendHashLookupResult",
    "BackendHashLookupStatus",
    "BackendLocalPreview",
    "BackendModelCatalogChangeEvent",
    "BackendModelCatalogChangedEntry",
    "BackendModelCatalogChangedFile",
    "BackendModelCatalogChangedSource",
    "BackendModelCatalogEntry",
    "BackendModelDownloadJob",
    "BackendModelDownloadResult",
    "BackendModelFile",
    "BackendModelSource",
    "BackendSidecar",
    "BackendSugarCompileCapabilities",
    "BANNER_THUMBNAIL_HEIGHT",
    "BANNER_THUMBNAIL_ROLE",
    "BANNER_THUMBNAIL_SIZE",
    "BANNER_THUMBNAIL_WIDTH",
    "CivitaiFile",
    "CivitaiImage",
    "CivitaiLookupResult",
    "CivitaiLookupStatus",
    "CivitaiModelVersion",
    "CivitaiThumbnailPolicy",
    "FingerprintStatus",
    "FirstSfwThumbnailPolicy",
    "JobStatus",
    "ModelDownloadStatus",
    "LocalModelEvidence",
    "MODEL_CATALOG_CHANGE_EVENT_TYPE",
    "MODEL_CATALOG_CHANGE_SCHEMA_VERSION",
    "ModelMetadataCacheRecord",
    "parse_backend_model_catalog_change_event",
    "STANDARD_THUMBNAIL_ROLE",
    "ThumbnailSelection",
    "ThumbnailAsset",
    "ThumbnailSelectionStatus",
    "ThumbnailStoreResult",
    "ThumbnailVariant",
]
