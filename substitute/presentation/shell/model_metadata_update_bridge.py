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

"""Batch background metadata updates onto the next GUI event-loop turn."""

from __future__ import annotations
from threading import RLock
from PySide6.QtCore import QObject, Qt, Signal, Slot
from substitute.application.model_metadata import ModelMetadataRefreshEvent
from substitute.shared.startup_trace import trace_mark


class ModelMetadataUpdateBridge(QObject):
    """Publish ready metadata promptly with bounded per-kind pending state."""

    model_updated = Signal(object)
    _flush_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Own one queued publication at a time on the receiver's GUI thread."""
        super().__init__(parent)
        self._pending: dict[str, ModelMetadataRefreshEvent] = {}
        self._flush_scheduled = False
        self._lock = RLock()
        self._flush_requested.connect(self._flush, Qt.ConnectionType.QueuedConnection)

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Retain the latest affected thumbnail and schedule one bounded delivery."""
        with self._lock:
            previous = self._pending.get(event.kind)
            if (
                previous is None
                or event.thumbnail_updated
                or not previous.thumbnail_updated
            ):
                self._pending[event.kind] = event
            if self._flush_scheduled:
                return
            self._flush_scheduled = True
        self._flush_requested.emit()

    @Slot()
    def _flush(self) -> None:
        """Publish each changed kind without waiting for the library refresh to end."""
        with self._lock:
            events = tuple(self._pending.values())
            self._pending.clear()
            self._flush_scheduled = False
        trace_mark("metadata_update_bridge.publish", pending_count=len(events))
        for event in events:
            self.model_updated.emit(event)


__all__ = ["ModelMetadataUpdateBridge"]
