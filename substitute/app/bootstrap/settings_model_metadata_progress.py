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

"""Publish Settings metadata refresh results to the catalog and open shell."""

from collections.abc import Callable

from substitute.application.model_metadata import ModelMetadataRefreshEvent
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("app.bootstrap.settings_model_metadata_progress")


class SettingsModelMetadataProgressSink:
    """Invalidate catalog snapshots before forwarding a completed model update."""

    def __init__(
        self,
        *,
        invalidate_catalog: Callable[[], None],
        publish_update: Callable[[ModelMetadataRefreshEvent], None],
    ) -> None:
        """Store catalog invalidation and thread-safe shell publication boundaries."""
        self._invalidate_catalog = invalidate_catalog
        self._publish_update = publish_update

    def emit_line(self, line: str) -> None:
        """Keep Settings refresh diagnostics outside widget lifetimes."""
        log_debug(_LOGGER, "Settings CivitAI metadata refresh progress", line=line)

    def emit_progress(self, line: str) -> None:
        """Record transient progress through the same diagnostic owner."""
        self.emit_line(line)

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Make a stored thumbnail available to currently mounted model pickers."""
        log_debug(
            _LOGGER,
            "Settings CivitAI metadata refresh updated model",
            kind=event.kind,
            value=event.value,
            thumbnail_updated=event.thumbnail_updated,
        )
        self._invalidate_catalog()
        self._publish_update(event)
