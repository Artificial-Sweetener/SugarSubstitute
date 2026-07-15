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

"""Cache complete reorder chip visuals for animated overlay displacement."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from ..projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
)
from .chip_visuals import PromptChipVisual


@dataclass(frozen=True, slots=True)
class PromptReorderChipVisualSnapshot:
    """Bind chip chrome geometry to projection-owned paint fragments."""

    segment_index: int
    visual: PromptChipVisual
    projection_snapshot: PromptReorderProjectionPaintSnapshot

    @property
    def key(self) -> PromptReorderProjectionSnapshotKey:
        """Return the projection identity proving this snapshot is fresh."""

        return self.projection_snapshot.key

    @property
    def source_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return source ranges represented by this complete visual snapshot."""

        return self.projection_snapshot.source_ranges


@dataclass(frozen=True, slots=True)
class PromptReorderVisualCacheCounters:
    """Summarize short-lived reorder visual cache activity."""

    hit_count: int = 0
    miss_count: int = 0
    stale_count: int = 0
    store_count: int = 0
    clear_count: int = 0

    def as_dict(self) -> dict[str, int]:
        """Return JSON-safe counters for focused diagnostics and tests."""

        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "stale_count": self.stale_count,
            "store_count": self.store_count,
            "clear_count": self.clear_count,
        }


class PromptReorderVisualSnapshotCache:
    """Store validated complete-chip snapshots for one reorder gesture."""

    def __init__(self) -> None:
        """Initialize an empty visual snapshot cache."""

        self._snapshots_by_index: dict[int, PromptReorderChipVisualSnapshot] = {}
        self._hit_count = 0
        self._miss_count = 0
        self._stale_count = 0
        self._store_count = 0
        self._clear_count = 0

    def clear(self) -> None:
        """Clear all stored visual snapshots and count the invalidation."""

        if self._snapshots_by_index:
            self._clear_count += 1
        self._snapshots_by_index.clear()

    def store_all(
        self,
        snapshots_by_index: dict[int, PromptReorderChipVisualSnapshot],
    ) -> None:
        """Replace the cached snapshots with one fresh batch."""

        self._snapshots_by_index = dict(snapshots_by_index)
        self._store_count += len(snapshots_by_index)

    def fresh_snapshots_by_index(
        self,
        expected_keys_by_index: dict[int, PromptReorderProjectionSnapshotKey],
    ) -> dict[int, PromptReorderChipVisualSnapshot]:
        """Return only snapshots whose key still matches the requested identity."""

        fresh: dict[int, PromptReorderChipVisualSnapshot] = {}
        for segment_index, expected_key in expected_keys_by_index.items():
            snapshot = self._snapshots_by_index.get(segment_index)
            if snapshot is None:
                self._miss_count += 1
                continue
            if snapshot.key != expected_key:
                self._stale_count += 1
                continue
            self._hit_count += 1
            fresh[segment_index] = snapshot
        return fresh

    def counters(self) -> PromptReorderVisualCacheCounters:
        """Return current cache counters."""

        return PromptReorderVisualCacheCounters(
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            stale_count=self._stale_count,
            store_count=self._store_count,
            clear_count=self._clear_count,
        )


def translated_snapshot_offset(
    *,
    painted_rect: QRectF,
    snapshot: PromptReorderChipVisualSnapshot,
) -> tuple[float, float]:
    """Return the translation from snapshot chrome to the current painted rect."""

    source_rect = QRectF(snapshot.visual.hotspot_rect)
    return (
        painted_rect.left() - source_rect.left(),
        painted_rect.top() - source_rect.top(),
    )


__all__ = [
    "PromptReorderChipVisualSnapshot",
    "PromptReorderVisualCacheCounters",
    "PromptReorderVisualSnapshotCache",
    "translated_snapshot_offset",
]
