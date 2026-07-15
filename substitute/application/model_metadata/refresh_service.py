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

"""Coordinate startup model metadata enrichment and cache updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import time

from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
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
    BackendCapabilities,
    BackendFingerprintJob,
    BackendModelCatalogEntry,
    CivitaiLookupStatus,
    FingerprintStatus,
    JobStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
)
from substitute.domain.model_metadata.thumbnail_policy import (
    CivitaiThumbnailPolicy,
    FirstSfwThumbnailPolicy,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_warning

_LOGGER = get_logger("application.model_metadata.refresh_service")
DEFAULT_MODEL_KINDS = (
    "checkpoints",
    "loras",
    "vae",
    "embeddings",
    "controlnet",
    "hypernetworks",
    "upscale_models",
    "diffusion_models",
)


@dataclass(frozen=True)
class ModelMetadataRefreshSummary:
    """Summarize the effects of one metadata refresh run."""

    discovered: int = 0
    fingerprint_requested: int = 0
    enriched: int = 0
    thumbnails_cached: int = 0
    not_found: int = 0
    skipped: int = 0
    no_sfw_thumbnail: int = 0
    failed: int = 0
    cancelled: bool = False


class ModelMetadataRefreshService:
    """Refresh CivitAI metadata for Comfy-visible models."""

    def __init__(
        self,
        *,
        backend: BackendModelMetadataGateway,
        civitai: CivitaiMetadataGateway,
        catalog: ModelMetadataCatalogRepository,
        thumbnails: ModelThumbnailRepository,
        thumbnail_policy: CivitaiThumbnailPolicy | None = None,
        civitai_preferences: CivitaiPreferenceService | None = None,
        clock: Callable[[], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        model_kinds: tuple[str, ...] = DEFAULT_MODEL_KINDS,
        capability_wait_timeout_seconds: float = 20.0,
        capability_retry_interval_seconds: float = 0.5,
        fingerprint_poll_interval_seconds: float = 0.5,
        fingerprint_poll_timeout_seconds: float = 120.0,
    ) -> None:
        """Initialize the refresh service with its application ports."""

        self._backend = backend
        self._civitai = civitai
        self._catalog = catalog
        self._thumbnails = thumbnails
        self._thumbnail_policy = thumbnail_policy or FirstSfwThumbnailPolicy()
        self._civitai_preferences = civitai_preferences
        self._clock = clock or _utc_now
        self._sleep = sleep
        self._model_kinds = model_kinds
        self._capability_wait_timeout_seconds = capability_wait_timeout_seconds
        self._capability_retry_interval_seconds = capability_retry_interval_seconds
        self._fingerprint_poll_interval_seconds = fingerprint_poll_interval_seconds
        self._fingerprint_poll_timeout_seconds = fingerprint_poll_timeout_seconds

    def refresh(
        self,
        progress: ModelMetadataProgressSink,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> ModelMetadataRefreshSummary:
        """Run one metadata refresh and report user-visible progress."""

        cancellation = cancellation_token
        progress.emit_line("Model metadata: checking backend capabilities.")
        capabilities = self._wait_for_capabilities(progress, cancellation)
        if capabilities is None or not capabilities.background_hashing:
            progress.emit_line(
                "Model metadata: Substitute BackEnd model API unavailable; skipping startup metadata refresh."
            )
            return ModelMetadataRefreshSummary()

        supported_kinds = tuple(
            kind
            for kind in self._model_kinds
            if kind in capabilities.supported_model_kinds
        )
        if not supported_kinds:
            progress.emit_line(
                "Model metadata: backend reports no supported model kinds."
            )
            return ModelMetadataRefreshSummary()

        models = self._backend.list_models(supported_kinds)
        progress.emit_line(
            f"Model metadata: found {len(models)} Comfy models across {len(supported_kinds)} kinds."
        )
        if cancellation.is_cancelled():
            progress.emit_line("Model metadata: refresh canceled during shutdown.")
            return ModelMetadataRefreshSummary(discovered=len(models), cancelled=True)

        refreshed_hashes = self._refresh_missing_fingerprints(
            models,
            progress,
            cancellation,
        )
        summary = self._enrich_entries(
            models=models,
            refreshed_hashes=refreshed_hashes,
            progress=progress,
            cancellation=cancellation,
        )
        complete_summary = ModelMetadataRefreshSummary(
            discovered=len(models),
            fingerprint_requested=len(refreshed_hashes),
            enriched=summary.enriched,
            thumbnails_cached=summary.thumbnails_cached,
            not_found=summary.not_found,
            skipped=summary.skipped,
            no_sfw_thumbnail=summary.no_sfw_thumbnail,
            failed=summary.failed,
            cancelled=summary.cancelled,
        )
        if complete_summary.cancelled:
            progress.emit_line("Model metadata: refresh canceled during shutdown.")
            return complete_summary
        progress.emit_line(
            "Model metadata: complete. "
            f"{complete_summary.enriched} metadata records updated, "
            f"{complete_summary.thumbnails_cached} thumbnails cached, "
            f"{complete_summary.not_found} not found, "
            f"{complete_summary.skipped} skipped."
        )
        return complete_summary

    def refresh_entries(
        self,
        models: tuple[BackendModelCatalogEntry, ...],
        progress: ModelMetadataProgressSink,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> ModelMetadataRefreshSummary:
        """Refresh CivitAI metadata for a scoped set of backend catalog entries."""

        cancellation = cancellation_token
        if not models:
            return ModelMetadataRefreshSummary()
        refreshed_hashes = self._refresh_missing_fingerprints(
            models,
            progress,
            cancellation,
        )
        summary = self._enrich_entries(
            models=models,
            refreshed_hashes=refreshed_hashes,
            progress=progress,
            cancellation=cancellation,
        )
        return ModelMetadataRefreshSummary(
            discovered=len(models),
            fingerprint_requested=len(refreshed_hashes),
            enriched=summary.enriched,
            thumbnails_cached=summary.thumbnails_cached,
            not_found=summary.not_found,
            skipped=summary.skipped,
            no_sfw_thumbnail=summary.no_sfw_thumbnail,
            failed=summary.failed,
            cancelled=summary.cancelled,
        )

    def _wait_for_capabilities(
        self,
        progress: ModelMetadataProgressSink,
        cancellation: RefreshCancellationToken,
    ) -> BackendCapabilities | None:
        """Poll backend capabilities after Comfy starts accepting connections."""

        deadline = time.monotonic() + self._capability_wait_timeout_seconds
        first_retry = True
        while not cancellation.is_cancelled():
            capabilities = self._backend.get_capabilities()
            if capabilities is not None:
                return capabilities
            if time.monotonic() >= deadline:
                return None
            if first_retry:
                progress.emit_line(
                    "Model metadata: waiting for Substitute BackEnd model API."
                )
                first_retry = False
            else:
                progress.emit_progress(
                    "Model metadata: waiting for Substitute BackEnd model API\r"
                )
            self._sleep(self._capability_retry_interval_seconds)
        return None

    def _refresh_missing_fingerprints(
        self,
        models: tuple[BackendModelCatalogEntry, ...],
        progress: ModelMetadataProgressSink,
        cancellation: RefreshCancellationToken,
    ) -> dict[tuple[str, str], str]:
        """Ask the backend to hash models without SHA256 evidence."""

        missing = tuple(entry for entry in models if _ready_sha256(entry) is None)
        if not missing:
            return {}
        progress.emit_line(
            f"Model metadata: {len(missing)} models need SHA256 fingerprints."
        )
        job = self._backend.refresh_fingerprints(missing)
        if job.status is JobStatus.FAILED:
            progress.emit_line("Model metadata: fingerprint job failed to start.")
            return {}
        progress.emit_line(
            f"Model metadata: fingerprint job queued for {len(missing)} models."
        )
        completed_job = self._poll_fingerprint_job(job, progress, cancellation)
        return {
            (entry.kind, entry.value): entry.sha256.upper()
            for entry in completed_job.entries
            if entry.sha256 and entry.status is JobStatus.COMPLETE
        }

    def _poll_fingerprint_job(
        self,
        job: BackendFingerprintJob,
        progress: ModelMetadataProgressSink,
        cancellation: RefreshCancellationToken,
    ) -> BackendFingerprintJob:
        """Poll one backend fingerprint job until it settles or times out."""

        deadline = time.monotonic() + self._fingerprint_poll_timeout_seconds
        current_job = job
        while current_job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            if cancellation.is_cancelled():
                return current_job
            completed = sum(
                1 for entry in current_job.entries if entry.status is JobStatus.COMPLETE
            )
            total = len(current_job.entries)
            progress.emit_progress(
                f"Model metadata: fingerprinting {completed}/{total} models\r"
            )
            if time.monotonic() >= deadline:
                progress.emit_line("Model metadata: fingerprint job timed out.")
                return current_job
            self._sleep(self._fingerprint_poll_interval_seconds)
            polled_job = self._backend.get_fingerprint_job(current_job.job_id)
            if polled_job is None:
                progress.emit_line(
                    "Model metadata: fingerprint job became unavailable."
                )
                return current_job
            current_job = polled_job
        progress.emit_line("Model metadata: fingerprinting complete.")
        return current_job

    def _enrich_entries(
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
                _ready_sha256(entry) or refreshed_hashes.get((entry.kind, entry.value)),
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


def _ready_sha256(entry: BackendModelCatalogEntry) -> str | None:
    """Return ready SHA256 evidence from backend fingerprint or sidecar data."""

    if entry.fingerprint.status is FingerprintStatus.READY and entry.fingerprint.sha256:
        return entry.fingerprint.sha256.upper()
    if entry.sidecar.sha256:
        return entry.sidecar.sha256.upper()
    return None


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


__all__ = [
    "DEFAULT_MODEL_KINDS",
    "ModelMetadataRefreshService",
    "ModelMetadataRefreshSummary",
]
