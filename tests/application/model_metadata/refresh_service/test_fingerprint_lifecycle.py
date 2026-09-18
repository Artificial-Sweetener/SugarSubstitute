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

"""Prove automatic fingerprint ownership, progressive updates, and cancellation."""

from __future__ import annotations
import pytest
from substitute.application.model_metadata import refresh_service
from substitute.application.model_metadata import (
    ModelMetadataRefreshService,
)
from substitute.domain.model_metadata import (
    BackendFingerprintJob,
    BackendFingerprintJobEntry,
    BackendModelCatalogEntry,
    FingerprintStatus,
    JobStatus,
)
from .characterization_support import (
    _FakeProgressSink,
    _NotCancelled,
    _FakeBackend,
    _FakeCivitai,
    _FakeCatalog,
    _FakeThumbnails,
    _entry,
)


class _RefreshClock:
    """Advance only the refresh owner's clock without patching shared time."""

    def __init__(self) -> None:
        """Start a deterministic background job timeline."""
        self.elapsed = 0.0

    def monotonic(self) -> float:
        """Return simulated elapsed time."""
        return self.elapsed

    def advance(self, _seconds: float) -> None:
        """Represent a large model making slow but valid progress."""
        self.elapsed += 121.0


def test_refresh_keeps_ownership_until_slow_fingerprinting_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A healthy large-model job must not leave models without automatic metadata."""

    class SlowBackend(_FakeBackend):
        """Finish hashing after the former two-minute foreground budget."""

        polls = 0

        def refresh_fingerprints(
            self, entries: tuple[BackendModelCatalogEntry, ...]
        ) -> BackendFingerprintJob:
            """Start one owned job without ready hashes."""
            self.fingerprint_requests.extend(entries)
            return BackendFingerprintJob("slow-job", JobStatus.RUNNING, ())

        def get_fingerprint_job(self, _job_id: str) -> BackendFingerprintJob:
            """Publish a terminal hash on the second poll."""
            self.polls += 1
            if self.polls == 1:
                return BackendFingerprintJob("slow-job", JobStatus.RUNNING, ())
            return BackendFingerprintJob(
                "slow-job",
                JobStatus.COMPLETE,
                (
                    BackendFingerprintJobEntry(
                        "loras", "large.safetensors", JobStatus.COMPLETE, "DEF456", None
                    ),
                ),
            )

    clock = _RefreshClock()
    monkeypatch.setattr(refresh_service, "time", clock)
    backend = SlowBackend(
        (_entry("large.safetensors", FingerprintStatus.MISSING, None),)
    )
    catalog = _FakeCatalog()
    progress = _FakeProgressSink(records=[], events=[])
    service = ModelMetadataRefreshService(
        backend=backend,
        civitai=_FakeCivitai(),
        catalog=catalog,
        thumbnails=_FakeThumbnails(),
        sleep=clock.advance,
    )

    summary = service.refresh(progress, cancellation_token=_NotCancelled())

    assert summary.enriched == 1
    assert summary.thumbnails_cached == 1
    assert len(catalog.records) == 1
    assert progress.events and progress.events[0].thumbnail_updated
    assert backend.polls == 2


def test_refresh_publishes_ready_metadata_before_remaining_hashes_finish() -> None:
    """Ready previews must become usable while large models are still hashing."""
    catalog = _FakeCatalog()
    entries = (
        _entry("ready.safetensors", FingerprintStatus.READY, "ABC123"),
        _entry("pending.safetensors", FingerprintStatus.MISSING, None),
    )

    class ObservedBackend(_FakeBackend):
        """Observe the persisted ready model before publishing the remaining hash."""

        def refresh_fingerprints(
            self, entries: tuple[BackendModelCatalogEntry, ...]
        ) -> BackendFingerprintJob:
            """Require the ready preview to have been published already."""
            assert [record.local.sha256 for record in catalog.records] == ["ABC123"]
            return super().refresh_fingerprints(entries)

    service = ModelMetadataRefreshService(
        backend=ObservedBackend(entries),
        civitai=_FakeCivitai(),
        catalog=catalog,
        thumbnails=_FakeThumbnails(),
    )
    summary = service.refresh(
        _FakeProgressSink(records=[]), cancellation_token=_NotCancelled()
    )
    assert summary.enriched == 2
    assert summary.thumbnails_cached == 2


def test_refresh_reports_unfinished_terminal_hashes_as_failures() -> None:
    """A failed backend job must not report a successful empty metadata refresh."""

    class FailedBackend(_FakeBackend):
        """End the backend job before producing its requested hash."""

        def refresh_fingerprints(
            self, entries: tuple[BackendModelCatalogEntry, ...]
        ) -> BackendFingerprintJob:
            """Return terminal failure with an unfinished model."""
            return BackendFingerprintJob("failed-job", JobStatus.FAILED, ())

    progress = _FakeProgressSink(records=[])
    service = ModelMetadataRefreshService(
        backend=FailedBackend(
            (_entry("missing.safetensors", FingerprintStatus.MISSING, None),)
        ),
        civitai=_FakeCivitai(),
        catalog=_FakeCatalog(),
        thumbnails=_FakeThumbnails(),
    )
    summary = service.refresh(progress, cancellation_token=_NotCancelled())
    assert summary.fingerprint_requested == 1
    assert summary.failed == 1
    assert progress.records[-1].startswith("Model metadata: incomplete.")


def test_refresh_cancels_running_fingerprint_observation_before_next_request() -> None:
    """Shutdown must release an active hashing observer without another network call."""

    class Cancellation:
        """Expose explicit cancellation at the scheduling boundary."""

        cancelled = False

        def is_cancelled(self) -> bool:
            """Return whether shutdown has requested cancellation."""
            return self.cancelled

        def cancel(self, _seconds: float) -> None:
            """Cancel when the observer yields to its scheduler."""
            self.cancelled = True

    class RunningBackend(_FakeBackend):
        """Keep a job running until its observer is cancelled."""

        def refresh_fingerprints(
            self, entries: tuple[BackendModelCatalogEntry, ...]
        ) -> BackendFingerprintJob:
            """Start the background job."""
            return BackendFingerprintJob("running-job", JobStatus.RUNNING, ())

        def get_fingerprint_job(self, _job_id: str) -> BackendFingerprintJob | None:
            """Reject any request after cancellation."""
            raise AssertionError("Cancelled observer queried the backend")

    token = Cancellation()
    progress = _FakeProgressSink(records=[])
    service = ModelMetadataRefreshService(
        backend=RunningBackend(
            (_entry("missing.safetensors", FingerprintStatus.MISSING, None),)
        ),
        civitai=_FakeCivitai(),
        catalog=_FakeCatalog(),
        thumbnails=_FakeThumbnails(),
        sleep=token.cancel,
    )
    summary = service.refresh(progress, cancellation_token=token)
    assert summary.cancelled
    assert summary.enriched == 0
    assert progress.records[-1] == "Model metadata: refresh canceled during shutdown."
