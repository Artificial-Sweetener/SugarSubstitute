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

"""Tests for model metadata refresh orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.model_metadata import (
    ModelMetadataRefreshEvent,
    ModelMetadataRefreshService,
)
from substitute.domain.model_metadata import (
    BackendCapabilities,
    BackendFingerprint,
    BackendFingerprintJob,
    BackendFingerprintJobEntry,
    BackendHashLookupResult,
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
    ThumbnailStoreResult,
    ThumbnailVariant,
)


@dataclass
class _FakeProgressSink:
    """Collect refresh progress records."""

    records: list[str]
    events: list[ModelMetadataRefreshEvent] | None = None

    def emit_line(self, line: str) -> None:
        """Record one stable line."""

        self.records.append(line)

    def emit_progress(self, line: str) -> None:
        """Record one transient progress line."""

        self.records.append(line)

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Record one structured metadata update event."""

        if self.events is not None:
            self.events.append(event)


class _NotCancelled:
    """Provide explicit uncancelled refresh state for direct service tests."""

    def is_cancelled(self) -> bool:
        """Return false because these tests do not request cancellation."""

        return False


class _FakeBackend:
    """Provide deterministic backend metadata responses."""

    def __init__(self, entries: tuple[BackendModelCatalogEntry, ...]) -> None:
        self.entries = entries
        self.fingerprint_requests: list[BackendModelCatalogEntry] = []
        self.capability_attempts = 0

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return backend capabilities with hashing enabled."""

        self.capability_attempts += 1
        return BackendCapabilities(
            api_version=1,
            model_metadata_schema_version=1,
            supported_model_kinds=("loras",),
            background_hashing=True,
            hash_lookup=True,
            local_preview_serving=True,
            sidecar_reading=True,
        )

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return fake model entries."""

        _ = refresh
        assert kinds == ("loras",)
        return self.entries

    def refresh_fingerprints(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
    ) -> BackendFingerprintJob:
        """Return a complete fake fingerprint job for requested entries."""

        self.fingerprint_requests.extend(entries)
        return BackendFingerprintJob(
            job_id="job-1",
            status=JobStatus.COMPLETE,
            entries=tuple(
                BackendFingerprintJobEntry(
                    kind=entry.kind,
                    value=entry.value,
                    status=JobStatus.COMPLETE,
                    sha256="DEF456",
                    error=None,
                )
                for entry in entries
            ),
        )

    def get_fingerprint_job(self, _job_id: str) -> BackendFingerprintJob | None:
        """Return no later job status because fake jobs complete immediately."""

        return None

    def lookup_model_by_hash(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> BackendHashLookupResult | None:
        """Return no hash lookup results for refresh-only tests."""

        _ = (kind, sha256)
        return None


class _DelayedCapabilitiesBackend(_FakeBackend):
    """Return no capabilities until a configured attempt count."""

    def __init__(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
        *,
        ready_after_attempts: int,
    ) -> None:
        super().__init__(entries)
        self._ready_after_attempts = ready_after_attempts

    def get_capabilities(self) -> BackendCapabilities | None:
        """Return capabilities only after the configured attempt count."""

        self.capability_attempts += 1
        if self.capability_attempts < self._ready_after_attempts:
            return None
        return BackendCapabilities(
            api_version=1,
            model_metadata_schema_version=1,
            supported_model_kinds=("loras",),
            background_hashing=True,
            hash_lookup=True,
            local_preview_serving=True,
            sidecar_reading=True,
        )


class _FakeCivitai:
    """Provide deterministic CivitAI lookup responses."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Return found or not-found results by SHA256."""

        self.calls.append(sha256)
        if sha256 == "NOTFOUND":
            return CivitaiLookupResult(status=CivitaiLookupStatus.NOT_FOUND)
        return CivitaiLookupResult(
            status=CivitaiLookupStatus.FOUND,
            version=_version(sha256),
        )


class _FakeCatalog:
    """Store refresh records in memory."""

    def __init__(self, fresh_sha256: str | None = None) -> None:
        self.fresh_sha256 = fresh_sha256
        self.records: list[ModelMetadataCacheRecord] = []
        self.not_found: list[LocalModelEvidence] = []

    def is_fresh(self, evidence: LocalModelEvidence) -> bool:
        """Return configured freshness for one SHA256."""

        return evidence.sha256 == self.fresh_sha256

    def save_record(self, record: ModelMetadataCacheRecord) -> None:
        """Record one saved metadata record."""

        self.records.append(record)

    def record_for_sha256(self, sha256: str) -> ModelMetadataCacheRecord | None:
        """Return the latest saved record for one SHA256."""

        for record in reversed(self.records):
            if record.local.sha256 == sha256:
                return record
        return None

    def save_not_found(self, evidence: LocalModelEvidence, *, fetched_at: str) -> None:
        """Record one not-found cache write."""

        _ = fetched_at
        self.not_found.append(evidence)


class _FakeThumbnails:
    """Store thumbnail requests in memory."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def cache_thumbnail(
        self,
        *,
        sha256: str,
        image: CivitaiImage,
        selection_policy: str,
    ) -> ThumbnailStoreResult:
        """Return one fake cached thumbnail result."""

        self.calls.append(image.url)
        return ThumbnailStoreResult(
            source="civitai",
            selection_policy=selection_policy,
            source_image_url=image.url,
            source_image_id=image.image_id,
            nsfw=image.nsfw,
            nsfw_level=image.nsfw_level,
            source_width=image.width,
            source_height=image.height,
            variants=(
                ThumbnailVariant(
                    size=128,
                    storage_key=f"{sha256}:128",
                    width=128,
                    height=128,
                    content_format="sqthumb-qimage-argb32-premultiplied",
                    byte_size=65536,
                ),
            ),
            downloaded_at="2026-04-14T12:00:00Z",
        )

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
        """Ignore local thumbnail requests in provider refresh tests."""

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


def test_refresh_enriches_hash_ready_models_and_skips_fresh_entries() -> None:
    """Refresh service should skip fresh records and enrich changed ones."""

    backend = _FakeBackend(
        (
            _entry("fresh.safetensors", FingerprintStatus.READY, "ABC123"),
            _entry("changed.safetensors", FingerprintStatus.READY, "DEF456"),
        )
    )
    civitai = _FakeCivitai()
    catalog = _FakeCatalog(fresh_sha256="ABC123")
    thumbnails = _FakeThumbnails()
    progress = _FakeProgressSink(records=[])
    service = ModelMetadataRefreshService(
        backend=backend,
        civitai=civitai,
        catalog=catalog,
        thumbnails=thumbnails,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    summary = service.refresh(progress, cancellation_token=_NotCancelled())

    assert summary.discovered == 2
    assert summary.skipped == 1
    assert summary.enriched == 1
    assert summary.thumbnails_cached == 1
    assert civitai.calls == ["DEF456"]
    assert thumbnails.calls == ["https://image.example/DEF456.jpg"]
    assert catalog.records[0].local.relative_path == "changed.safetensors"
    assert progress.records[-1].startswith("Model metadata: complete.")


def test_refresh_emits_structured_update_for_saved_record() -> None:
    """Refresh service should report committed metadata and thumbnail updates."""

    backend = _FakeBackend(
        (_entry("changed.safetensors", FingerprintStatus.READY, "DEF456"),)
    )
    events: list[ModelMetadataRefreshEvent] = []
    service = ModelMetadataRefreshService(
        backend=backend,
        civitai=_FakeCivitai(),
        catalog=_FakeCatalog(),
        thumbnails=_FakeThumbnails(),
        model_kinds=("loras",),
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    summary = service.refresh(
        _FakeProgressSink(records=[], events=events),
        cancellation_token=_NotCancelled(),
    )

    assert summary.enriched == 1
    assert events == [
        ModelMetadataRefreshEvent(
            kind="loras",
            value="changed.safetensors",
            relative_path="changed.safetensors",
            sha256="DEF456",
            provider_status="found",
            thumbnail_updated=True,
        )
    ]


def test_refresh_fingerprints_missing_hashes_and_records_not_found() -> None:
    """Refresh service should use backend fingerprint jobs before CivitAI lookup."""

    backend = _FakeBackend(
        (_entry("missing.safetensors", FingerprintStatus.MISSING, None),)
    )
    civitai = _FakeCivitai()
    catalog = _FakeCatalog()
    thumbnails = _FakeThumbnails()
    progress = _FakeProgressSink(records=[])
    service = ModelMetadataRefreshService(
        backend=backend,
        civitai=civitai,
        catalog=catalog,
        thumbnails=thumbnails,
        model_kinds=("loras",),
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    summary = service.refresh(progress, cancellation_token=_NotCancelled())

    assert summary.fingerprint_requested == 1
    assert summary.enriched == 1
    assert backend.fingerprint_requests[0].value == "missing.safetensors"
    assert civitai.calls == ["DEF456"]


def test_refresh_records_provider_not_found_without_thumbnail() -> None:
    """Refresh service should record not-found provider lookups without failing."""

    backend = _FakeBackend(
        (_entry("gone.safetensors", FingerprintStatus.READY, "NOTFOUND"),)
    )
    civitai = _FakeCivitai()
    catalog = _FakeCatalog()
    thumbnails = _FakeThumbnails()
    service = ModelMetadataRefreshService(
        backend=backend,
        civitai=civitai,
        catalog=catalog,
        thumbnails=thumbnails,
        model_kinds=("loras",),
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    summary = service.refresh(
        _FakeProgressSink(records=[]),
        cancellation_token=_NotCancelled(),
    )

    assert summary.not_found == 1
    assert catalog.not_found[0].sha256 == "NOTFOUND"
    assert thumbnails.calls == []


def test_refresh_emits_structured_update_for_provider_not_found() -> None:
    """Refresh service should report provider-not-found cache commits."""

    events: list[ModelMetadataRefreshEvent] = []
    service = ModelMetadataRefreshService(
        backend=_FakeBackend(
            (_entry("gone.safetensors", FingerprintStatus.READY, "NOTFOUND"),)
        ),
        civitai=_FakeCivitai(),
        catalog=_FakeCatalog(),
        thumbnails=_FakeThumbnails(),
        model_kinds=("loras",),
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    summary = service.refresh(
        _FakeProgressSink(records=[], events=events),
        cancellation_token=_NotCancelled(),
    )

    assert summary.not_found == 1
    assert events == [
        ModelMetadataRefreshEvent(
            kind="loras",
            value="gone.safetensors",
            relative_path="gone.safetensors",
            sha256="NOTFOUND",
            provider_status="not-found",
            thumbnail_updated=False,
        )
    ]


def test_refresh_waits_for_backend_capabilities_before_skipping() -> None:
    """Refresh service should give backend routes a grace period after port readiness."""

    backend = _DelayedCapabilitiesBackend(
        (_entry("late.safetensors", FingerprintStatus.READY, "ABC123"),),
        ready_after_attempts=3,
    )
    civitai = _FakeCivitai()
    catalog = _FakeCatalog()
    thumbnails = _FakeThumbnails()
    sleeps: list[float] = []
    progress = _FakeProgressSink(records=[])
    service = ModelMetadataRefreshService(
        backend=backend,
        civitai=civitai,
        catalog=catalog,
        thumbnails=thumbnails,
        model_kinds=("loras",),
        capability_wait_timeout_seconds=5.0,
        capability_retry_interval_seconds=0.25,
        sleep=sleeps.append,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    summary = service.refresh(progress, cancellation_token=_NotCancelled())

    assert summary.enriched == 1
    assert backend.capability_attempts == 3
    assert sleeps == [0.25, 0.25]
    assert (
        "Model metadata: waiting for Substitute BackEnd model API." in progress.records
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
