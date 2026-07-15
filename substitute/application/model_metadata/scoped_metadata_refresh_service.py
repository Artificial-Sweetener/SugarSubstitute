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

"""Refresh CivitAI metadata for model files reported by catalog change events."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from substitute.application.execution import (
    CancellationToken as ExecutionCancellationToken,
    ExecutionContext,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
    ModelMetadataRefreshEvent,
    ModelMetadataUpdateSink,
    RefreshCancellationToken,
)
from substitute.application.model_metadata.refresh_service import (
    ModelMetadataRefreshService,
    ModelMetadataRefreshSummary,
)
from substitute.domain.model_metadata import (
    BackendModelCatalogChangedEntry,
    BackendModelCatalogEntry,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_exception

_LOGGER = get_logger("application.model_metadata.scoped_metadata_refresh_service")
DEFAULT_SCOPED_METADATA_BATCH_SIZE = 8


class _ScopedMetadataProgressSink:
    """Log scoped refresh progress and forward structured metadata updates."""

    def __init__(self, update_sink: ModelMetadataUpdateSink) -> None:
        """Store the update sink used by live UI listeners."""

        self._update_sink = update_sink

    def emit_line(self, line: str) -> None:
        """Log one stable progress line."""

        log_debug(_LOGGER, "Scoped model metadata refresh progress", line=line)

    def emit_progress(self, line: str) -> None:
        """Log one transient progress line."""

        log_debug(_LOGGER, "Scoped model metadata refresh progress", line=line)

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Forward one committed metadata update to the configured sink."""

        self._update_sink.emit_model_updated(event)


class _ExecutionRefreshCancellationToken:
    """Adapt execution cancellation tokens to metadata refresh cancellation."""

    def __init__(self, token: ExecutionCancellationToken) -> None:
        """Store the execution token backing refresh cancellation checks."""

        self._token = token

    def is_cancelled(self) -> bool:
        """Return whether the owning execution task has been cancelled."""

        return self._token.is_cancelled


class ScopedMetadataRefreshService:
    """Queue bounded metadata refresh work for added or modified model files."""

    def __init__(
        self,
        *,
        backend: BackendModelMetadataGateway,
        refresh_service: ModelMetadataRefreshService,
        update_sink: ModelMetadataUpdateSink,
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None] | None = None,
        batch_size: int = DEFAULT_SCOPED_METADATA_BATCH_SIZE,
    ) -> None:
        """Initialize scoped refresh collaborators without starting work."""

        self._backend = backend
        self._refresh_service = refresh_service
        self._progress = _ScopedMetadataProgressSink(update_sink)
        self._scope = TaskScope(
            submitter=submitter,
            scope_id=f"scoped_metadata_refresh_{id(self):x}",
        )
        self._close_submitter = close_submitter
        self._batch_size = max(1, batch_size)
        self._queued: dict[
            tuple[str, str, str, int, str], BackendModelCatalogChangedEntry
        ] = {}
        self._running = False
        self._shutdown_requested = False
        self._lock = RLock()
        self._request_id = 0

    def queue_entries(
        self,
        entries: tuple[BackendModelCatalogChangedEntry, ...],
    ) -> None:
        """Queue added or modified model entries for bounded metadata refresh."""

        normalized = tuple(entry for entry in entries if entry.kind and entry.value)
        if not normalized:
            return
        with self._lock:
            if self._shutdown_requested:
                return
            for entry in normalized:
                self._queued[entry.queue_key] = entry
            if self._running:
                return
            self._running = True
        try:
            self._schedule_drain("queued_entries")
        except Exception:
            with self._lock:
                self._running = False
            log_exception(_LOGGER, "Failed to schedule scoped model metadata refresh")

    def shutdown(self) -> None:
        """Stop accepting work and release owned execution resources."""

        with self._lock:
            self._shutdown_requested = True
            self._queued.clear()
        self._scope.close(reason="scoped_metadata_refresh_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _schedule_drain(self, reason: str) -> None:
        """Submit one queue-drain request through the execution boundary."""

        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            pending_count = len(self._queued)
        self._scope.submit(
            TaskRequest(
                identity=TaskIdentity(
                    request_id=request_id,
                    domain="model_metadata",
                    parts=(("operation_key", "scoped_refresh"),),
                ),
                context=ExecutionContext(
                    operation="scoped_model_metadata_refresh",
                    reason=reason,
                    lane="model_metadata",
                    safe_fields=(
                        ("operation_key", "scoped_refresh"),
                        ("request_id", request_id),
                        ("pending_count", pending_count),
                    ),
                ),
                work=lambda token: self._drain_queue(
                    _ExecutionRefreshCancellationToken(token)
                ),
            )
        )

    def _drain_queue(self, cancellation: RefreshCancellationToken) -> None:
        """Drain queued changes in bounded batches until no work remains."""

        try:
            while not cancellation.is_cancelled():
                batch = self._next_batch()
                if not batch:
                    return
                self._refresh_batch(batch, cancellation=cancellation)
        except Exception:
            log_exception(_LOGGER, "Scoped model metadata refresh failed")
        finally:
            with self._lock:
                self._running = False
                should_continue = bool(self._queued) and not self._shutdown_requested
                if should_continue:
                    self._running = True
            if should_continue:
                try:
                    self._schedule_drain("queued_entries_remain")
                except Exception:
                    with self._lock:
                        self._running = False
                    log_exception(
                        _LOGGER,
                        "Failed to reschedule scoped model metadata refresh",
                    )

    def _next_batch(self) -> tuple[BackendModelCatalogChangedEntry, ...]:
        """Pop the next bounded batch from the queue."""

        with self._lock:
            if self._shutdown_requested or not self._queued:
                return ()
            keys = tuple(self._queued)[: self._batch_size]
            return tuple(self._queued.pop(key) for key in keys)

    def _refresh_batch(
        self,
        changed_entries: tuple[BackendModelCatalogChangedEntry, ...],
        *,
        cancellation: RefreshCancellationToken,
    ) -> None:
        """Refresh metadata for one batch of changed backend entries."""

        kinds = tuple(sorted({entry.kind for entry in changed_entries}))
        catalog_entries = self._matching_catalog_entries(changed_entries, kinds)
        if not catalog_entries:
            log_debug(
                _LOGGER,
                "Scoped model metadata refresh skipped; backend entries not found",
                requested_count=len(changed_entries),
                kinds=kinds,
            )
            return
        summary = self._refresh_service.refresh_entries(
            catalog_entries,
            self._progress,
            cancellation_token=cancellation,
        )
        self._log_summary(summary, requested_count=len(changed_entries), kinds=kinds)

    def _matching_catalog_entries(
        self,
        changed_entries: tuple[BackendModelCatalogChangedEntry, ...],
        kinds: tuple[str, ...],
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return current backend catalog entries matching the changed files."""

        changed_keys = {
            (entry.kind, entry.value, entry.source.root_id, entry.source.relative_path)
            for entry in changed_entries
        }
        matches: list[BackendModelCatalogEntry] = []
        for entry in self._backend.list_models(kinds):
            key = (
                entry.kind,
                entry.value,
                entry.source.root_id,
                entry.source.relative_path,
            )
            if key in changed_keys:
                matches.append(entry)
        return tuple(matches)

    def _log_summary(
        self,
        summary: ModelMetadataRefreshSummary,
        *,
        requested_count: int,
        kinds: tuple[str, ...],
    ) -> None:
        """Log one completed scoped metadata refresh batch."""

        log_debug(
            _LOGGER,
            "Scoped model metadata refresh completed",
            requested_count=requested_count,
            kinds=kinds,
            discovered=summary.discovered,
            fingerprint_requested=summary.fingerprint_requested,
            enriched=summary.enriched,
            not_found=summary.not_found,
            skipped=summary.skipped,
            failed=summary.failed,
            cancelled=summary.cancelled,
        )


__all__ = ["DEFAULT_SCOPED_METADATA_BATCH_SIZE", "ScopedMetadataRefreshService"]
