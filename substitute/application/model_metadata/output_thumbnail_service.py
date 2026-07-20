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

"""Assign final output canvas images as local model thumbnails."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import time
from uuid import UUID

from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
    ModelMetadataCatalogRepository,
    ModelMetadataRefreshEvent,
    ModelMetadataUpdateSink,
    ModelThumbnailRepository,
    RefreshCancellationToken,
)
from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.domain.model_metadata import (
    BackendFingerprintJob,
    BackendModelCatalogEntry,
    FingerprintStatus,
    JobStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
)
from substitute.domain.workflow import ImageMeta
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("application.model_metadata.output_thumbnail_service")
_LOCAL_THUMBNAIL_SOURCE = "output_canvas"
_LOCAL_PROVIDER_STATUS = "local-thumbnail"


class SetModelThumbnailFromOutputStatus(str, Enum):
    """Describe the outcome of assigning a local output image thumbnail."""

    UPDATED = "updated"
    MODEL_NOT_FOUND = "model-not-found"
    HASH_UNAVAILABLE = "hash-unavailable"
    IMAGE_NOT_FOUND = "image-not-found"
    IMAGE_UNDECODABLE = "image-undecodable"
    SAVE_FAILED = "save-failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SetModelThumbnailFromOutputRequest:
    """Request assigning a final output image as a model thumbnail."""

    kind: str
    value: str
    image_id: UUID


@dataclass(frozen=True, slots=True)
class SetModelThumbnailFromOutputResult:
    """Report the outcome of local output thumbnail assignment."""

    status: SetModelThumbnailFromOutputStatus
    kind: str
    value: str
    image_id: UUID
    relative_path: str | None = None
    sha256: str | None = None
    thumbnail_updated: bool = False
    message: str = ""


class SetModelThumbnailFromOutputService:
    """Own user-requested output-canvas thumbnail assignment for one model."""

    def __init__(
        self,
        *,
        backend: BackendModelMetadataGateway,
        catalog: ModelMetadataCatalogRepository,
        thumbnails: ModelThumbnailRepository,
        image_registry: CanvasImageRegistry,
        update_sink: ModelMetadataUpdateSink,
        clock: Callable[[], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        fingerprint_poll_interval_seconds: float = 0.5,
        fingerprint_poll_timeout_seconds: float = 120.0,
    ) -> None:
        """Store collaborators used to assign local thumbnails off the UI thread."""

        self._backend = backend
        self._catalog = catalog
        self._thumbnails = thumbnails
        self._image_registry = image_registry
        self._update_sink = update_sink
        self._clock = clock or _utc_now
        self._sleep = sleep
        self._fingerprint_poll_interval_seconds = fingerprint_poll_interval_seconds
        self._fingerprint_poll_timeout_seconds = fingerprint_poll_timeout_seconds

    def set_thumbnail(
        self,
        request: SetModelThumbnailFromOutputRequest,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> SetModelThumbnailFromOutputResult:
        """Assign one output image as the selected local model thumbnail."""

        cancellation = cancellation_token
        kind = request.kind.strip()
        value = request.value.strip()
        if not kind or not value:
            return _result(
                SetModelThumbnailFromOutputStatus.MODEL_NOT_FOUND,
                kind=kind,
                value=value,
                image_id=request.image_id,
                message=app_text(
                    "Thumbnail assignment requires a model kind and value."
                ),
            )
        log_info(
            _LOGGER,
            "Output canvas thumbnail assignment requested",
            kind=kind,
            value=value,
            image_id=str(request.image_id),
        )
        try:
            return self._set_thumbnail(
                kind=kind,
                value=value,
                image_id=request.image_id,
                cancellation=cancellation,
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Output canvas thumbnail assignment failed unexpectedly",
                kind=kind,
                value=value,
                image_id=str(request.image_id),
            )
            return _result(
                SetModelThumbnailFromOutputStatus.SAVE_FAILED,
                kind=kind,
                value=value,
                image_id=request.image_id,
                message=app_text(
                    "Thumbnail assignment failed; existing metadata was kept."
                ),
            )

    def _set_thumbnail(
        self,
        *,
        kind: str,
        value: str,
        image_id: UUID,
        cancellation: RefreshCancellationToken,
    ) -> SetModelThumbnailFromOutputResult:
        """Run the local thumbnail assignment workflow after normalization."""

        if cancellation.is_cancelled():
            return _result(
                SetModelThumbnailFromOutputStatus.CANCELLED,
                kind=kind,
                value=value,
                image_id=image_id,
            )
        entry = self._selected_backend_entry(kind=kind, value=value)
        if entry is None:
            return _result(
                SetModelThumbnailFromOutputStatus.MODEL_NOT_FOUND,
                kind=kind,
                value=value,
                image_id=image_id,
                message=app_text("The selected model is no longer present locally."),
            )
        sha256 = self._sha256_for_entry(entry, cancellation)
        if sha256 is None:
            return _result(
                SetModelThumbnailFromOutputStatus.HASH_UNAVAILABLE,
                kind=kind,
                value=value,
                image_id=image_id,
                relative_path=entry.source.relative_path,
                message=app_text("The selected model could not be fingerprinted."),
            )
        image_meta = self._image_registry.metadata_for(image_id)
        payload = self._image_registry.payload_for(image_id)
        if image_meta is None or (payload is None and not image_meta.path):
            return _result(
                SetModelThumbnailFromOutputStatus.IMAGE_NOT_FOUND,
                kind=kind,
                value=value,
                image_id=image_id,
                relative_path=entry.source.relative_path,
                sha256=sha256,
                message=app_text("The selected output image is no longer available."),
            )
        evidence = LocalModelEvidence.from_backend_entry(entry, sha256)
        previous_record = self._catalog.record_for_sha256(evidence.sha256)
        cached_thumbnail = self._cache_thumbnail(
            evidence=evidence,
            image=payload,
            image_meta=image_meta,
        )
        if cached_thumbnail is None:
            return _result(
                SetModelThumbnailFromOutputStatus.IMAGE_UNDECODABLE,
                kind=kind,
                value=value,
                image_id=image_id,
                relative_path=entry.source.relative_path,
                sha256=evidence.sha256,
                message=app_text("The selected output image could not be decoded."),
            )
        provider = previous_record.provider if previous_record is not None else None
        provider_status = (
            previous_record.provider_status
            if previous_record is not None
            else _LOCAL_PROVIDER_STATUS
        )
        record = ModelMetadataCacheRecord(
            schema_version=1,
            local=evidence,
            provider=provider,
            provider_status=provider_status,
            thumbnail=cached_thumbnail,
            thumbnail_status=ThumbnailSelectionStatus.SELECTED,
            updated_at=self._clock(),
        )
        self._catalog.save_record(record)
        event = ModelMetadataRefreshEvent(
            kind=entry.kind,
            value=entry.value,
            relative_path=entry.source.relative_path,
            sha256=evidence.sha256,
            provider_status=provider_status,
            metadata_updated=False,
            thumbnail_updated=True,
        )
        self._update_sink.emit_model_updated(event)
        log_info(
            _LOGGER,
            "Output canvas thumbnail assignment completed",
            kind=entry.kind,
            value=entry.value,
            sha256=evidence.sha256,
            image_id=str(image_id),
        )
        return _result(
            SetModelThumbnailFromOutputStatus.UPDATED,
            kind=entry.kind,
            value=entry.value,
            image_id=image_id,
            relative_path=entry.source.relative_path,
            sha256=evidence.sha256,
            thumbnail_updated=True,
            message=app_text("Thumbnail updated from output canvas."),
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
                "Output thumbnail fingerprint job failed to start",
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
                    "Output thumbnail fingerprint job timed out",
                    job_id=current_job.job_id,
                )
                return current_job
            self._sleep(self._fingerprint_poll_interval_seconds)
            polled_job = self._backend.get_fingerprint_job(current_job.job_id)
            if polled_job is None:
                log_debug(
                    _LOGGER,
                    "Output thumbnail fingerprint job became unavailable",
                    job_id=current_job.job_id,
                )
                return current_job
            current_job = polled_job
        return current_job

    def _cache_thumbnail(
        self,
        *,
        evidence: LocalModelEvidence,
        image: object | None,
        image_meta: ImageMeta,
    ) -> ThumbnailStoreResult | None:
        """Cache a detached output image as a model thumbnail."""

        try:
            return self._thumbnails.cache_local_thumbnail(
                sha256=evidence.sha256,
                image=image,
                source=_LOCAL_THUMBNAIL_SOURCE,
                source_label=_source_label_for(image_meta),
                source_path=image_meta.path or None,
                source_width=image_meta.width,
                source_height=image_meta.height,
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Failed to cache output canvas thumbnail",
                kind=evidence.kind,
                value=evidence.value,
                sha256=evidence.sha256,
            )
            return None


def _source_label_for(image_meta: ImageMeta) -> str:
    """Return a stable local source label for thumbnail source metadata."""

    if image_meta.path:
        return image_meta.path
    if image_meta.source_label:
        return image_meta.source_label
    if image_meta.cube_name:
        return image_meta.cube_name
    return _LOCAL_THUMBNAIL_SOURCE


def _ready_sha256(entry: BackendModelCatalogEntry) -> str | None:
    """Return ready SHA256 evidence from backend fingerprint or sidecar data."""

    if entry.fingerprint.status is FingerprintStatus.READY and entry.fingerprint.sha256:
        return entry.fingerprint.sha256.upper()
    if entry.sidecar.sha256:
        return entry.sidecar.sha256.upper()
    return None


def _result(
    status: SetModelThumbnailFromOutputStatus,
    *,
    kind: str,
    value: str,
    image_id: UUID,
    relative_path: str | None = None,
    sha256: str | None = None,
    thumbnail_updated: bool = False,
    message: str = "",
) -> SetModelThumbnailFromOutputResult:
    """Build one output thumbnail assignment result."""

    return SetModelThumbnailFromOutputResult(
        status=status,
        kind=kind,
        value=value,
        image_id=image_id,
        relative_path=relative_path,
        sha256=sha256,
        thumbnail_updated=thumbnail_updated,
        message=message,
    )


def _utc_now() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "SetModelThumbnailFromOutputRequest",
    "SetModelThumbnailFromOutputResult",
    "SetModelThumbnailFromOutputService",
    "SetModelThumbnailFromOutputStatus",
]
