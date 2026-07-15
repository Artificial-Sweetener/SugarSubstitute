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

"""Force-refresh CivitAI metadata for one user-selected local model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import time

from substitute.application.civitai import CivitaiPreferenceService
from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
    CivitaiMetadataGateway,
    ModelMetadataCatalogRepository,
    ModelMetadataRefreshEvent,
    ModelMetadataUpdateSink,
    ModelThumbnailRepository,
    RefreshCancellationToken,
)
from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.domain.model_metadata import (
    BackendFingerprintJob,
    BackendModelCatalogEntry,
    CivitaiLookupStatus,
    FingerprintStatus,
    JobStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
)
from substitute.domain.model_metadata.thumbnail_policy import (
    CivitaiThumbnailPolicy,
    FirstSfwThumbnailPolicy,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("application.model_metadata.manual_refresh_service")


class ManualModelMetadataRefreshStatus(str, Enum):
    """Describe the outcome of one user-requested metadata refresh."""

    UPDATED = "updated"
    UPDATED_METADATA_PRESERVED_THUMBNAIL = "updated-metadata-preserved-thumbnail"
    NOT_FOUND_PRESERVED = "not-found-preserved"
    UNAVAILABLE_PRESERVED = "unavailable-preserved"
    INVALID_RESPONSE_PRESERVED = "invalid-response-preserved"
    MODEL_NOT_FOUND_LOCALLY = "model-not-found-locally"
    FINGERPRINT_UNAVAILABLE = "fingerprint-unavailable"
    LOOKUP_DISABLED = "lookup-disabled"
    CANCELLED = "cancelled"
    FAILED_PRESERVED = "failed-preserved"


@dataclass(frozen=True, slots=True)
class ManualModelMetadataRefreshRequest:
    """Identify one local model selected for user-requested metadata refresh."""

    kind: str
    value: str


@dataclass(frozen=True, slots=True)
class ManualModelMetadataRefreshResult:
    """Return the committed or preserved outcome of a manual refresh."""

    status: ManualModelMetadataRefreshStatus
    kind: str
    value: str
    relative_path: str | None = None
    sha256: str | None = None
    provider_status: str | None = None
    thumbnail_updated: bool = False
    message: str = ""


class ManualModelMetadataRefreshService:
    """Own non-destructive user-requested CivitAI metadata refreshes."""

    def __init__(
        self,
        *,
        backend: BackendModelMetadataGateway,
        civitai: CivitaiMetadataGateway,
        catalog: ModelMetadataCatalogRepository,
        thumbnails: ModelThumbnailRepository,
        update_sink: ModelMetadataUpdateSink,
        thumbnail_policy: CivitaiThumbnailPolicy | None = None,
        civitai_preferences: CivitaiPreferenceService | None = None,
        clock: Callable[[], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        fingerprint_poll_interval_seconds: float = 0.5,
        fingerprint_poll_timeout_seconds: float = 120.0,
    ) -> None:
        """Store collaborators used to refresh one selected model off the UI thread."""

        self._backend = backend
        self._civitai = civitai
        self._catalog = catalog
        self._thumbnails = thumbnails
        self._update_sink = update_sink
        self._thumbnail_policy = thumbnail_policy or FirstSfwThumbnailPolicy()
        self._civitai_preferences = civitai_preferences
        self._clock = clock or _utc_now
        self._sleep = sleep
        self._fingerprint_poll_interval_seconds = fingerprint_poll_interval_seconds
        self._fingerprint_poll_timeout_seconds = fingerprint_poll_timeout_seconds

    def refresh_model(
        self,
        request: ManualModelMetadataRefreshRequest,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> ManualModelMetadataRefreshResult:
        """Force-refresh CivitAI metadata for one user-selected local model."""

        cancellation = cancellation_token
        kind = request.kind.strip()
        value = request.value.strip()
        if not kind or not value:
            return _result(
                ManualModelMetadataRefreshStatus.MODEL_NOT_FOUND_LOCALLY,
                kind=kind,
                value=value,
                message="Manual metadata refresh requires a model kind and value.",
            )
        log_info(
            _LOGGER,
            "Manual CivitAI metadata refresh requested",
            kind=kind,
            value=value,
        )
        try:
            return self._refresh_model(
                kind=kind,
                value=value,
                cancellation=cancellation,
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Manual CivitAI metadata refresh failed unexpectedly",
                kind=kind,
                value=value,
            )
            return _result(
                ManualModelMetadataRefreshStatus.FAILED_PRESERVED,
                kind=kind,
                value=value,
                message="CivitAI metadata refresh failed; existing metadata was kept.",
            )

    def _refresh_model(
        self,
        *,
        kind: str,
        value: str,
        cancellation: RefreshCancellationToken,
    ) -> ManualModelMetadataRefreshResult:
        """Run the non-destructive refresh workflow after request normalization."""

        if cancellation.is_cancelled():
            return _result(
                ManualModelMetadataRefreshStatus.CANCELLED, kind=kind, value=value
            )
        entry = self._selected_backend_entry(kind=kind, value=value)
        if entry is None:
            return _result(
                ManualModelMetadataRefreshStatus.MODEL_NOT_FOUND_LOCALLY,
                kind=kind,
                value=value,
                message="The selected model is no longer present locally.",
            )
        sha256 = self._sha256_for_entry(entry, cancellation)
        if sha256 is None:
            return _result(
                ManualModelMetadataRefreshStatus.FINGERPRINT_UNAVAILABLE,
                kind=kind,
                value=value,
                relative_path=entry.source.relative_path,
                message="The selected model could not be fingerprinted.",
            )
        if cancellation.is_cancelled():
            return _result(
                ManualModelMetadataRefreshStatus.CANCELLED,
                kind=kind,
                value=value,
                relative_path=entry.source.relative_path,
                sha256=sha256,
            )
        preferences = (
            self._civitai_preferences.load_preferences()
            if self._civitai_preferences is not None
            else None
        )
        if preferences is not None and not preferences.metadata_lookup_enabled:
            return _result(
                ManualModelMetadataRefreshStatus.LOOKUP_DISABLED,
                kind=kind,
                value=value,
                relative_path=entry.source.relative_path,
                sha256=sha256,
                message="CivitAI metadata lookup is disabled in Settings.",
            )
        try:
            lookup = self._civitai.lookup_model_version_by_hash(sha256)
        except Exception:
            log_exception(
                _LOGGER,
                "Manual CivitAI lookup failed unexpectedly",
                kind=kind,
                value=value,
                sha256=sha256,
            )
            return _result(
                ManualModelMetadataRefreshStatus.FAILED_PRESERVED,
                kind=kind,
                value=value,
                relative_path=entry.source.relative_path,
                sha256=sha256,
                message="CivitAI lookup failed; existing metadata was kept.",
            )
        if lookup.status is CivitaiLookupStatus.NOT_FOUND:
            return _preserved_lookup_result(
                ManualModelMetadataRefreshStatus.NOT_FOUND_PRESERVED,
                entry=entry,
                sha256=sha256,
                provider_status=lookup.status.value,
                message="CivitAI did not return a match; existing metadata was kept.",
            )
        if lookup.status is CivitaiLookupStatus.UNAVAILABLE:
            return _preserved_lookup_result(
                ManualModelMetadataRefreshStatus.UNAVAILABLE_PRESERVED,
                entry=entry,
                sha256=sha256,
                provider_status=lookup.status.value,
                message="CivitAI is unavailable; existing metadata was kept.",
            )
        if lookup.status is not CivitaiLookupStatus.FOUND or lookup.version is None:
            return _preserved_lookup_result(
                ManualModelMetadataRefreshStatus.INVALID_RESPONSE_PRESERVED,
                entry=entry,
                sha256=sha256,
                provider_status=lookup.status.value,
                message="CivitAI returned unusable metadata; existing metadata was kept.",
            )

        evidence = LocalModelEvidence.from_backend_entry(entry, sha256)
        thumbnail_downloads_enabled = True
        active_thumbnail_policy = self._thumbnail_policy
        if preferences is not None:
            thumbnail_downloads_enabled = preferences.thumbnail_downloads_enabled
            active_thumbnail_policy = CivitaiThumbnailPolicy(
                preferences.thumbnail_safety_policy
                if thumbnail_downloads_enabled
                else CivitaiThumbnailSafetyPolicy.DISABLED
            )
        previous_record = self._catalog.record_for_sha256(evidence.sha256)
        selection = active_thumbnail_policy.select(lookup.version)
        cached_thumbnail: ThumbnailStoreResult | None = None
        if (
            thumbnail_downloads_enabled
            and selection.status is ThumbnailSelectionStatus.SELECTED
            and selection.image is not None
        ):
            try:
                cached_thumbnail = self._thumbnails.cache_thumbnail(
                    sha256=evidence.sha256,
                    image=selection.image,
                    selection_policy=selection.policy,
                )
            except Exception:
                log_exception(
                    _LOGGER,
                    "Manual CivitAI thumbnail refresh failed unexpectedly",
                    kind=entry.kind,
                    value=entry.value,
                    sha256=evidence.sha256,
                )
                cached_thumbnail = None
        preserved_thumbnail = (
            previous_record.thumbnail
            if cached_thumbnail is None and previous_record is not None
            else None
        )
        thumbnail = cached_thumbnail or preserved_thumbnail
        thumbnail_status = (
            ThumbnailSelectionStatus.SELECTED
            if thumbnail is not None
            else selection.status
        )
        record = ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence,
            provider=lookup.version,
            provider_status=lookup.status.value,
            thumbnail=thumbnail,
            thumbnail_status=thumbnail_status,
            updated_at=self._clock(),
        )
        self._catalog.save_record(record)
        thumbnail_updated = cached_thumbnail is not None
        self._update_sink.emit_model_updated(
            ModelMetadataRefreshEvent(
                kind=entry.kind,
                value=entry.value,
                relative_path=entry.source.relative_path,
                sha256=evidence.sha256,
                provider_status=lookup.status.value,
                metadata_updated=True,
                thumbnail_updated=thumbnail_updated,
            )
        )
        status = (
            ManualModelMetadataRefreshStatus.UPDATED
            if thumbnail_updated or preserved_thumbnail is None
            else ManualModelMetadataRefreshStatus.UPDATED_METADATA_PRESERVED_THUMBNAIL
        )
        log_info(
            _LOGGER,
            "Manual CivitAI metadata refresh completed",
            kind=entry.kind,
            value=entry.value,
            sha256=evidence.sha256,
            status=status.value,
            thumbnail_updated=thumbnail_updated,
        )
        return _result(
            status,
            kind=entry.kind,
            value=entry.value,
            relative_path=entry.source.relative_path,
            sha256=evidence.sha256,
            provider_status=lookup.status.value,
            thumbnail_updated=thumbnail_updated,
            message="CivitAI metadata refreshed.",
        )

    def _selected_backend_entry(
        self,
        *,
        kind: str,
        value: str,
    ) -> BackendModelCatalogEntry | None:
        """Return the live backend entry matching the selected model identity."""

        for entry in self._backend.list_models((kind,), refresh=True):
            if entry.kind == kind and entry.value == value:
                return entry
        return None

    def _sha256_for_entry(
        self,
        entry: BackendModelCatalogEntry,
        cancellation: RefreshCancellationToken,
    ) -> str | None:
        """Return ready SHA256 evidence, requesting fingerprinting when needed."""

        ready = _ready_sha256(entry)
        if ready is not None:
            return ready
        job = self._backend.refresh_fingerprints((entry,))
        if job.status is JobStatus.FAILED:
            log_warning(
                _LOGGER,
                "Manual metadata fingerprint job failed to start",
                kind=entry.kind,
                value=entry.value,
            )
            return None
        completed = self._poll_fingerprint_job(job, cancellation)
        for job_entry in completed.entries:
            if (
                job_entry.kind == entry.kind
                and job_entry.value == entry.value
                and job_entry.status is JobStatus.COMPLETE
                and job_entry.sha256
            ):
                return job_entry.sha256.upper()
        return None

    def _poll_fingerprint_job(
        self,
        job: BackendFingerprintJob,
        cancellation: RefreshCancellationToken,
    ) -> BackendFingerprintJob:
        """Poll one backend fingerprint job until it settles or times out."""

        deadline = time.monotonic() + self._fingerprint_poll_timeout_seconds
        current_job = job
        while current_job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            if cancellation.is_cancelled():
                return current_job
            if time.monotonic() >= deadline:
                log_warning(
                    _LOGGER,
                    "Manual metadata fingerprint job timed out",
                    job_id=current_job.job_id,
                )
                return current_job
            self._sleep(self._fingerprint_poll_interval_seconds)
            polled_job = self._backend.get_fingerprint_job(current_job.job_id)
            if polled_job is None:
                log_debug(
                    _LOGGER,
                    "Manual metadata fingerprint job became unavailable",
                    job_id=current_job.job_id,
                )
                return current_job
            current_job = polled_job
        return current_job


def _ready_sha256(entry: BackendModelCatalogEntry) -> str | None:
    """Return ready SHA256 evidence from backend fingerprint or sidecar data."""

    if entry.fingerprint.status is FingerprintStatus.READY and entry.fingerprint.sha256:
        return entry.fingerprint.sha256.upper()
    if entry.sidecar.sha256:
        return entry.sidecar.sha256.upper()
    return None


def _preserved_lookup_result(
    status: ManualModelMetadataRefreshStatus,
    *,
    entry: BackendModelCatalogEntry,
    sha256: str,
    provider_status: str,
    message: str,
) -> ManualModelMetadataRefreshResult:
    """Return a non-destructive result for a failed provider lookup."""

    log_info(
        _LOGGER,
        "Manual CivitAI metadata refresh preserved existing cache",
        kind=entry.kind,
        value=entry.value,
        sha256=sha256,
        status=status.value,
        provider_status=provider_status,
    )
    return _result(
        status,
        kind=entry.kind,
        value=entry.value,
        relative_path=entry.source.relative_path,
        sha256=sha256,
        provider_status=provider_status,
        message=message,
    )


def _result(
    status: ManualModelMetadataRefreshStatus,
    *,
    kind: str,
    value: str,
    relative_path: str | None = None,
    sha256: str | None = None,
    provider_status: str | None = None,
    thumbnail_updated: bool = False,
    message: str = "",
) -> ManualModelMetadataRefreshResult:
    """Build one manual refresh result."""

    return ManualModelMetadataRefreshResult(
        status=status,
        kind=kind,
        value=value,
        relative_path=relative_path,
        sha256=sha256,
        provider_status=provider_status,
        thumbnail_updated=thumbnail_updated,
        message=message,
    )


def _utc_now() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "ManualModelMetadataRefreshRequest",
    "ManualModelMetadataRefreshResult",
    "ManualModelMetadataRefreshService",
    "ManualModelMetadataRefreshStatus",
]
