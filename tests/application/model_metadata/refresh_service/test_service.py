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

"""Verify metadata enrichment and committed model update events."""

from __future__ import annotations
from substitute.application.model_metadata import (
    ModelMetadataRefreshEvent,
    ModelMetadataRefreshService,
)
from substitute.domain.model_metadata import (
    FingerprintStatus,
)
from .characterization_support import (
    _FakeProgressSink,
    _NotCancelled,
    _FakeBackend,
    _DelayedCapabilitiesBackend,
    _FakeCivitai,
    _FakeCatalog,
    _FakeThumbnails,
    _entry,
)


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
