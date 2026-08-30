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

"""Tests for assigning output canvas images as model thumbnails."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from PySide6.QtGui import QColor, QImage

from substitute.application.model_metadata import (
    SetModelThumbnailFromOutputRequest,
    SetModelThumbnailFromOutputService,
    SetModelThumbnailFromOutputStatus,
)
from substitute.application.model_metadata.ports import ModelMetadataRefreshEvent
from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.domain.model_metadata import (
    BackendFingerprint,
    BackendFingerprintJob,
    BackendLocalPreview,
    BackendModelCatalogEntry,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    CivitaiImage,
    CivitaiModelVersion,
    FingerprintStatus,
    JobStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailAsset,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
    ThumbnailVariant,
)
from substitute.domain.workflow import ImageMeta


class _Backend:
    """Return configured backend model entries."""

    def __init__(self, entries: tuple[BackendModelCatalogEntry, ...]) -> None:
        """Store fake model catalog entries."""

        self.entries = entries

    def get_capabilities(self) -> None:
        """Return no capabilities because this service does not inspect them."""

        return None

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return matching entries and ignore refresh semantics."""

        _ = refresh
        return tuple(entry for entry in self.entries if entry.kind in kinds)

    def refresh_fingerprints(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
    ) -> BackendFingerprintJob:
        """Return a failed job because tests use ready hashes."""

        _ = entries
        return BackendFingerprintJob(job_id="job", status=JobStatus.FAILED, entries=())

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return no later job state."""

        _ = job_id
        return None


class _Catalog:
    """Store metadata records in memory."""

    def __init__(self, existing_record: ModelMetadataCacheRecord | None = None) -> None:
        """Store one optional existing record."""

        self.existing_record = existing_record
        self.records: list[ModelMetadataCacheRecord] = []

    def is_fresh(self, evidence: LocalModelEvidence) -> bool:
        """Return false because this service does not freshness-check."""

        _ = evidence
        return False

    def record_for_sha256(self, sha256: str) -> ModelMetadataCacheRecord | None:
        """Return the configured existing record for preservation tests."""

        _ = sha256
        return self.existing_record

    def save_record(self, record: ModelMetadataCacheRecord) -> None:
        """Record one saved cache record."""

        self.records.append(record)

    def save_not_found(self, evidence: LocalModelEvidence, *, fetched_at: str) -> None:
        """Ignore not-found writes because they are not used here."""

        _ = (evidence, fetched_at)


class _Thumbnails:
    """Record local thumbnail cache requests."""

    def __init__(self, result: ThumbnailStoreResult | None) -> None:
        """Store the configured cache result."""

        self.result = result
        self.local_calls: list[tuple[str, object | None, str, str, str | None]] = []

    def cache_thumbnail(
        self,
        *,
        sha256: str,
        image: CivitaiImage,
        selection_policy: str,
    ) -> ThumbnailStoreResult | None:
        """Reject provider thumbnail calls in local-output tests."""

        _ = (sha256, image, selection_policy)
        raise AssertionError("CivitAI thumbnail cache should not be used")

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
        """Record local thumbnail cache requests and return configured result."""

        _ = (source_width, source_height)
        self.local_calls.append((sha256, image, source, source_label, source_path))
        return self.result


@dataclass
class _UpdateSink:
    """Collect emitted update events."""

    events: list[ModelMetadataRefreshEvent]

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Record one emitted metadata update event."""

        self.events.append(event)


class _NotCancelled:
    """Provide explicit uncancelled refresh state for direct service tests."""

    def is_cancelled(self) -> bool:
        """Return false because these tests do not request cancellation."""

        return False


def test_output_thumbnail_service_saves_local_thumbnail_preserving_provider() -> None:
    """Successful assignment should replace thumbnail while preserving metadata."""

    image_id = uuid4()
    registry = _registry_with_image(image_id)
    entry = _entry(sha256="ABC123")
    existing = _record("ABC123", provider_status="found")
    thumbnail = _thumbnail("ABC123")
    catalog = _Catalog(existing)
    thumbnails = _Thumbnails(thumbnail)
    sink = _UpdateSink([])
    service = SetModelThumbnailFromOutputService(
        backend=_Backend((entry,)),
        catalog=catalog,
        thumbnails=thumbnails,
        image_registry=registry,
        update_sink=sink,
        clock=lambda: "2026-07-03T12:00:00Z",
    )

    result = service.set_thumbnail(
        SetModelThumbnailFromOutputRequest(
            kind="loras",
            value="Folder/Midna.safetensors",
            image_id=image_id,
        ),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is SetModelThumbnailFromOutputStatus.UPDATED
    assert result.thumbnail_updated is True
    assert len(catalog.records) == 1
    saved = catalog.records[0]
    assert saved.provider is existing.provider
    assert saved.provider_status == "found"
    assert saved.thumbnail is thumbnail
    assert saved.thumbnail_status is ThumbnailSelectionStatus.SELECTED
    assert thumbnails.local_calls[0][0] == "ABC123"
    assert thumbnails.local_calls[0][2] == "output_canvas"
    assert sink.events == [
        ModelMetadataRefreshEvent(
            kind="loras",
            value="Folder/Midna.safetensors",
            relative_path="Folder/Midna.safetensors",
            sha256="ABC123",
            provider_status="found",
            metadata_updated=False,
            thumbnail_updated=True,
        )
    ]


def test_output_thumbnail_service_does_not_save_when_image_missing() -> None:
    """Missing selected output images should leave metadata untouched."""

    image_id = uuid4()
    catalog = _Catalog()
    service = SetModelThumbnailFromOutputService(
        backend=_Backend((_entry(sha256="ABC123"),)),
        catalog=catalog,
        thumbnails=_Thumbnails(_thumbnail("ABC123")),
        image_registry=CanvasImageRegistry(),
        update_sink=_UpdateSink([]),
    )

    result = service.set_thumbnail(
        SetModelThumbnailFromOutputRequest(
            kind="loras",
            value="Folder/Midna.safetensors",
            image_id=image_id,
        ),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is SetModelThumbnailFromOutputStatus.IMAGE_NOT_FOUND
    assert catalog.records == []


def test_output_thumbnail_service_does_not_save_without_model_hash() -> None:
    """Models without hash evidence should not receive local thumbnails."""

    image_id = uuid4()
    catalog = _Catalog()
    service = SetModelThumbnailFromOutputService(
        backend=_Backend((_entry(sha256=None),)),
        catalog=catalog,
        thumbnails=_Thumbnails(_thumbnail("ABC123")),
        image_registry=_registry_with_image(image_id),
        update_sink=_UpdateSink([]),
    )

    result = service.set_thumbnail(
        SetModelThumbnailFromOutputRequest(
            kind="loras",
            value="Folder/Midna.safetensors",
            image_id=image_id,
        ),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is SetModelThumbnailFromOutputStatus.HASH_UNAVAILABLE
    assert catalog.records == []


def _registry_with_image(image_id: UUID) -> CanvasImageRegistry:
    """Return an image registry containing one output QImage."""

    image = QImage(32, 24, QImage.Format.Format_ARGB32)
    image.fill(QColor("#336699"))
    registry = CanvasImageRegistry()
    registry.store(
        image_id,
        payload=image,
        metadata=ImageMeta(
            workflow_name="Workflow",
            cube_name="Cube",
            image_number=1,
            suffix=".png",
            path="C:/outputs/image.png",
            source_key="main",
            source_label="Main output",
            width=32,
            height=24,
            list_index=0,
        ),
    )
    return registry


def _entry(sha256: str | None) -> BackendModelCatalogEntry:
    """Return one backend model catalog entry."""

    return BackendModelCatalogEntry(
        schema_version=1,
        target_id="target",
        kind="loras",
        value="Folder/Midna.safetensors",
        display_name="Midna",
        source=BackendModelSource(
            root_id="root",
            relative_path="Folder/Midna.safetensors",
        ),
        file=BackendModelFile(
            extension=".safetensors",
            size_bytes=123,
            modified_at="2026-07-03T10:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=FingerprintStatus.READY if sha256 else FingerprintStatus.MISSING,
            sha256=sha256,
            source="cache" if sha256 else None,
            computed_at="2026-07-03T10:00:00Z" if sha256 else None,
            error=None,
        ),
        sidecar=BackendSidecar(
            found=False,
            model_id=None,
            model_version_id=None,
            sha256=None,
            activation_text=None,
            description=None,
            base_model=None,
            modified_at=None,
        ),
        local_preview=BackendLocalPreview(
            available=False,
            preview_id=None,
            url=None,
            source=None,
            modified_at=None,
            width=None,
            height=None,
        ),
    )


def _record(sha256: str, *, provider_status: str) -> ModelMetadataCacheRecord:
    """Return one existing metadata record with provider data."""

    evidence = LocalModelEvidence.from_backend_entry(_entry(sha256), sha256)
    return ModelMetadataCacheRecord(
        schema_version=1,
        local=evidence,
        provider=_version(),
        provider_status=provider_status,
        thumbnail=None,
        thumbnail_status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
        updated_at="2026-07-03T10:00:00Z",
    )


def _version() -> CivitaiModelVersion:
    """Return minimal provider metadata for preservation assertions."""

    return CivitaiModelVersion(
        model_id=100,
        model_version_id=200,
        model_name="Midna",
        model_type="LORA",
        version_name="v1",
        base_model=None,
        trained_words=(),
        description=None,
        version_description=None,
        tags=(),
        creator_username=None,
        creator_image=None,
        nsfw=False,
        nsfw_level="None",
        availability=None,
        files=(),
        images=(),
        stats={},
        model_page_url="https://civitai.com/models/100?modelVersionId=200",
        source_url="https://civitai.com/api/v1/model-versions/by-hash/ABC123",
        fetched_at="2026-07-03T10:00:00Z",
        raw_provider_payload={},
    )


def _thumbnail(sha256: str) -> ThumbnailStoreResult:
    """Return one cached local thumbnail result."""

    variant = ThumbnailVariant(
        size=128,
        storage_key=f"{sha256}:standard:128",
        width=128,
        height=96,
        content_format="raw",
        byte_size=4,
    )
    asset = ThumbnailAsset(
        storage_key=variant.storage_key,
        width=128,
        height=96,
        qt_format=QImage.Format.Format_ARGB32.value,
        bytes_per_line=512,
        content_format="raw",
        payload=b"data",
    )
    return ThumbnailStoreResult(
        source="output_canvas",
        selection_policy="user_selected_output_canvas",
        source_image_url="C:/outputs/image.png",
        source_image_id=None,
        nsfw=None,
        nsfw_level=None,
        source_width=32,
        source_height=24,
        variants=(variant,),
        downloaded_at="2026-07-03T12:00:00Z",
        assets=(asset,),
    )
