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

"""Compose independently governed model metadata and thumbnail stores."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.ports.civitai_cache_repository import CivitaiCacheSummary
from substitute.domain.model_metadata import (
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailAsset,
    ThumbnailSelectionStatus,
)
from substitute.infrastructure.persistence.sqlite_model_metadata_store import (
    SqliteModelMetadataStore,
)
from substitute.infrastructure.persistence.sqlite_model_thumbnail_asset_store import (
    SqliteModelThumbnailAssetStore,
)


class ComposedModelMetadataRepository:
    """Present model catalog ports while preserving cache ownership boundaries."""

    def __init__(
        self,
        metadata: SqliteModelMetadataStore,
        thumbnails: SqliteModelThumbnailAssetStore,
    ) -> None:
        """Store the normalized metadata and thumbnail asset collaborators."""

        self._metadata = metadata
        self._thumbnails = thumbnails

    def is_fresh(self, evidence: LocalModelEvidence) -> bool:
        """Return whether metadata and any selected thumbnails are compatible."""

        if not self._metadata.is_fresh(evidence):
            return False
        record = self._metadata.record_for_sha256(evidence.sha256)
        if record is None:
            return False
        if record.thumbnail_status is not ThumbnailSelectionStatus.SELECTED:
            return True
        return self._thumbnails.has_variants(evidence.sha256)

    def record_for_sha256(self, sha256: str) -> ModelMetadataCacheRecord | None:
        """Return one metadata record projected with its thumbnail references."""

        record = self._metadata.record_for_sha256(sha256)
        return self._with_thumbnail(record)

    def save_record(self, record: ModelMetadataCacheRecord) -> None:
        """Persist metadata, then reconcile its independently stored thumbnails."""

        self._metadata.save_record(record)
        self._thumbnails.replace(record.local.sha256, record.thumbnail)

    def save_not_found(self, evidence: LocalModelEvidence, *, fetched_at: str) -> None:
        """Persist a provider miss and remove stale thumbnails for its model hash."""

        self._metadata.save_not_found(evidence, fetched_at=fetched_at)
        self._thumbnails.replace(evidence.sha256, None)

    def save_local_evidence(
        self,
        evidence: LocalModelEvidence,
        *,
        updated_at: str,
    ) -> None:
        """Persist local model evidence and remove stale provider thumbnails."""

        self._metadata.save_local_evidence(evidence, updated_at=updated_at)
        self._thumbnails.replace(evidence.sha256, None)

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return metadata records projected with thumbnail references."""

        return tuple(
            projected
            for record in self._metadata.list_records(kind=kind)
            if (projected := self._with_thumbnail(record)) is not None
        )

    def recipe_hash_revision(self, *, kind: str | None = None) -> tuple[int, str, int]:
        """Return the metadata revision token used by recipe hash indexes."""

        return self._metadata.recipe_hash_revision(kind=kind)

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one prepared thumbnail asset by logical storage key."""

        return self._thumbnails.read_thumbnail_asset(storage_key)

    def cache_summary(self) -> CivitaiCacheSummary:
        """Return combined provider metadata and thumbnail cache usage."""

        source_count, variant_count, variant_bytes = self._thumbnails.summary()
        return CivitaiCacheSummary(
            provider_record_count=self._metadata.provider_record_count(),
            thumbnail_source_count=source_count,
            thumbnail_variant_count=variant_count,
            thumbnail_bytes=variant_bytes,
        )

    def clear_civitai_thumbnails(self) -> None:
        """Clear prepared thumbnails and mark their metadata selections absent."""

        self._thumbnails.clear()
        self._metadata.mark_civitai_thumbnails_stale()

    def clear_civitai_metadata(self) -> None:
        """Clear provider data and thumbnails while retaining local evidence."""

        self._thumbnails.clear()
        self._metadata.clear_civitai_metadata()

    def _with_thumbnail(
        self,
        record: ModelMetadataCacheRecord | None,
    ) -> ModelMetadataCacheRecord | None:
        """Attach thumbnail references from the independent asset store."""

        if record is None:
            return None
        thumbnail = self._thumbnails.result_for_sha256(record.local.sha256)
        return replace(record, thumbnail=thumbnail)


__all__ = ["ComposedModelMetadataRepository"]
