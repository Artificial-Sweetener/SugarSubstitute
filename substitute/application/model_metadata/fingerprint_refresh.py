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

"""Own background fingerprint jobs until terminal state or explicit cancellation."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
    ModelMetadataProgressSink,
    RefreshCancellationToken,
)
from substitute.domain.model_metadata import (
    BackendFingerprintJob,
    BackendModelCatalogEntry,
    FingerprintStatus,
    JobStatus,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.model_metadata.fingerprint_refresh")


@dataclass(frozen=True)
class FingerprintRefreshBatch:
    """Publish newly ready models once and account for terminal failures."""

    models: tuple[BackendModelCatalogEntry, ...] = ()
    hashes: tuple[tuple[str, str, str], ...] = ()
    requested: int = 0
    failed: int = 0


class ModelFingerprintRefresh:
    """Stream ready fingerprints without imposing a library-size time limit."""

    def __init__(
        self,
        backend: BackendModelMetadataGateway,
        *,
        sleep: Callable[[float], None],
        poll_interval_seconds: float,
    ) -> None:
        """Store the cancellable job's network and scheduling boundaries."""
        self._backend = backend
        self._sleep = sleep
        self._poll_interval_seconds = poll_interval_seconds

    def batches(
        self,
        models: tuple[BackendModelCatalogEntry, ...],
        progress: ModelMetadataProgressSink,
        cancellation: RefreshCancellationToken,
    ) -> Iterator[FingerprintRefreshBatch]:
        """Yield ready models while retaining responsibility for unfinished hashes.

        Backend requests have individual transport timeouts. A running hashing job
        owns its completion: library size is not a deadline. Closing the refresh
        cancels observation at the next bounded request or scheduling boundary.
        """
        ready = tuple(model for model in models if ready_sha256(model) is not None)
        missing = tuple(model for model in models if ready_sha256(model) is None)
        pending = {(model.kind, model.value): model for model in missing}
        if cancellation.is_cancelled():
            return
        if ready:
            yield FingerprintRefreshBatch(models=ready)
        if not pending or cancellation.is_cancelled():
            return
        current: BackendFingerprintJob | None = self._backend.refresh_fingerprints(
            missing
        )
        yield FingerprintRefreshBatch(requested=len(missing))
        while not cancellation.is_cancelled():
            if current is None:
                log_warning(
                    _LOGGER,
                    "Fingerprint job became unavailable",
                    pending_count=len(pending),
                )
                yield FingerprintRefreshBatch(failed=len(pending))
                return
            completed: list[BackendModelCatalogEntry] = []
            hashes: list[tuple[str, str, str]] = []
            failed = 0
            for entry in current.entries:
                key = (entry.kind, entry.value)
                if key not in pending:
                    continue
                if entry.status is JobStatus.COMPLETE and entry.sha256:
                    completed.append(pending.pop(key))
                    hashes.append((*key, entry.sha256.upper()))
                elif entry.status in {JobStatus.FAILED, JobStatus.COMPLETE}:
                    pending.pop(key)
                    failed += 1
                    log_warning(
                        _LOGGER,
                        "Model fingerprint failed",
                        kind=entry.kind,
                        value=entry.value,
                        reason=entry.error or "missing hash",
                    )
            if completed or failed:
                yield FingerprintRefreshBatch(
                    tuple(completed), tuple(hashes), failed=failed
                )
            if current.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
                if pending:
                    log_warning(
                        _LOGGER,
                        "Fingerprint job ended with unfinished models",
                        job_id=current.job_id,
                        pending_count=len(pending),
                        status=current.status.value,
                    )
                    yield FingerprintRefreshBatch(failed=len(pending))
                return
            progress.emit_progress(
                f"Model metadata: fingerprinting {len(missing) - len(pending)}/{len(missing)} models\r"
            )
            self._sleep(self._poll_interval_seconds)
            if cancellation.is_cancelled():
                return
            current = self._backend.get_fingerprint_job(current.job_id)


def ready_sha256(entry: BackendModelCatalogEntry) -> str | None:
    """Return authoritative fingerprint or sidecar evidence when already available."""
    if entry.fingerprint.status is FingerprintStatus.READY and entry.fingerprint.sha256:
        return entry.fingerprint.sha256.upper()
    if entry.sidecar.sha256:
        return entry.sidecar.sha256.upper()
    return None
