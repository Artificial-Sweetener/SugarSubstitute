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

"""Own live, preview, and base-drag prompt reorder chip caches."""

from __future__ import annotations

from collections import OrderedDict

from .observability import log_reorder_drag_event
from .reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometrySnapshot,
)
from .reorder_chip_visual_identity import chip_geometry_visual_reuse_key
from .reorder_geometry_cache_keys import (
    PromptReorderChipGeometryCacheKey,
    same_geometry_inputs_except_scroll,
)
from .reorder_geometry_metrics import PromptReorderGeometryMetrics

_DEFAULT_PREVIEW_LIMIT = 16


class PromptReorderChipGeometryCache:
    """Own bounded chip snapshot storage and cross-publication reuse."""

    def __init__(
        self,
        *,
        metrics: PromptReorderGeometryMetrics,
        preview_limit: int = _DEFAULT_PREVIEW_LIMIT,
    ) -> None:
        """Initialize one live slot, one base slot, and one bounded preview LRU."""

        self._metrics = metrics
        self._preview_limit = preview_limit
        self._live_key: PromptReorderChipGeometryCacheKey | None = None
        self._live_snapshot: PromptReorderChipGeometrySnapshot | None = None
        self._base_key: PromptReorderChipGeometryCacheKey | None = None
        self._base_snapshot: PromptReorderChipGeometrySnapshot | None = None
        self._preview: OrderedDict[
            PromptReorderChipGeometryCacheKey,
            PromptReorderChipGeometrySnapshot,
        ] = OrderedDict()

    def clear_live(self, *, reason: str) -> None:
        """Invalidate live geometry after layout-affecting changes."""

        had_cache = self._live_snapshot is not None
        self._live_key = None
        self._live_snapshot = None
        if had_cache:
            log_reorder_drag_event(
                "cache.live_chip_geometry.invalidate",
                reason=reason,
            )

    def clear_preview(self, *, reason: str) -> None:
        """Invalidate the bounded preview LRU."""

        cache_size = len(self._preview)
        self._preview.clear()
        if cache_size:
            log_reorder_drag_event(
                "cache.preview_chip_geometry.invalidate",
                reason=reason,
                cache_size=cache_size,
            )

    def clear_base_drag(self, *, reason: str) -> None:
        """Invalidate the stable base-drag chip slot."""

        had_cache = self._base_snapshot is not None
        self._base_key = None
        self._base_snapshot = None
        if had_cache:
            log_reorder_drag_event(
                "cache.base_drag_chip_geometry.invalidate",
                reason=reason,
            )

    def live(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> PromptReorderChipGeometrySnapshot | None:
        """Return live geometry for one exact identity."""

        if self._live_key == key and self._live_snapshot is not None:
            self._metrics.live_chip_hit_count += 1
            return self._live_snapshot
        self._metrics.live_chip_miss_count += 1
        return None

    def live_scroll_candidate(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> (
        tuple[
            PromptReorderChipGeometryCacheKey,
            PromptReorderChipGeometrySnapshot,
        ]
        | None
    ):
        """Return live geometry when only vertical scroll differs."""

        if (
            self._live_key is None
            or self._live_snapshot is None
            or not same_geometry_inputs_except_scroll(self._live_key, key)
        ):
            return None
        return self._live_key, self._live_snapshot

    def store_live(
        self,
        *,
        key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> None:
        """Store the newest live chip publication."""

        self._live_key = key
        self._live_snapshot = snapshot

    def preview(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> PromptReorderChipGeometrySnapshot | None:
        """Return and refresh one preview snapshot, including exact live reuse."""

        snapshot = self._preview.get(key)
        if (
            snapshot is None
            and self._live_key == key
            and self._live_snapshot is not None
        ):
            snapshot = self._live_snapshot
            self._metrics.preview_chip_live_reuse_count += 1
        if snapshot is None:
            self._metrics.preview_chip_miss_count += 1
            return None
        self._metrics.preview_chip_hit_count += 1
        self._metrics.preview_reused_chip_count += len(
            snapshot.geometries_by_chip_index
        )
        if key in self._preview:
            self._preview.move_to_end(key)
        return snapshot

    def preview_scroll_candidate(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> (
        tuple[
            PromptReorderChipGeometryCacheKey,
            PromptReorderChipGeometrySnapshot,
        ]
        | None
    ):
        """Return the newest preview differing only by vertical scroll."""

        for cached_key in reversed(self._preview):
            if same_geometry_inputs_except_scroll(cached_key, key):
                return cached_key, self._preview[cached_key]
        return None

    def store_preview(
        self,
        *,
        key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> None:
        """Store one preview snapshot and enforce the LRU bound."""

        self._preview[key] = snapshot
        self._preview.move_to_end(key)
        while len(self._preview) > self._preview_limit:
            self._preview.popitem(last=False)
            log_reorder_drag_event(
                "cache.preview_chip_geometry.invalidate",
                reason="evict_lru",
                cache_size=len(self._preview),
            )

    def reuse_preview_geometries(
        self,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> tuple[PromptReorderChipGeometrySnapshot, int, int, int]:
        """Reuse immutable chip objects from recent previews when strictly equal."""

        if not self._preview:
            rebuilt_count = len(snapshot.geometries_by_chip_index)
            self._metrics.preview_rebuilt_chip_count += rebuilt_count
            return snapshot, 0, rebuilt_count, 0
        reused_geometries: dict[int, PromptReorderChipGeometry] = {}
        reused_count = 0
        rebuilt_count = 0
        rejected_count = 0
        previous_geometries = [
            cached_geometry
            for cached_snapshot in reversed(self._preview.values())
            for cached_geometry in cached_snapshot.geometries_by_chip_index.values()
        ]
        previous_by_visual_key = {
            chip_geometry_visual_reuse_key(geometry): geometry
            for geometry in previous_geometries
        }
        for chip_index, geometry in snapshot.geometries_by_chip_index.items():
            reusable_geometry = previous_by_visual_key.get(
                chip_geometry_visual_reuse_key(geometry)
            )
            if reusable_geometry is not None:
                reused_geometries[chip_index] = reusable_geometry
                reused_count += 1
                continue
            if any(
                previous_geometry.chip_index == chip_index
                for previous_geometry in previous_geometries
            ):
                rejected_count += 1
            reused_geometries[chip_index] = geometry
            rebuilt_count += 1
        self._metrics.preview_reused_chip_count += reused_count
        self._metrics.preview_rebuilt_chip_count += rebuilt_count
        self._metrics.preview_reuse_rejected_count += rejected_count
        if reused_count == 0:
            return snapshot, 0, rebuilt_count, rejected_count
        return (
            PromptReorderChipGeometrySnapshot(
                geometries_by_chip_index=reused_geometries,
                ordered_chip_indices=snapshot.ordered_chip_indices,
                visual_line_count=snapshot.visual_line_count,
                layout_width=snapshot.layout_width,
                content_height=snapshot.content_height,
                scroll_offset=snapshot.scroll_offset,
            ),
            reused_count,
            rebuilt_count,
            rejected_count,
        )

    def base_drag(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> PromptReorderChipGeometrySnapshot | None:
        """Return stable base geometry, including exact preview reuse."""

        if self._base_key == key and self._base_snapshot is not None:
            self._metrics.base_chip_hit_count += 1
            return self._base_snapshot
        preview_snapshot = self._preview.get(key)
        if preview_snapshot is not None:
            self._base_key = key
            self._base_snapshot = preview_snapshot
            self._metrics.base_chip_hit_count += 1
            self._metrics.base_chip_preview_reuse_count += 1
            return preview_snapshot
        self._metrics.base_chip_miss_count += 1
        return None

    def base_drag_scroll_candidate(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> (
        tuple[
            PromptReorderChipGeometryCacheKey,
            PromptReorderChipGeometrySnapshot,
        ]
        | None
    ):
        """Return base geometry when only vertical scroll differs."""

        if (
            self._base_key is None
            or self._base_snapshot is None
            or not same_geometry_inputs_except_scroll(self._base_key, key)
        ):
            return None
        return self._base_key, self._base_snapshot

    def store_base_drag(
        self,
        *,
        key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> None:
        """Store one stable base-drag chip publication."""

        self._base_key = key
        self._base_snapshot = snapshot


__all__ = ["PromptReorderChipGeometryCache"]
