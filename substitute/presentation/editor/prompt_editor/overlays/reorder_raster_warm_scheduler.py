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

"""Warm reorder chip rasters in bounded event-loop batches after interaction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer

from .chip_painter import PromptChipPaintStyle
from .reorder_raster_cache import PromptReorderRasterCache
from .reorder_visual_cache import PromptReorderChipVisualSnapshot

_RASTER_WARM_BATCH_SIZE = 8


@dataclass(frozen=True, slots=True)
class _PromptReorderRasterWarmJob:
    """Carry the latest raster inputs for one live or preview paint lane."""

    snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot]
    styles_by_index: Mapping[int, PromptChipPaintStyle]
    device_pixel_ratio: float

    @property
    def required_entry_count(self) -> int:
        """Return how many snapshots have a corresponding paint style."""

        return sum(
            segment_index in self.styles_by_index
            for segment_index in self.snapshots_by_index
        )


class PromptReorderRasterWarmScheduler:
    """Move raster preparation out of Alt and pointer-dispatch critical paths."""

    def __init__(
        self,
        *,
        parent: QObject,
        cache: PromptReorderRasterCache,
        entries_changed: Callable[[], None],
    ) -> None:
        """Create one zero-delay bounded raster batch scheduler."""

        self._cache = cache
        self._entries_changed = entries_changed
        self._jobs: dict[str, _PromptReorderRasterWarmJob] = {}
        self._last_entry_counts: dict[str, int] = {}
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._warm_next_batch)

    def request(
        self,
        name: str,
        *,
        snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot],
        styles_by_index: Mapping[int, PromptChipPaintStyle],
        device_pixel_ratio: float,
    ) -> None:
        """Schedule latest raster inputs without doing raster work inline."""

        self._jobs[name] = _PromptReorderRasterWarmJob(
            snapshots_by_index=snapshots_by_index,
            styles_by_index=styles_by_index,
            device_pixel_ratio=device_pixel_ratio,
        )
        self._last_entry_counts.setdefault(name, -1)
        if not self._timer.isActive():
            self._timer.start()

    def cancel(self, name: str) -> None:
        """Discard one obsolete live or preview warm request."""

        self._jobs.pop(name, None)
        self._last_entry_counts.pop(name, None)
        if not self._jobs:
            self._timer.stop()

    def clear(self) -> None:
        """Discard every pending warm request."""

        self._jobs.clear()
        self._last_entry_counts.clear()
        self._timer.stop()

    def _warm_next_batch(self) -> None:
        """Build one bounded batch, publish it, and yield to the event loop."""

        if not self._jobs:
            return
        name = next(iter(self._jobs))
        job = self._jobs[name]
        entries = self._cache.entries_for_snapshots(
            snapshots_by_index=job.snapshots_by_index,
            styles_by_index=job.styles_by_index,
            device_pixel_ratio=job.device_pixel_ratio,
            build_limit=_RASTER_WARM_BATCH_SIZE,
        )
        previous_entry_count = self._last_entry_counts.get(name, -1)
        complete = len(entries) >= job.required_entry_count
        stalled = len(entries) <= previous_entry_count
        if complete or stalled:
            self._jobs.pop(name, None)
            self._last_entry_counts.pop(name, None)
        else:
            self._last_entry_counts[name] = len(entries)
        if complete:
            self._entries_changed()
        if self._jobs:
            self._timer.start()


__all__ = ["PromptReorderRasterWarmScheduler"]
