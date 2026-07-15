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

"""Tests for user-requested model metadata refresh behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from substitute.application.civitai import CivitaiPreferenceService
from substitute.application.model_metadata import (
    ManualModelMetadataRefreshRequest,
    ManualModelMetadataRefreshService,
    ManualModelMetadataRefreshStatus,
    ModelMetadataRefreshEvent,
)
from substitute.domain.civitai import default_civitai_preferences
from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendFingerprint,
    BackendFingerprintJob,
    BackendFingerprintJobEntry,
    BackendLocalPreview,
    BackendModelCatalogEntry,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    CivitaiImage,
    CivitaiLookupResult,
    CivitaiLookupStatus,
    CivitaiModelVersion,
    FingerprintStatus,
    JobStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
    ThumbnailVariant,
)


class _FakeBackend:
    """Provide deterministic local model catalog and fingerprint behavior."""

    def __init__(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
        *,
        fingerprint_sha256: str | None = "FINGERPRINTED",
    ) -> None:
        self.entries = entries
        self.fingerprint_sha256 = fingerprint_sha256
        self.list_refresh_values: list[bool] = []
        self.fingerprint_requests: list[BackendModelCatalogEntry] = []

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return no capabilities because manual refresh does not use them."""

        return None

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return entries matching requested kinds."""

        self.list_refresh_values.append(refresh)
        return tuple(entry for entry in self.entries if entry.kind in kinds)

    def refresh_fingerprints(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
    ) -> BackendFingerprintJob:
        """Return a completed fingerprint job for requested entries."""

        self.fingerprint_requests.extend(entries)
        return BackendFingerprintJob(
            job_id="manual-job",
            status=JobStatus.COMPLETE,
            entries=tuple(
                BackendFingerprintJobEntry(
                    kind=entry.kind,
                    value=entry.value,
                    status=(
                        JobStatus.COMPLETE
                        if self.fingerprint_sha256 is not None
                        else JobStatus.FAILED
                    ),
                    sha256=self.fingerprint_sha256,
                    error=None,
                )
                for entry in entries
            ),
        )

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return no later job status because fake jobs settle immediately."""

        _ = job_id
        return None


class _FakeCivitai:
    """Return configured CivitAI lookup responses."""

    def __init__(self, result: CivitaiLookupResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Record the hash and return the configured result."""

        self.calls.append(sha256)
        return self.result


class _FakeCatalog:
    """Store manual refresh records in memory."""

    def __init__(self, existing_record: ModelMetadataCacheRecord | None = None) -> None:
        self.existing_record = existing_record
        self.records: list[ModelMetadataCacheRecord] = []
        self.not_found: list[LocalModelEvidence] = []
        self.fresh_checks: list[LocalModelEvidence] = []
        self.record_reads: list[str] = []

    def is_fresh(self, evidence: LocalModelEvidence) -> bool:
        """Record freshness checks and always require refresh."""

        self.fresh_checks.append(evidence)
        return False

    def record_for_sha256(self, sha256: str) -> ModelMetadataCacheRecord | None:
        """Return the configured existing record for preservation tests."""

        self.record_reads.append(sha256)
        return self.existing_record if self.existing_record is not None else None

    def save_record(self, record: ModelMetadataCacheRecord) -> None:
        """Record one saved metadata record."""

        self.records.append(record)

    def save_not_found(self, evidence: LocalModelEvidence, *, fetched_at: str) -> None:
        """Record unexpected not-found writes."""

        _ = fetched_at
        self.not_found.append(evidence)


class _FakeThumbnails:
    """Return configured thumbnail cache results."""

    def __init__(self, result: ThumbnailStoreResult | None = None) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def cache_thumbnail(
        self,
        *,
        sha256: str,
        image: CivitaiImage,
        selection_policy: str,
    ) -> ThumbnailStoreResult | None:
        """Record thumbnail cache requests and return the configured result."""

        _ = selection_policy
        self.calls.append((sha256, image.url))
        return self.result

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
        """Ignore local thumbnail requests in manual provider refresh tests."""

        _ = (
            sha256,
            image,
            source,
            source_label,
            source_path,
            source_width,
            source_height,
        )
        return None


@dataclass
class _FakeUpdateSink:
    """Collect emitted model metadata update events."""

    events: list[ModelMetadataRefreshEvent]

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Record one model metadata update event."""

        self.events.append(event)


class _FakePreferences:
    """Return configured CivitAI preferences."""

    def __init__(
        self, *, metadata_enabled: bool = True, thumbnails_enabled: bool = True
    ) -> None:
        self._preferences = default_civitai_preferences()
        self._preferences = self._preferences.with_metadata_lookup_enabled(
            metadata_enabled
        ).with_thumbnail_downloads_enabled(thumbnails_enabled)

    def load_preferences(self) -> object:
        """Return the configured preferences object."""

        return self._preferences


class _NotCancelled:
    """Provide explicit uncancelled refresh state for direct service tests."""

    def is_cancelled(self) -> bool:
        """Return false because these tests do not request cancellation."""

        return False


def test_manual_refresh_found_saves_metadata_thumbnail_and_emits_event() -> None:
    """A found CivitAI result should replace metadata and cache a fresh thumbnail."""

    entry = _entry("fresh.safetensors", FingerprintStatus.READY, "ABC123")
    thumbnails = _FakeThumbnails(_thumbnail("ABC123", "new-thumb"))
    events: list[ModelMetadataRefreshEvent] = []
    catalog = _FakeCatalog()
    service = _service(
        backend=_FakeBackend((entry,)),
        civitai=_FakeCivitai(
            CivitaiLookupResult(
                status=CivitaiLookupStatus.FOUND,
                version=_version("ABC123"),
            )
        ),
        catalog=catalog,
        thumbnails=thumbnails,
        update_sink=_FakeUpdateSink(events),
    )

    result = service.refresh_model(
        ManualModelMetadataRefreshRequest(kind="loras", value="fresh.safetensors"),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is ManualModelMetadataRefreshStatus.UPDATED
    assert result.thumbnail_updated is True
    assert catalog.fresh_checks == []
    assert catalog.records[0].provider is not None
    assert catalog.records[0].thumbnail is thumbnails.result
    assert thumbnails.calls == [("ABC123", "https://image.example/ABC123.jpg")]
    assert events == [
        ModelMetadataRefreshEvent(
            kind="loras",
            value="fresh.safetensors",
            relative_path="fresh.safetensors",
            sha256="ABC123",
            provider_status="found",
            thumbnail_updated=True,
        )
    ]


def test_manual_refresh_not_found_preserves_existing_metadata() -> None:
    """A CivitAI not-found response should not overwrite cached metadata."""

    existing = _record("ABC123", thumbnail=_thumbnail("ABC123", "old-thumb"))
    catalog = _FakeCatalog(existing_record=existing)
    events: list[ModelMetadataRefreshEvent] = []
    service = _service(
        backend=_FakeBackend(
            (_entry("gone.safetensors", FingerprintStatus.READY, "ABC123"),)
        ),
        civitai=_FakeCivitai(CivitaiLookupResult(status=CivitaiLookupStatus.NOT_FOUND)),
        catalog=catalog,
        thumbnails=_FakeThumbnails(),
        update_sink=_FakeUpdateSink(events),
    )

    result = service.refresh_model(
        ManualModelMetadataRefreshRequest(kind="loras", value="gone.safetensors"),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is ManualModelMetadataRefreshStatus.NOT_FOUND_PRESERVED
    assert catalog.records == []
    assert catalog.not_found == []
    assert events == []


def test_manual_refresh_cached_not_found_can_later_create_association() -> None:
    """Manual refresh should bypass cached not-found state and save a found result."""

    cached_not_found = _record(
        "ABC123",
        provider=None,
        provider_status="not-found",
        thumbnail=None,
    )
    catalog = _FakeCatalog(existing_record=cached_not_found)
    service = _service(
        backend=_FakeBackend(
            (_entry("new.safetensors", FingerprintStatus.READY, "ABC123"),)
        ),
        civitai=_FakeCivitai(
            CivitaiLookupResult(
                status=CivitaiLookupStatus.FOUND,
                version=_version("ABC123"),
            )
        ),
        catalog=catalog,
        thumbnails=_FakeThumbnails(),
        update_sink=_FakeUpdateSink([]),
    )

    result = service.refresh_model(
        ManualModelMetadataRefreshRequest(kind="loras", value="new.safetensors"),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is ManualModelMetadataRefreshStatus.UPDATED
    assert catalog.records[0].provider is not None
    assert catalog.records[0].provider_status == "found"


def test_manual_refresh_found_preserves_existing_thumbnail_when_download_fails() -> (
    None
):
    """A found metadata refresh should carry forward the old thumbnail on cache miss."""

    old_thumbnail = _thumbnail("ABC123", "old-thumb")
    catalog = _FakeCatalog(existing_record=_record("ABC123", thumbnail=old_thumbnail))
    events: list[ModelMetadataRefreshEvent] = []
    service = _service(
        backend=_FakeBackend(
            (_entry("thumb.safetensors", FingerprintStatus.READY, "ABC123"),)
        ),
        civitai=_FakeCivitai(
            CivitaiLookupResult(
                status=CivitaiLookupStatus.FOUND,
                version=_version("ABC123"),
            )
        ),
        catalog=catalog,
        thumbnails=_FakeThumbnails(result=None),
        update_sink=_FakeUpdateSink(events),
    )

    result = service.refresh_model(
        ManualModelMetadataRefreshRequest(kind="loras", value="thumb.safetensors"),
        cancellation_token=_NotCancelled(),
    )

    assert (
        result.status
        is ManualModelMetadataRefreshStatus.UPDATED_METADATA_PRESERVED_THUMBNAIL
    )
    assert result.thumbnail_updated is False
    assert catalog.records[0].thumbnail is old_thumbnail
    assert events[0].thumbnail_updated is False


def test_manual_refresh_lookup_disabled_does_not_query_civitai() -> None:
    """Disabled metadata lookup should stop before provider network work."""

    civitai = _FakeCivitai(
        CivitaiLookupResult(
            status=CivitaiLookupStatus.FOUND,
            version=_version("ABC123"),
        )
    )
    service = _service(
        backend=_FakeBackend(
            (_entry("disabled.safetensors", FingerprintStatus.READY, "ABC123"),)
        ),
        civitai=civitai,
        catalog=_FakeCatalog(),
        thumbnails=_FakeThumbnails(),
        update_sink=_FakeUpdateSink([]),
        preferences=_FakePreferences(metadata_enabled=False),
    )

    result = service.refresh_model(
        ManualModelMetadataRefreshRequest(kind="loras", value="disabled.safetensors"),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is ManualModelMetadataRefreshStatus.LOOKUP_DISABLED
    assert civitai.calls == []


def test_manual_refresh_missing_backend_model_preserves_cache() -> None:
    """A removed local model should not query CivitAI or mutate the cache."""

    catalog = _FakeCatalog()
    civitai = _FakeCivitai(CivitaiLookupResult(status=CivitaiLookupStatus.NOT_FOUND))
    service = _service(
        backend=_FakeBackend(()),
        civitai=civitai,
        catalog=catalog,
        thumbnails=_FakeThumbnails(),
        update_sink=_FakeUpdateSink([]),
    )

    result = service.refresh_model(
        ManualModelMetadataRefreshRequest(kind="loras", value="missing.safetensors"),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is ManualModelMetadataRefreshStatus.MODEL_NOT_FOUND_LOCALLY
    assert civitai.calls == []
    assert catalog.records == []


def test_manual_refresh_requests_missing_fingerprint() -> None:
    """Manual refresh should request a fingerprint when no SHA256 is ready."""

    entry = _entry("hashme.safetensors", FingerprintStatus.MISSING, None)
    backend = _FakeBackend((entry,), fingerprint_sha256="DEF456")
    service = _service(
        backend=backend,
        civitai=_FakeCivitai(
            CivitaiLookupResult(
                status=CivitaiLookupStatus.FOUND,
                version=_version("DEF456"),
            )
        ),
        catalog=_FakeCatalog(),
        thumbnails=_FakeThumbnails(),
        update_sink=_FakeUpdateSink([]),
    )

    result = service.refresh_model(
        ManualModelMetadataRefreshRequest(kind="loras", value="hashme.safetensors"),
        cancellation_token=_NotCancelled(),
    )

    assert result.status is ManualModelMetadataRefreshStatus.UPDATED
    assert backend.fingerprint_requests == [entry]


def test_manual_refresh_unavailable_and_invalid_responses_preserve_cache() -> None:
    """Provider failures should keep existing metadata and skip update events."""

    for lookup_status, expected_status in (
        (
            CivitaiLookupStatus.UNAVAILABLE,
            ManualModelMetadataRefreshStatus.UNAVAILABLE_PRESERVED,
        ),
        (
            CivitaiLookupStatus.INVALID_RESPONSE,
            ManualModelMetadataRefreshStatus.INVALID_RESPONSE_PRESERVED,
        ),
    ):
        catalog = _FakeCatalog(existing_record=_record("ABC123"))
        events: list[ModelMetadataRefreshEvent] = []
        service = _service(
            backend=_FakeBackend(
                (_entry("bad.safetensors", FingerprintStatus.READY, "ABC123"),)
            ),
            civitai=_FakeCivitai(CivitaiLookupResult(status=lookup_status)),
            catalog=catalog,
            thumbnails=_FakeThumbnails(),
            update_sink=_FakeUpdateSink(events),
        )

        result = service.refresh_model(
            ManualModelMetadataRefreshRequest(kind="loras", value="bad.safetensors"),
            cancellation_token=_NotCancelled(),
        )

        assert result.status is expected_status
        assert catalog.records == []
        assert events == []


def _service(
    *,
    backend: _FakeBackend,
    civitai: _FakeCivitai,
    catalog: _FakeCatalog,
    thumbnails: _FakeThumbnails,
    update_sink: _FakeUpdateSink,
    preferences: _FakePreferences | None = None,
) -> ManualModelMetadataRefreshService:
    """Return a manual refresh service with deterministic timing."""

    return ManualModelMetadataRefreshService(
        backend=backend,
        civitai=civitai,
        catalog=catalog,
        thumbnails=thumbnails,
        update_sink=update_sink,
        civitai_preferences=cast(CivitaiPreferenceService | None, preferences),
        clock=lambda: "2026-04-14T12:00:00Z",
        fingerprint_poll_timeout_seconds=0.0,
    )


def _entry(
    relative_path: str,
    fingerprint_status: FingerprintStatus,
    sha256: str | None,
) -> BackendModelCatalogEntry:
    """Return one backend catalog entry."""

    return BackendModelCatalogEntry(
        schema_version=1,
        target_id=f"target-{relative_path}",
        kind="loras",
        value=relative_path,
        display_name=relative_path,
        source=BackendModelSource(root_id="root", relative_path=relative_path),
        file=BackendModelFile(
            extension=".safetensors",
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=fingerprint_status,
            sha256=sha256,
            source="cache" if sha256 else None,
            computed_at="2026-04-14T01:00:00Z" if sha256 else None,
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


def _record(
    sha256: str,
    *,
    provider: CivitaiModelVersion | None = None,
    provider_status: str = "found",
    thumbnail: ThumbnailStoreResult | None = None,
) -> ModelMetadataCacheRecord:
    """Return one cached metadata record."""

    evidence = LocalModelEvidence.from_backend_entry(
        _entry("cached.safetensors", FingerprintStatus.READY, sha256),
        sha256,
    )
    return ModelMetadataCacheRecord(
        schema_version=1,
        local=evidence,
        provider=provider or _version(sha256) if provider_status == "found" else None,
        provider_status=provider_status,
        thumbnail=thumbnail,
        thumbnail_status=(
            ThumbnailSelectionStatus.SELECTED
            if thumbnail is not None
            else ThumbnailSelectionStatus.NO_SFW_IMAGE
        ),
        updated_at="2026-04-14T12:00:00Z",
    )


def _version(sha256: str) -> CivitaiModelVersion:
    """Return one CivitAI version with a safe thumbnail image."""

    return CivitaiModelVersion(
        model_id=100,
        model_version_id=200,
        model_name=f"Model {sha256}",
        model_type="LORA",
        version_name="Version A",
        base_model="SDXL 1.0",
        trained_words=("trigger",),
        description=None,
        version_description=None,
        tags=(),
        creator_username=None,
        creator_image=None,
        nsfw=False,
        nsfw_level="None",
        availability=None,
        files=(),
        images=(
            CivitaiImage(
                image_id=1,
                url=f"https://image.example/{sha256}.jpg",
                image_type="image",
                nsfw=False,
                nsfw_level="None",
                width=512,
                height=768,
                meta=None,
            ),
        ),
        stats={},
        model_page_url="https://civitai.com/models/100?modelVersionId=200",
        source_url=f"https://civitai.com/api/v1/model-versions/by-hash/{sha256}",
        fetched_at="2026-04-14T12:00:00Z",
        raw_provider_payload={},
    )


def _thumbnail(sha256: str, storage_suffix: str) -> ThumbnailStoreResult:
    """Return one cached thumbnail result."""

    return ThumbnailStoreResult(
        source="civitai",
        selection_policy="first-sfw",
        source_image_url=f"https://image.example/{sha256}.jpg",
        source_image_id=1,
        nsfw=False,
        nsfw_level="None",
        source_width=512,
        source_height=768,
        variants=(
            ThumbnailVariant(
                size=128,
                storage_key=f"{sha256}:{storage_suffix}",
                width=128,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=65536,
            ),
        ),
        downloaded_at="2026-04-14T12:00:00Z",
    )
