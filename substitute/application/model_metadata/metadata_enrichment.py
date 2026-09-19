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

"""Enrich hash-ready models and publish committed metadata changes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from substitute.application.model_metadata.ports import (
    CivitaiMetadataGateway,
    ModelMetadataCatalogRepository,
    ModelMetadataProgressSink,
    ModelMetadataRefreshEvent,
    ModelThumbnailRepository,
    RefreshCancellationToken,
)
from substitute.application.civitai import CivitaiPreferenceService
from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.domain.model_metadata import (
    BackendModelCatalogEntry,
    CivitaiLookupStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
)
from substitute.domain.model_metadata.thumbnail_policy import (
    CivitaiThumbnailPolicy,
    FirstSfwThumbnailPolicy,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_warning


from .fingerprint_refresh import ready_sha256
from .refresh_summary import ModelMetadataRefreshSummary

_LOGGER = get_logger("application.model_metadata.metadata_enrichment")


class ModelMetadataEnrichmentService:
    """Own provider lookup, policy selection, and metadata publication."""

    def __init__(
        self,
        *,
        civitai: CivitaiMetadataGateway,
        catalog: ModelMetadataCatalogRepository,
        thumbnails: ModelThumbnailRepository,
        thumbnail_policy: CivitaiThumbnailPolicy | None,
        civitai_preferences: CivitaiPreferenceService | None,
        clock: Callable[[], str] | None,
    ) -> None:
        """Store metadata persistence, provider, and thumbnail policy boundaries."""
        self._civitai = civitai
        self._catalog = catalog
        self._thumbnails = thumbnails
        self._thumbnail_policy = thumbnail_policy or FirstSfwThumbnailPolicy()
        self._civitai_preferences = civitai_preferences
        self._clock = clock or _utc_now

    def enrich(
        self,
        *,
        models: tuple[BackendModelCatalogEntry, ...],
        refreshed_hashes: dict[tuple[str, str], str],
        progress: ModelMetadataProgressSink,
        cancellation: RefreshCancellationToken,
    ) -> ModelMetadataRefreshSummary:
        """Query CivitAI and persist cache records for hash-ready models."""

        candidates = [
            (
                entry,
                ready_sha256(entry) or refreshed_hashes.get((entry.kind, entry.value)),
            )
            for entry in models
        ]
        hash_ready = [
            (entry, sha256) for entry, sha256 in candidates if sha256 is not None
        ]
        preferences = (
            self._civitai_preferences.load_preferences()
            if self._civitai_preferences is not None
            else None
        )
        if preferences is not None and not preferences.metadata_lookup_enabled:
            progress.emit_line(
                "Model metadata: CivitAI metadata lookup disabled in Settings."
            )
            return ModelMetadataRefreshSummary(skipped=len(hash_ready))
        active_thumbnail_policy = self._thumbnail_policy
        thumbnail_downloads_enabled = True
        if preferences is not None:
            thumbnail_downloads_enabled = preferences.thumbnail_downloads_enabled
            active_thumbnail_policy = CivitaiThumbnailPolicy(
                preferences.thumbnail_safety_policy
                if thumbnail_downloads_enabled
                else CivitaiThumbnailSafetyPolicy.DISABLED
            )
        enriched = 0
        thumbnails_cached = 0
        not_found = 0
        skipped = 0
        no_sfw_thumbnail = 0
        failed = 0
        total = len(hash_ready)
        for index, (entry, sha256) in enumerate(hash_ready, start=1):
            if cancellation.is_cancelled():
                return ModelMetadataRefreshSummary(
                    enriched=enriched,
                    thumbnails_cached=thumbnails_cached,
                    not_found=not_found,
                    skipped=skipped,
                    no_sfw_thumbnail=no_sfw_thumbnail,
                    failed=failed,
                    cancelled=True,
                )
            assert sha256 is not None
            evidence = LocalModelEvidence.from_backend_entry(entry, sha256)
            if self._catalog.is_fresh(evidence):
                skipped += 1
                continue
            progress.emit_progress(
                f"Model metadata: querying CivitAI {index}/{total} - {entry.source.relative_path}\r"
            )
            try:
                result = self._civitai.lookup_model_version_by_hash(evidence.sha256)
            except Exception:
                failed += 1
                log_exception(
                    _LOGGER,
                    "Unexpected CivitAI lookup failure",
                    kind=entry.kind,
                    value=entry.value,
                    sha256=evidence.sha256,
                )
                continue
            if result.status is CivitaiLookupStatus.NOT_FOUND:
                self._catalog.save_not_found(evidence, fetched_at=self._clock())
                _emit_model_updated(
                    progress,
                    ModelMetadataRefreshEvent(
                        kind=entry.kind,
                        value=entry.value,
                        relative_path=entry.source.relative_path,
                        sha256=evidence.sha256,
                        provider_status=result.status.value,
                        thumbnail_updated=False,
                    ),
                )
                not_found += 1
                continue
            if result.status is not CivitaiLookupStatus.FOUND or result.version is None:
                failed += 1
                log_warning(
                    _LOGGER,
                    "CivitAI lookup did not return usable metadata",
                    kind=entry.kind,
                    value=entry.value,
                    sha256=evidence.sha256,
                    status=result.status.value,
                    error=result.error,
                )
                continue
            selection = active_thumbnail_policy.select(result.version)
            cached_thumbnail = None
            if (
                thumbnail_downloads_enabled
                and selection.status is ThumbnailSelectionStatus.SELECTED
                and selection.image
            ):
                cached_thumbnail = self._thumbnails.cache_thumbnail(
                    sha256=evidence.sha256,
                    image=selection.image,
                    selection_policy=selection.policy,
                )
                if cached_thumbnail is not None:
                    thumbnails_cached += 1
                    progress.emit_progress(
                        f"Model metadata: cached thumbnail {index}/{total} - {entry.source.relative_path}\r"
                    )
            else:
                no_sfw_thumbnail += 1
            record = ModelMetadataCacheRecord(
                schema_version=1,
                local=evidence,
                provider=result.version,
                provider_status=result.status.value,
                thumbnail=cached_thumbnail,
                thumbnail_status=selection.status,
                updated_at=self._clock(),
            )
            self._catalog.save_record(record)
            _emit_model_updated(
                progress,
                ModelMetadataRefreshEvent(
                    kind=entry.kind,
                    value=entry.value,
                    relative_path=entry.source.relative_path,
                    sha256=evidence.sha256,
                    provider_status=result.status.value,
                    thumbnail_updated=cached_thumbnail is not None,
                ),
            )
            enriched += 1
        return ModelMetadataRefreshSummary(
            enriched=enriched,
            thumbnails_cached=thumbnails_cached,
            not_found=not_found,
            skipped=skipped,
            no_sfw_thumbnail=no_sfw_thumbnail,
            failed=failed,
        )


def _utc_now() -> str:
    """Return the current UTC timestamp for cache records."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _emit_model_updated(
    progress: ModelMetadataProgressSink,
    event: ModelMetadataRefreshEvent,
) -> None:
    """Emit a structured update when the supplied progress sink supports it."""

    emit_model_updated = getattr(progress, "emit_model_updated", None)
    if callable(emit_model_updated):
        emit_model_updated(event)
