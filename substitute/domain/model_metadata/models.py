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

"""Define model metadata records exchanged between refresh services."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.domain.common import JsonObject
from substitute.domain.model_metadata.statuses import (
    BackendHashLookupStatus,
    CivitaiLookupStatus,
    FingerprintStatus,
    JobStatus,
    ModelDownloadStatus,
    ThumbnailSelectionStatus,
)

BANNER_THUMBNAIL_HEIGHT = 160
BANNER_THUMBNAIL_ROLE = "banner"
BANNER_THUMBNAIL_SIZE = 768
BANNER_THUMBNAIL_WIDTH = 768
STANDARD_THUMBNAIL_ROLE = "standard"


@dataclass(frozen=True)
class BackendCubeLibraryCapabilities:
    """Represent Cube Library capability facts from Substitute BackEnd."""

    schema_version: int = 0
    available: bool = False
    unavailable_reason: str = ""
    sugar_cubes_version: str = ""
    catalog_supported: bool = False
    artifact_load_supported: bool = False
    workflow_compile_supported: bool = False
    pack_management_supported: bool = False
    dependency_readiness_supported: bool = False
    dependency_repair_supported: bool = False
    versioned_dependency_readiness_supported: bool = False
    sync_dependency_orchestration_supported: bool = False


@dataclass(frozen=True)
class BackendSugarCompileCapabilities:
    """Represent Sugar compile capability facts from Substitute BackEnd."""

    schema_version: int = 0
    available: bool = False
    unavailable_reason: str = ""
    compile_route: str = ""
    sugar_dsl_version: str = ""


@dataclass(frozen=True)
class BackendCapabilities:
    """Represent the backend model metadata feature contract."""

    api_version: int
    model_metadata_schema_version: int
    supported_model_kinds: tuple[str, ...]
    background_hashing: bool
    hash_lookup: bool
    local_preview_serving: bool
    sidecar_reading: bool
    extension_version: str = ""
    features: tuple[str, ...] = ()
    cube_library: BackendCubeLibraryCapabilities = field(
        default_factory=BackendCubeLibraryCapabilities
    )
    sugar_compile: BackendSugarCompileCapabilities = field(
        default_factory=BackendSugarCompileCapabilities
    )


@dataclass(frozen=True)
class BackendModelSource:
    """Identify a Comfy-visible model without exposing absolute paths."""

    root_id: str
    relative_path: str


@dataclass(frozen=True)
class BackendModelFile:
    """Describe safe file freshness data returned by Substitute BackEnd."""

    extension: str
    size_bytes: int
    modified_at: str
    created_at: str | None


@dataclass(frozen=True)
class BackendFingerprint:
    """Describe backend SHA256 evidence for one model catalog entry."""

    status: FingerprintStatus
    sha256: str | None
    source: str | None
    computed_at: str | None
    error: str | None


@dataclass(frozen=True)
class BackendSidecar:
    """Summarize local model sidecar metadata observed by the backend."""

    found: bool
    model_id: int | None
    model_version_id: int | None
    sha256: str | None
    activation_text: str | None
    description: str | None
    base_model: str | None
    modified_at: str | None


@dataclass(frozen=True)
class BackendLocalPreview:
    """Reference a backend-served local preview image."""

    available: bool
    preview_id: str | None
    url: str | None
    source: str | None
    modified_at: str | None
    width: int | None
    height: int | None


@dataclass(frozen=True)
class BackendModelCatalogEntry:
    """Represent one Comfy-visible model entry returned by the backend."""

    schema_version: int
    target_id: str
    kind: str
    value: str
    display_name: str
    source: BackendModelSource
    file: BackendModelFile
    fingerprint: BackendFingerprint
    sidecar: BackendSidecar
    local_preview: BackendLocalPreview


@dataclass(frozen=True)
class BackendFingerprintJobEntry:
    """Represent one backend fingerprint job entry."""

    kind: str
    value: str
    status: JobStatus
    sha256: str | None
    error: str | None


@dataclass(frozen=True)
class BackendFingerprintJob:
    """Represent backend fingerprint job progress."""

    job_id: str
    status: JobStatus
    entries: tuple[BackendFingerprintJobEntry, ...]


@dataclass(frozen=True)
class BackendHashLookupMatch:
    """Represent a backend-visible local model matching a requested hash."""

    kind: str
    value: str
    display_name: str
    source: BackendModelSource
    file: BackendModelFile


@dataclass(frozen=True)
class BackendHashLookupResult:
    """Represent the backend local hash lookup outcome."""

    status: BackendHashLookupStatus
    kind: str
    sha256: str
    matches: tuple[BackendHashLookupMatch, ...]
    job_id: str | None


@dataclass(frozen=True)
class BackendModelDownloadResult:
    """Represent a verified model file downloaded by Substitute BackEnd."""

    kind: str
    value: str
    display_name: str
    source: BackendModelSource
    sha256: str
    file: BackendModelFile


@dataclass(frozen=True)
class BackendModelDownloadJob:
    """Represent a backend model download job."""

    job_id: str
    status: ModelDownloadStatus
    kind: str
    sha256: str
    value: str | None
    result: BackendModelDownloadResult | None
    error: str | None
    bytes_downloaded: int | None = None
    bytes_total: int | None = None
    detail: str | None = None


@dataclass(frozen=True)
class CivitaiFile:
    """Represent file metadata from a CivitAI model version."""

    file_id: int | None
    name: str
    size_kb: float | None
    file_type: str | None
    download_url: str | None
    pickle_scan_result: str | None
    virus_scan_result: str | None
    primary: bool
    hashes: JsonObject
    metadata: JsonObject


@dataclass(frozen=True)
class CivitaiImage:
    """Represent an image candidate from a CivitAI model version."""

    image_id: int | None
    url: str
    image_type: str | None
    nsfw: bool | None
    nsfw_level: str | int | None
    width: int | None
    height: int | None
    meta: JsonObject | None


@dataclass(frozen=True)
class CivitaiModelVersion:
    """Represent normalized CivitAI model and matched version metadata."""

    model_id: int
    model_version_id: int
    model_name: str
    model_type: str | None
    version_name: str
    base_model: str | None
    trained_words: tuple[str, ...]
    description: str | None
    version_description: str | None
    tags: tuple[str, ...]
    creator_username: str | None
    creator_image: str | None
    nsfw: bool | None
    nsfw_level: str | int | None
    availability: str | None
    files: tuple[CivitaiFile, ...]
    images: tuple[CivitaiImage, ...]
    stats: JsonObject
    model_page_url: str
    source_url: str
    fetched_at: str
    raw_provider_payload: JsonObject


@dataclass(frozen=True)
class CivitaiLookupResult:
    """Represent the outcome of a CivitAI model-version lookup."""

    status: CivitaiLookupStatus
    version: CivitaiModelVersion | None = None
    error: str | None = None


@dataclass(frozen=True)
class ThumbnailSelection:
    """Represent the thumbnail policy decision for one model version."""

    status: ThumbnailSelectionStatus
    image: CivitaiImage | None
    policy: str


@dataclass(frozen=True)
class ThumbnailVariant:
    """Reference one prepared thumbnail asset derived from a provider image."""

    size: int
    storage_key: str
    width: int
    height: int
    content_format: str
    byte_size: int
    role: str = STANDARD_THUMBNAIL_ROLE

    def to_json(self) -> JsonObject:
        """Return a stable JSON representation for cache persistence."""

        return {
            "role": self.role,
            "size": self.size,
            "storageKey": self.storage_key,
            "width": self.width,
            "height": self.height,
            "contentFormat": self.content_format,
            "byteSize": self.byte_size,
        }


@dataclass(frozen=True)
class ThumbnailStoreResult:
    """Represent prepared thumbnail assets and their provider source data."""

    source: str
    selection_policy: str
    source_image_url: str
    source_image_id: int | None
    nsfw: bool | None
    nsfw_level: str | int | None
    source_width: int | None
    source_height: int | None
    variants: tuple[ThumbnailVariant, ...]
    downloaded_at: str
    assets: tuple["ThumbnailAsset", ...] = ()

    def to_json(self) -> JsonObject:
        """Return a stable JSON representation for cache persistence."""

        return {
            "source": self.source,
            "selectionPolicy": self.selection_policy,
            "sourceImageUrl": self.source_image_url,
            "sourceImageId": self.source_image_id,
            "nsfw": self.nsfw,
            "nsfwLevel": self.nsfw_level,
            "sourceWidth": self.source_width,
            "sourceHeight": self.source_height,
            "variants": [variant.to_json() for variant in self.variants],
            "downloadedAt": self.downloaded_at,
        }


@dataclass(frozen=True)
class ThumbnailAsset:
    """Carry one Qt-ready thumbnail payload read from durable storage."""

    storage_key: str
    width: int
    height: int
    qt_format: int
    bytes_per_line: int
    content_format: str
    payload: bytes


@dataclass(frozen=True)
class LocalModelEvidence:
    """Represent local freshness evidence used for cache validation."""

    target_id: str
    root_id: str
    relative_path: str
    kind: str
    value: str
    display_name: str
    size_bytes: int
    modified_at: str
    sha256: str

    @classmethod
    def from_backend_entry(
        cls, entry: BackendModelCatalogEntry, sha256: str
    ) -> LocalModelEvidence:
        """Build local cache evidence from a backend model entry and SHA256."""

        return cls(
            target_id=entry.target_id,
            root_id=entry.source.root_id,
            relative_path=entry.source.relative_path,
            kind=entry.kind,
            value=entry.value,
            display_name=entry.display_name,
            size_bytes=entry.file.size_bytes,
            modified_at=entry.file.modified_at,
            sha256=sha256.upper(),
        )

    def to_json(self) -> JsonObject:
        """Return a stable JSON representation for cache persistence."""

        return {
            "targetId": self.target_id,
            "rootId": self.root_id,
            "relativePath": self.relative_path,
            "kind": self.kind,
            "value": self.value,
            "displayName": self.display_name,
            "sizeBytes": self.size_bytes,
            "modifiedAt": self.modified_at,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ModelMetadataCacheRecord:
    """Represent one persisted enriched metadata cache record."""

    schema_version: int
    local: LocalModelEvidence
    provider: CivitaiModelVersion | None
    provider_status: str
    thumbnail: ThumbnailStoreResult | None
    thumbnail_status: ThumbnailSelectionStatus
    updated_at: str


__all__ = [
    "BackendCapabilities",
    "BackendCubeLibraryCapabilities",
    "BackendFingerprint",
    "BackendFingerprintJob",
    "BackendFingerprintJobEntry",
    "BackendHashLookupMatch",
    "BackendHashLookupResult",
    "BackendLocalPreview",
    "BackendModelCatalogEntry",
    "BackendModelFile",
    "BackendModelDownloadJob",
    "BackendModelDownloadResult",
    "BackendModelSource",
    "BackendSidecar",
    "BANNER_THUMBNAIL_HEIGHT",
    "BANNER_THUMBNAIL_ROLE",
    "BANNER_THUMBNAIL_SIZE",
    "BANNER_THUMBNAIL_WIDTH",
    "CivitaiFile",
    "CivitaiImage",
    "CivitaiLookupResult",
    "CivitaiModelVersion",
    "LocalModelEvidence",
    "ModelMetadataCacheRecord",
    "ThumbnailSelection",
    "ThumbnailAsset",
    "ThumbnailStoreResult",
    "ThumbnailVariant",
    "STANDARD_THUMBNAIL_ROLE",
]
