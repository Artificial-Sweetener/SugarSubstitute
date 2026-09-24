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

"""Load bounded model-version previews without delaying interactive transfers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal

from sugarsubstitute_shared.model_discovery import DiscoveredModel

_LOGGER = logging.getLogger(__name__)


class VersionThumbnailSignals(QObject):
    """Deliver one version's preview or fallback to the owning Qt thread."""

    loaded = Signal(int, object)
    failed = Signal(int)
    finished = Signal()


class VersionThumbnailLoad(QRunnable):
    """Fetch provider previews independently of the version/download task."""

    def __init__(
        self,
        versions: Sequence[DiscoveredModel],
        *,
        fetch: Callable[[str], bytes],
    ) -> None:
        """Retain exact-version URLs and the governed image transport."""

        super().__init__()
        self.setAutoDelete(False)
        self.signals = VersionThumbnailSignals()
        self._versions = tuple(versions)
        self._fetch = fetch
        self._cancelled = Event()

    def cancel(self) -> None:
        """Stop starting new image requests after the family closes."""

        self._cancelled.set()

    def run(self) -> None:
        """Settle each thumbnail independently and always publish completion."""

        try:
            for version in self._versions:
                if self._cancelled.is_set():
                    break
                url = version.thumbnail_url
                if url is None:
                    self.signals.failed.emit(version.version_id)
                    continue
                try:
                    payload = self._fetch(url)
                except (OSError, TimeoutError, ValueError, RuntimeError) as error:
                    _LOGGER.warning(
                        "Model version preview unavailable: model=%s version=%s reason=%s",
                        version.model_id,
                        version.version_id,
                        type(error).__name__,
                    )
                    self.signals.failed.emit(version.version_id)
                except Exception:
                    _LOGGER.exception(
                        "Unexpected model version preview failure: model=%s version=%s",
                        version.model_id,
                        version.version_id,
                    )
                    self.signals.failed.emit(version.version_id)
                else:
                    self.signals.loaded.emit(version.version_id, payload)
        finally:
            self.signals.finished.emit()


__all__ = ["VersionThumbnailLoad", "VersionThumbnailSignals"]
