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

"""Bridge backend model catalog change events onto the Qt event loop."""

from __future__ import annotations

from threading import RLock

from PySide6.QtCore import QObject, Signal

from substitute.application.model_metadata import BackendModelCatalogChangeEvent
from substitute.shared.startup_trace import trace_mark


class ModelCatalogUpdateBridge(QObject):
    """Emit model catalog changes through Qt's thread-safe signal dispatch."""

    model_catalog_changed = Signal(object)
    _flush_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize bridge state for burst coalescing by model kind."""

        super().__init__(parent)
        self._coalesced_events: dict[str, BackendModelCatalogChangeEvent] = {}
        self._lock = RLock()
        self._flush_requested.connect(self.flush)

    def emit_model_catalog_changed(
        self,
        event: BackendModelCatalogChangeEvent,
    ) -> None:
        """Coalesce one background event and request GUI-thread delivery."""

        trace_mark(
            "model_catalog_update_bridge.enqueue",
            revision=event.revision,
            kinds=event.kinds,
            added_count=len(event.added),
            removed_count=len(event.removed),
            modified_count=len(event.modified),
        )
        key = ",".join(event.kinds) or event.revision
        with self._lock:
            self._coalesced_events[key] = event
        self._flush_requested.emit()

    def flush(self) -> None:
        """Emit currently coalesced catalog change events on the GUI thread."""

        with self._lock:
            events = tuple(self._coalesced_events.values())
            self._coalesced_events.clear()
        trace_mark("model_catalog_update_bridge.flush", pending_count=len(events))
        for event in events:
            self.model_catalog_changed.emit(event)


__all__ = ["ModelCatalogUpdateBridge"]
