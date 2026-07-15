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

"""Bridge background model metadata updates onto the Qt event loop."""

from __future__ import annotations

from threading import RLock

from PySide6.QtCore import QObject, Signal

from substitute.application.model_metadata import ModelMetadataRefreshEvent
from substitute.shared.startup_trace import trace_mark


class ModelMetadataUpdateBridge(QObject):
    """Emit metadata refresh events through Qt's thread-safe signal dispatch."""

    model_updated = Signal(object)
    _flush_requested = Signal()
    _end_startup_coalescing_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize bridge state for optional startup coalescing."""

        super().__init__(parent)
        self._startup_coalescing = False
        self._pending_events: list[ModelMetadataRefreshEvent] = []
        self._coalesced_events: dict[str, ModelMetadataRefreshEvent] = {}
        self._lock = RLock()
        self._flush_requested.connect(self.flush)
        self._end_startup_coalescing_requested.connect(self.end_startup_coalescing)

    def begin_startup_coalescing(self) -> None:
        """Start batching metadata updates during startup restore."""

        with self._lock:
            events_to_emit = tuple(self._pending_events)
            self._pending_events.clear()
            pending_count = len(self._coalesced_events)
            self._startup_coalescing = True
        trace_mark(
            "metadata_update_bridge.coalesce.begin",
            pending_count=pending_count,
        )
        for event in events_to_emit:
            self.model_updated.emit(event)

    def flush_startup_coalescing(self) -> None:
        """Emit currently coalesced metadata updates."""

        with self._lock:
            self._drain_pending_into_coalescing_locked()
            events = tuple(self._coalesced_events.values())
            self._coalesced_events.clear()
        trace_mark("metadata_update_bridge.flush", pending_count=len(events))
        for event in events:
            self.model_updated.emit(event)

    def end_startup_coalescing(self) -> None:
        """Flush pending updates and resume immediate metadata dispatch."""

        with self._lock:
            self._drain_pending_into_coalescing_locked()
            if not self._startup_coalescing:
                pending_count = len(self._coalesced_events)
                events: tuple[ModelMetadataRefreshEvent, ...] = ()
                should_flush = False
            else:
                pending_count = len(self._coalesced_events)
                self._startup_coalescing = False
                events = tuple(self._coalesced_events.values())
                self._coalesced_events.clear()
                should_flush = True
        if not should_flush:
            trace_mark(
                "metadata_update_bridge.coalesce.end_skip",
                reason="not_coalescing",
                pending_count=pending_count,
            )
            return
        trace_mark(
            "metadata_update_bridge.coalesce.end",
            pending_count=pending_count,
        )
        for event in events:
            self.model_updated.emit(event)

    def request_end_startup_coalescing(self) -> None:
        """Request coalescing shutdown through this QObject's thread."""

        trace_mark("metadata_update_bridge.coalesce.end_requested")
        self._end_startup_coalescing_requested.emit()

    def timeout_startup_coalescing(self) -> None:
        """Flush startup coalescing after the safety timeout expires."""

        with self._lock:
            startup_coalescing = self._startup_coalescing
            pending_count = len(self._coalesced_events) + len(self._pending_events)
        if not startup_coalescing:
            trace_mark(
                "metadata_update_bridge.coalesce.timeout_skip",
                reason="not_coalescing",
            )
            return
        trace_mark(
            "metadata_update_bridge.coalesce.timeout_flush",
            pending_count=pending_count,
        )
        self.end_startup_coalescing()

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Queue one refresh event for GUI-thread coalescing and publication."""

        trace_mark(
            "model_metadata_update_bridge.emit_model_updated",
            kind=event.kind,
            thumbnail_updated=event.thumbnail_updated,
        )
        with self._lock:
            self._pending_events.append(event)
        self._flush_requested.emit()

    def flush(self) -> None:
        """Publish or coalesce queued refresh events on the GUI thread."""

        with self._lock:
            if self._startup_coalescing:
                self._drain_pending_into_coalescing_locked()
                return
            events = tuple(self._pending_events)
            self._pending_events.clear()
        trace_mark("metadata_update_bridge.publish", pending_count=len(events))
        for event in events:
            self.model_updated.emit(event)

    def _drain_pending_into_coalescing_locked(self) -> None:
        """Fold queued events into the startup coalescing map."""

        pending_events = tuple(self._pending_events)
        self._pending_events.clear()
        for event in pending_events:
            existing = self._coalesced_events.get(event.kind)
            if (
                existing is None
                or event.thumbnail_updated
                or not existing.thumbnail_updated
            ):
                self._coalesced_events[event.kind] = event
            trace_mark(
                "metadata_update_bridge.coalesce",
                kind=event.kind,
                thumbnail_updated=event.thumbnail_updated,
                pending_count=len(self._coalesced_events),
            )


__all__ = ["ModelMetadataUpdateBridge"]
