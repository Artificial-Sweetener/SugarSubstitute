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

"""Define application ports for model metadata refresh orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendFingerprintJob,
    BackendHashLookupResult,
    BackendModelCatalogChangeEvent,
    BackendModelDownloadJob,
    BackendModelCatalogEntry,
    CivitaiImage,
    CivitaiLookupResult,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailAsset,
    ThumbnailStoreResult,
)


@dataclass(frozen=True)
class ModelMetadataRefreshEvent:
    """Describe one metadata cache update produced by a refresh run."""

    kind: str
    value: str
    relative_path: str
    sha256: str
    provider_status: str
    metadata_updated: bool = True
    thumbnail_updated: bool = False


class BackendModelMetadataGateway(Protocol):
    """Describe Substitute BackEnd model metadata operations."""

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return backend capabilities or ``None`` when unavailable."""

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return Comfy-visible model catalog entries for requested kinds."""

    def refresh_fingerprints(
        self, entries: tuple[BackendModelCatalogEntry, ...]
    ) -> BackendFingerprintJob:
        """Queue SHA256 fingerprint refresh for selected entries."""

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return a fingerprint job status by identifier."""


class BackendModelCatalogChangeGateway(Protocol):
    """Describe reconnect recovery for backend model catalog change events."""

    def get_latest_model_catalog_change(
        self,
    ) -> BackendModelCatalogChangeEvent | None:
        """Return the latest backend model catalog change for reconnect recovery."""


class BackendModelHashLookupGateway(Protocol):
    """Describe backend model hash lookup operations used during recipe load."""

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult | None:
        """Return local backend model matches for a SHA256 value."""


class BackendModelDownloadGateway(Protocol):
    """Describe backend model download operations used by resolver flows."""

    def start_civitai_model_download(
        self,
        *,
        kind: str,
        sha256: str,
        download_url: str,
        file_name: str,
        file_type: str | None,
        metadata_format: str | None,
        pickle_scan_result: str | None,
        virus_scan_result: str | None,
        download_path_pattern: str,
        download_path_tokens: Mapping[str, str],
        api_key: str | None,
    ) -> BackendModelDownloadJob | None:
        """Queue a backend-owned CivitAI model download."""

    def get_model_download_job(self, job_id: str) -> BackendModelDownloadJob | None:
        """Return a model download job by identifier."""

    def cancel_model_download_job(self, job_id: str) -> BackendModelDownloadJob | None:
        """Request cancellation for one backend model download job."""


class CivitaiMetadataGateway(Protocol):
    """Describe CivitAI metadata lookup operations."""

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Return CivitAI metadata for a model SHA256 value."""


class ModelMetadataCatalogRepository(Protocol):
    """Persist enriched model metadata records under Substitute user data."""

    def is_fresh(self, evidence: LocalModelEvidence) -> bool:
        """Return whether cached provider metadata is fresh for local evidence."""

    def record_for_sha256(self, sha256: str) -> ModelMetadataCacheRecord | None:
        """Return one cached metadata record by SHA256 when available."""

    def save_record(self, record: ModelMetadataCacheRecord) -> None:
        """Persist one enriched model metadata record."""

    def save_not_found(self, evidence: LocalModelEvidence, *, fetched_at: str) -> None:
        """Persist a provider-not-found result for one local model."""


class ModelMetadataCatalogQueryRepository(Protocol):
    """Read enriched model metadata records from Substitute user data."""

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return cached metadata records, optionally filtered by model kind."""


class ModelThumbnailRepository(Protocol):
    """Persist selected provider thumbnail images."""

    def cache_thumbnail(
        self,
        *,
        sha256: str,
        image: CivitaiImage,
        selection_policy: str,
    ) -> ThumbnailStoreResult | None:
        """Download and cache one selected thumbnail image."""

    def cache_local_thumbnail(
        self,
        *,
        sha256: str,
        image: object | None,
        source: str,
        source_label: str,
        source_path: str | None = None,
        source_width: int | None = None,
        source_height: int | None = None,
    ) -> ThumbnailStoreResult | None:
        """Cache a local image as the selected thumbnail for one model."""


class ThumbnailAssetRepository(Protocol):
    """Read prepared thumbnail assets by logical storage key."""

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one prepared thumbnail asset, or ``None`` when missing."""


class ModelMetadataProgressSink(Protocol):
    """Emit user-visible progress lines for metadata startup refresh."""

    def emit_line(self, line: str) -> None:
        """Emit one stable progress line."""

    def emit_progress(self, line: str) -> None:
        """Emit one transient progress line that may be redrawn."""


class ModelMetadataUpdateSink(Protocol):
    """Emit structured metadata update events to live UI listeners."""

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Emit one committed model metadata update event."""


class RefreshCancellationToken(Protocol):
    """Report whether a running metadata refresh should stop early."""

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""


__all__ = [
    "BackendModelMetadataGateway",
    "BackendModelCatalogChangeGateway",
    "BackendModelHashLookupGateway",
    "BackendModelDownloadGateway",
    "CivitaiMetadataGateway",
    "ModelMetadataCatalogQueryRepository",
    "ModelMetadataCatalogRepository",
    "ModelMetadataProgressSink",
    "ModelMetadataRefreshEvent",
    "ModelMetadataUpdateSink",
    "ModelThumbnailRepository",
    "RefreshCancellationToken",
    "ThumbnailAssetRepository",
]
