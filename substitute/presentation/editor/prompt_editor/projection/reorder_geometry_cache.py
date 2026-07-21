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

"""Define prompt-safe cache keys for projection-owned reorder geometry."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import (
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
)

from .reorder_preview import PromptReorderProjectionSnapshot
from .observability import log_reorder_drag_event
from .reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometrySnapshot,
)
from .reorder_placement_geometry import PromptReorderPlacementSnapshot


_DEFAULT_PREVIEW_CHIP_GEOMETRY_CACHE_LIMIT = 16


@dataclass(frozen=True, slots=True)
class PromptReorderGeometryViewportKey:
    """Identify viewport-local inputs that affect reorder geometry positions."""

    viewport_left: int
    viewport_top: int
    viewport_width: int
    viewport_height: int
    scroll_offset: int
    layout_width_x100: int


@dataclass(frozen=True, slots=True)
class PromptReorderSnapshotGeometryKey:
    """Identify semantic snapshot inputs that affect reorder geometry."""

    text: str
    chip_rendered_ranges: tuple[tuple[int, int, int], ...]
    chip_owned_ranges: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    gap_ranges: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderLayoutGeometryKey:
    """Identify one reorder layout plus its projection layout instance."""

    projection_layout_identity: int
    rows: tuple[tuple[int, tuple[int, ...]], ...]
    gaps: tuple[tuple[int, int, str, str], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderChipGeometryCacheKey:
    """Identify a chip geometry snapshot cache entry."""

    snapshot: PromptReorderSnapshotGeometryKey
    layout: PromptReorderLayoutGeometryKey
    viewport: PromptReorderGeometryViewportKey


@dataclass(frozen=True, slots=True)
class PromptReorderPlacementGeometryCacheKey:
    """Identify a placement geometry snapshot cache entry."""

    snapshot: PromptReorderSnapshotGeometryKey
    layout: PromptReorderLayoutGeometryKey
    viewport: PromptReorderGeometryViewportKey


ReorderGeometrySnapshot = PromptReorderProjectionSnapshot | PromptReorderPreviewSnapshot


class PromptReorderGeometryCache:
    """Own reorder geometry cache entries, keys, counters, and invalidation."""

    def __init__(
        self,
        *,
        preview_chip_cache_limit: int = _DEFAULT_PREVIEW_CHIP_GEOMETRY_CACHE_LIMIT,
    ) -> None:
        """Initialize empty reorder geometry caches with bounded LRU capacity."""

        self._preview_chip_cache_limit = preview_chip_cache_limit
        self._live_chip_geometry_cache_key: PromptReorderChipGeometryCacheKey | None = (
            None
        )
        self._live_chip_geometry_cache: PromptReorderChipGeometrySnapshot | None = None
        self._base_drag_chip_geometry_cache_key: (
            PromptReorderChipGeometryCacheKey | None
        ) = None
        self._base_drag_chip_geometry_cache: (
            PromptReorderChipGeometrySnapshot | None
        ) = None
        self._base_drag_placement_cache_key: (
            PromptReorderPlacementGeometryCacheKey | None
        ) = None
        self._base_drag_placement_cache: PromptReorderPlacementSnapshot | None = None
        self._preview_chip_geometry_cache: OrderedDict[
            PromptReorderChipGeometryCacheKey,
            PromptReorderChipGeometrySnapshot,
        ] = OrderedDict()
        self.reset_counters()

    def reset_counters(self) -> None:
        """Reset per-gesture reorder geometry cache counters."""

        self._base_drag_chip_geometry_cache_hit_count = 0
        self._base_drag_chip_geometry_cache_miss_count = 0
        self._base_drag_chip_geometry_preview_reuse_count = 0
        self._base_drag_placement_cache_hit_count = 0
        self._base_drag_placement_cache_miss_count = 0
        self._preview_chip_geometry_cache_hit_count = 0
        self._preview_chip_geometry_cache_miss_count = 0
        self._preview_chip_geometry_live_reuse_count = 0
        self._preview_chip_geometry_reused_chip_count = 0
        self._preview_chip_geometry_rebuilt_chip_count = 0
        self._preview_chip_geometry_reuse_rejected_count = 0
        self._scroll_translated_chip_geometry_count = 0
        self._scroll_rebuilt_chip_geometry_count = 0
        self._live_chip_geometry_cache_hit_count = 0
        self._live_chip_geometry_cache_miss_count = 0
        self._max_base_drag_chip_geometry_ms = 0.0
        self._max_base_drag_placement_ms = 0.0
        self._max_preview_chip_geometry_ms = 0.0

    def counters(self) -> dict[str, object]:
        """Return per-gesture reorder cache counters for diagnostics summaries."""

        return {
            "base_chip_geometry_cache_hit_count": (
                self._base_drag_chip_geometry_cache_hit_count
            ),
            "base_chip_geometry_cache_miss_count": (
                self._base_drag_chip_geometry_cache_miss_count
            ),
            "base_chip_geometry_preview_reuse_count": (
                self._base_drag_chip_geometry_preview_reuse_count
            ),
            "base_placement_cache_hit_count": (
                self._base_drag_placement_cache_hit_count
            ),
            "base_placement_cache_miss_count": (
                self._base_drag_placement_cache_miss_count
            ),
            "preview_chip_geometry_cache_hit_count": (
                self._preview_chip_geometry_cache_hit_count
            ),
            "preview_chip_geometry_cache_miss_count": (
                self._preview_chip_geometry_cache_miss_count
            ),
            "preview_chip_geometry_live_reuse_count": (
                self._preview_chip_geometry_live_reuse_count
            ),
            "preview_chip_geometry_reused_chip_count": (
                self._preview_chip_geometry_reused_chip_count
            ),
            "preview_chip_geometry_rebuilt_chip_count": (
                self._preview_chip_geometry_rebuilt_chip_count
            ),
            "preview_chip_geometry_reuse_rejected_count": (
                self._preview_chip_geometry_reuse_rejected_count
            ),
            "scroll_translated_chip_geometry_count": (
                self._scroll_translated_chip_geometry_count
            ),
            "scroll_rebuilt_chip_geometry_count": (
                self._scroll_rebuilt_chip_geometry_count
            ),
            "live_chip_geometry_cache_hit_count": (
                self._live_chip_geometry_cache_hit_count
            ),
            "live_chip_geometry_cache_miss_count": (
                self._live_chip_geometry_cache_miss_count
            ),
            "max_base_chip_geometry_ms": (
                f"{self._max_base_drag_chip_geometry_ms:.3f}"
            ),
            "max_base_placement_ms": f"{self._max_base_drag_placement_ms:.3f}",
            "max_preview_chip_geometry_ms": (
                f"{self._max_preview_chip_geometry_ms:.3f}"
            ),
        }

    def clear_base_drag_geometry_caches(self, *, reason: str) -> None:
        """Invalidate stable drag-base chip and placement geometry caches."""

        had_chip_cache = self._base_drag_chip_geometry_cache is not None
        had_placement_cache = self._base_drag_placement_cache is not None
        self._base_drag_chip_geometry_cache_key = None
        self._base_drag_chip_geometry_cache = None
        self._base_drag_placement_cache_key = None
        self._base_drag_placement_cache = None
        if had_chip_cache:
            log_reorder_drag_event(
                "cache.base_drag_chip_geometry.invalidate",
                reason=reason,
            )
        if had_placement_cache:
            log_reorder_drag_event(
                "cache.base_drag_placement.invalidate",
                reason=reason,
            )

    def clear_live_chip_geometry_cache(self, *, reason: str) -> None:
        """Invalidate stable live chip geometry after layout-affecting changes."""

        had_cache = self._live_chip_geometry_cache is not None
        self._live_chip_geometry_cache_key = None
        self._live_chip_geometry_cache = None
        if had_cache:
            log_reorder_drag_event(
                "cache.live_chip_geometry.invalidate",
                reason=reason,
            )

    def clear_preview_chip_geometry_cache(self, *, reason: str) -> None:
        """Invalidate cached preview chip geometry snapshots."""

        cache_size = len(self._preview_chip_geometry_cache)
        self._preview_chip_geometry_cache.clear()
        if cache_size:
            log_reorder_drag_event(
                "cache.preview_chip_geometry.invalidate",
                reason=reason,
                cache_size=cache_size,
            )

    def clear_all(self, *, reason: str) -> None:
        """Invalidate all reorder geometry caches."""

        self.clear_live_chip_geometry_cache(reason=reason)
        self.clear_base_drag_geometry_caches(reason=reason)
        self.clear_preview_chip_geometry_cache(reason=reason)

    def chip_geometry_cache_key(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
        projection_layout_identity: int,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_width: float,
    ) -> PromptReorderChipGeometryCacheKey:
        """Return the full identity for a reorder chip geometry snapshot."""

        return PromptReorderChipGeometryCacheKey(
            snapshot=reorder_chip_snapshot_geometry_key(snapshot),
            layout=reorder_layout_geometry_key(
                layout_view,
                projection_layout_identity=projection_layout_identity,
            ),
            viewport=reorder_geometry_viewport_key(
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
                layout_width=layout_width,
            ),
        )

    def live_chip_geometry_cache_key(
        self,
        *,
        source_text: str,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        layout_view: PromptReorderLayoutView,
        projection_layout_identity: int,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_width: float,
    ) -> PromptReorderChipGeometryCacheKey:
        """Return the full identity for stable live projection chip geometry."""

        snapshot_key = reorder_chip_snapshot_geometry_key_from_parts(
            source_text=source_text,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )
        return PromptReorderChipGeometryCacheKey(
            snapshot=snapshot_key,
            layout=reorder_layout_geometry_key(
                layout_view,
                projection_layout_identity=projection_layout_identity,
            ),
            viewport=reorder_geometry_viewport_key(
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
                layout_width=layout_width,
            ),
        )

    def live_chip_snapshot(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> PromptReorderChipGeometrySnapshot | None:
        """Return stable live chip geometry for one exact viewport identity."""

        if (
            self._live_chip_geometry_cache_key == key
            and self._live_chip_geometry_cache is not None
        ):
            self._live_chip_geometry_cache_hit_count += 1
            return self._live_chip_geometry_cache
        self._live_chip_geometry_cache_miss_count += 1
        return None

    def live_chip_scroll_candidate(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> (
        tuple[PromptReorderChipGeometryCacheKey, PromptReorderChipGeometrySnapshot]
        | None
    ):
        """Return live geometry when only the scroll offset changed."""

        cached_key = self._live_chip_geometry_cache_key
        cached_snapshot = self._live_chip_geometry_cache
        if (
            cached_key is None
            or cached_snapshot is None
            or not _same_geometry_inputs_except_scroll(cached_key, key)
        ):
            return None
        return cached_key, cached_snapshot

    def remember_live_chip_snapshot(
        self,
        *,
        key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> None:
        """Store the newest live chip geometry snapshot."""

        self._live_chip_geometry_cache_key = key
        self._live_chip_geometry_cache = snapshot

    def placement_geometry_cache_key(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
        projection_layout_identity: int,
        viewport_rect: QRectF,
        scroll_offset: float,
        layout_width: float,
    ) -> PromptReorderPlacementGeometryCacheKey:
        """Return the full identity for a reorder placement snapshot."""

        return PromptReorderPlacementGeometryCacheKey(
            snapshot=reorder_snapshot_geometry_key(snapshot),
            layout=reorder_layout_geometry_key(
                layout_view,
                projection_layout_identity=projection_layout_identity,
            ),
            viewport=reorder_geometry_viewport_key(
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
                layout_width=layout_width,
            ),
        )

    def context(
        self,
        key: PromptReorderChipGeometryCacheKey | PromptReorderPlacementGeometryCacheKey,
    ) -> dict[str, object]:
        """Return prompt-safe diagnostics for one reorder geometry cache key."""

        return reorder_geometry_cache_context(
            snapshot_key=key.snapshot,
            layout_key=key.layout,
            viewport_key=key.viewport,
        )

    def preview_chip_snapshot(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> PromptReorderChipGeometrySnapshot | None:
        """Return and refresh one cached preview chip geometry snapshot."""

        cached_snapshot = self._preview_chip_geometry_cache.get(key)
        if (
            cached_snapshot is None
            and self._live_chip_geometry_cache_key == key
            and self._live_chip_geometry_cache is not None
        ):
            cached_snapshot = self._live_chip_geometry_cache
            self._preview_chip_geometry_live_reuse_count += 1
        if cached_snapshot is None:
            self._preview_chip_geometry_cache_miss_count += 1
            return None
        self._preview_chip_geometry_cache_hit_count += 1
        self._preview_chip_geometry_reused_chip_count += len(
            cached_snapshot.geometries_by_chip_index
        )
        if key in self._preview_chip_geometry_cache:
            self._preview_chip_geometry_cache.move_to_end(key)
        return cached_snapshot

    def preview_chip_scroll_candidate(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> (
        tuple[PromptReorderChipGeometryCacheKey, PromptReorderChipGeometrySnapshot]
        | None
    ):
        """Return the newest matching preview geometry from another scroll offset."""

        for cached_key in reversed(self._preview_chip_geometry_cache):
            if _same_geometry_inputs_except_scroll(cached_key, key):
                return cached_key, self._preview_chip_geometry_cache[cached_key]
        return None

    def remember_preview_chip_snapshot(
        self,
        *,
        key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> None:
        """Store one preview chip snapshot and evict oldest entries if needed."""

        self._preview_chip_geometry_cache[key] = snapshot
        self._preview_chip_geometry_cache.move_to_end(key)
        while len(self._preview_chip_geometry_cache) > self._preview_chip_cache_limit:
            self._preview_chip_geometry_cache.popitem(last=False)
            log_reorder_drag_event(
                "cache.preview_chip_geometry.invalidate",
                reason="evict_lru",
                cache_size=len(self._preview_chip_geometry_cache),
            )

    def reuse_preview_chip_geometry_snapshot(
        self,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> tuple[PromptReorderChipGeometrySnapshot, int, int, int]:
        """Reuse immutable chip geometries from recent preview snapshots when equal."""

        if not self._preview_chip_geometry_cache:
            rebuilt_count = len(snapshot.geometries_by_chip_index)
            self._preview_chip_geometry_rebuilt_chip_count += rebuilt_count
            return snapshot, 0, rebuilt_count, 0
        reused_geometries: dict[int, PromptReorderChipGeometry] = {}
        reused_count = 0
        rebuilt_count = 0
        rejected_count = 0
        previous_geometries = [
            cached_geometry
            for cached_snapshot in reversed(self._preview_chip_geometry_cache.values())
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
        self._preview_chip_geometry_reused_chip_count += reused_count
        self._preview_chip_geometry_rebuilt_chip_count += rebuilt_count
        self._preview_chip_geometry_reuse_rejected_count += rejected_count
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

    def base_drag_chip_snapshot(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> PromptReorderChipGeometrySnapshot | None:
        """Return the stable base-drag chip snapshot for a matching cache key."""

        if (
            self._base_drag_chip_geometry_cache_key == key
            and self._base_drag_chip_geometry_cache is not None
        ):
            self._base_drag_chip_geometry_cache_hit_count += 1
            return self._base_drag_chip_geometry_cache
        preview_snapshot = self._preview_chip_geometry_cache.get(key)
        if preview_snapshot is not None:
            self._base_drag_chip_geometry_cache_key = key
            self._base_drag_chip_geometry_cache = preview_snapshot
            self._base_drag_chip_geometry_cache_hit_count += 1
            self._base_drag_chip_geometry_preview_reuse_count += 1
            return preview_snapshot
        self._base_drag_chip_geometry_cache_miss_count += 1
        return None

    def base_drag_chip_scroll_candidate(
        self,
        key: PromptReorderChipGeometryCacheKey,
    ) -> (
        tuple[PromptReorderChipGeometryCacheKey, PromptReorderChipGeometrySnapshot]
        | None
    ):
        """Return stable base geometry when only the scroll offset changed."""

        cached_key = self._base_drag_chip_geometry_cache_key
        cached_snapshot = self._base_drag_chip_geometry_cache
        if (
            cached_key is None
            or cached_snapshot is None
            or not _same_geometry_inputs_except_scroll(cached_key, key)
        ):
            return None
        return cached_key, cached_snapshot

    def record_scroll_geometry_reuse(
        self,
        *,
        translated_chip_count: int,
        rebuilt_chip_count: int,
    ) -> None:
        """Record bounded scroll-translation work for abuse diagnostics."""

        self._scroll_translated_chip_geometry_count += translated_chip_count
        self._scroll_rebuilt_chip_geometry_count += rebuilt_chip_count

    def remember_base_drag_chip_snapshot(
        self,
        *,
        key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> None:
        """Store one stable base-drag chip snapshot."""

        self._base_drag_chip_geometry_cache_key = key
        self._base_drag_chip_geometry_cache = snapshot

    def base_drag_placement_snapshot(
        self,
        key: PromptReorderPlacementGeometryCacheKey,
    ) -> PromptReorderPlacementSnapshot | None:
        """Return the stable base-drag placement snapshot for a matching cache key."""

        if (
            self._base_drag_placement_cache_key == key
            and self._base_drag_placement_cache is not None
        ):
            self._base_drag_placement_cache_hit_count += 1
            return self._base_drag_placement_cache
        self._base_drag_placement_cache_miss_count += 1
        return None

    def remember_base_drag_placement_snapshot(
        self,
        *,
        key: PromptReorderPlacementGeometryCacheKey,
        snapshot: PromptReorderPlacementSnapshot,
    ) -> None:
        """Store one stable base-drag placement snapshot."""

        self._base_drag_placement_cache_key = key
        self._base_drag_placement_cache = snapshot

    def record_base_drag_chip_elapsed(self, elapsed_ms: float) -> None:
        """Record the maximum base-drag chip geometry build duration."""

        self._max_base_drag_chip_geometry_ms = max(
            self._max_base_drag_chip_geometry_ms,
            elapsed_ms,
        )

    def record_base_drag_placement_elapsed(self, elapsed_ms: float) -> None:
        """Record the maximum base-drag placement geometry build duration."""

        self._max_base_drag_placement_ms = max(
            self._max_base_drag_placement_ms,
            elapsed_ms,
        )

    def record_preview_chip_elapsed(self, elapsed_ms: float) -> None:
        """Record the maximum preview chip geometry build duration."""

        self._max_preview_chip_geometry_ms = max(
            self._max_preview_chip_geometry_ms,
            elapsed_ms,
        )


def reorder_geometry_viewport_key(
    *,
    viewport_rect: QRectF,
    scroll_offset: float,
    layout_width: float,
) -> PromptReorderGeometryViewportKey:
    """Return a stable viewport cache key using rounded device-independent values."""

    return PromptReorderGeometryViewportKey(
        viewport_left=int(round(viewport_rect.left())),
        viewport_top=int(round(viewport_rect.top())),
        viewport_width=int(round(viewport_rect.width())),
        viewport_height=int(round(viewport_rect.height())),
        scroll_offset=int(round(scroll_offset)),
        layout_width_x100=int(round(layout_width * 100.0)),
    )


def reorder_geometry_viewport_rect(
    viewport_key: PromptReorderGeometryViewportKey,
) -> QRectF:
    """Restore the viewport rectangle represented by one geometry cache key."""

    return QRectF(
        viewport_key.viewport_left,
        viewport_key.viewport_top,
        viewport_key.viewport_width,
        viewport_key.viewport_height,
    )


def _same_geometry_inputs_except_scroll(
    first: PromptReorderChipGeometryCacheKey,
    second: PromptReorderChipGeometryCacheKey,
) -> bool:
    """Return whether two chip keys differ only by vertical scroll offset."""

    first_viewport = first.viewport
    second_viewport = second.viewport
    return (
        first.snapshot == second.snapshot
        and first.layout == second.layout
        and first_viewport.viewport_left == second_viewport.viewport_left
        and first_viewport.viewport_top == second_viewport.viewport_top
        and first_viewport.viewport_width == second_viewport.viewport_width
        and first_viewport.viewport_height == second_viewport.viewport_height
        and first_viewport.layout_width_x100 == second_viewport.layout_width_x100
        and first_viewport.scroll_offset != second_viewport.scroll_offset
    )


def reorder_snapshot_geometry_key(
    snapshot: ReorderGeometrySnapshot,
) -> PromptReorderSnapshotGeometryKey:
    """Return a semantic cache key for either application or projection snapshots."""

    return PromptReorderSnapshotGeometryKey(
        text=_snapshot_text(snapshot),
        chip_rendered_ranges=tuple(
            sorted(
                (
                    chip_index,
                    range_start,
                    range_end,
                )
                for chip_index, (
                    range_start,
                    range_end,
                ) in snapshot.chip_rendered_ranges_by_index.items()
            )
        ),
        chip_owned_ranges=tuple(
            sorted(
                (
                    chip_index,
                    tuple(sorted(owned_ranges)),
                )
                for chip_index, owned_ranges in snapshot.chip_owned_ranges_by_index.items()
            )
        ),
        gap_ranges=_sorted_ranges(snapshot.gap_ranges_by_index),
    )


def reorder_chip_snapshot_geometry_key(
    snapshot: ReorderGeometrySnapshot,
) -> PromptReorderSnapshotGeometryKey:
    """Return only snapshot inputs that affect chip geometry."""

    return reorder_chip_snapshot_geometry_key_from_parts(
        source_text=_snapshot_text(snapshot),
        chip_rendered_ranges_by_index=snapshot.chip_rendered_ranges_by_index,
        chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
    )


def reorder_chip_snapshot_geometry_key_from_parts(
    *,
    source_text: str,
    chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
    chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
) -> PromptReorderSnapshotGeometryKey:
    """Return chip geometry identity without unrelated placement gap ranges."""

    return PromptReorderSnapshotGeometryKey(
        text=source_text,
        chip_rendered_ranges=tuple(
            sorted(
                (chip_index, range_start, range_end)
                for chip_index, (
                    range_start,
                    range_end,
                ) in chip_rendered_ranges_by_index.items()
            )
        ),
        chip_owned_ranges=tuple(
            sorted(
                (chip_index, tuple(sorted(owned_ranges)))
                for chip_index, owned_ranges in chip_owned_ranges_by_index.items()
            )
        ),
        gap_ranges=(),
    )


def reorder_layout_geometry_key(
    layout_view: PromptReorderLayoutView,
    *,
    projection_layout_identity: int,
) -> PromptReorderLayoutGeometryKey:
    """Return a cache key for a layout view and its visual projection owner."""

    return PromptReorderLayoutGeometryKey(
        projection_layout_identity=projection_layout_identity,
        rows=tuple(
            (row.row_index, tuple(row.chip_indices)) for row in layout_view.rows
        ),
        gaps=tuple(
            (
                gap.gap_index,
                gap.blank_line_count,
                gap.placement.value,
                gap.separator_text,
            )
            for gap in layout_view.gaps
        ),
    )


def reorder_geometry_cache_context(
    *,
    snapshot_key: PromptReorderSnapshotGeometryKey,
    layout_key: PromptReorderLayoutGeometryKey,
    viewport_key: PromptReorderGeometryViewportKey,
    prefix: str = "geometry_cache",
) -> dict[str, object]:
    """Return prompt-content-safe diagnostic fields for a geometry cache key."""

    return {
        f"{prefix}_text_length": len(snapshot_key.text),
        f"{prefix}_snapshot_hash": _safe_key_hash(snapshot_key),
        f"{prefix}_chip_range_count": len(snapshot_key.chip_rendered_ranges),
        f"{prefix}_owned_range_count": len(snapshot_key.chip_owned_ranges),
        f"{prefix}_gap_range_count": len(snapshot_key.gap_ranges),
        f"{prefix}_layout_hash": _safe_key_hash(layout_key),
        f"{prefix}_row_count": len(layout_key.rows),
        f"{prefix}_gap_count": len(layout_key.gaps),
        f"{prefix}_viewport_width": viewport_key.viewport_width,
        f"{prefix}_viewport_height": viewport_key.viewport_height,
        f"{prefix}_scroll_offset": viewport_key.scroll_offset,
        f"{prefix}_layout_width_x100": viewport_key.layout_width_x100,
    }


def chip_geometry_visual_reuse_key(
    geometry: PromptReorderChipGeometry,
) -> tuple[object, ...]:
    """Return the strict geometry identity required for per-chip visual reuse."""

    return (
        geometry.chip_index,
        geometry.source_start,
        geometry.source_end,
        geometry.rendered_start,
        geometry.rendered_end,
        geometry.geometry_id.visual_revision,
        geometry.hotspot_rect.left(),
        geometry.hotspot_rect.top(),
        geometry.hotspot_rect.width(),
        geometry.hotspot_rect.height(),
        round(geometry.outline_bounds.left(), 3),
        round(geometry.outline_bounds.top(), 3),
        round(geometry.outline_bounds.width(), 3),
        round(geometry.outline_bounds.height(), 3),
        tuple(
            (
                line.visual_line_index,
                round(line.content_rect.left(), 3),
                round(line.content_rect.top(), 3),
                round(line.content_rect.width(), 3),
                round(line.content_rect.height(), 3),
                round(line.leading_anchor.x(), 3),
                round(line.leading_anchor.y(), 3),
                round(line.trailing_anchor.x(), 3),
                round(line.trailing_anchor.y(), 3),
            )
            for line in geometry.visual_lines
        ),
    )


def _snapshot_text(snapshot: ReorderGeometrySnapshot) -> str:
    """Return source text from either snapshot representation."""

    if isinstance(snapshot, PromptReorderProjectionSnapshot):
        return snapshot.document_view.source_text
    return snapshot.text


def _sorted_ranges(
    ranges_by_index: Mapping[int, tuple[int, int]],
) -> tuple[tuple[int, int, int], ...]:
    """Return deterministic range tuples suitable for cache keys."""

    return tuple(
        sorted(
            (range_index, range_start, range_end)
            for range_index, (
                range_start,
                range_end,
            ) in ranges_by_index.items()
        )
    )


def _safe_key_hash(key: object) -> str:
    """Return a compact diagnostic hash without logging prompt text."""

    return hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]


__all__ = [
    "PromptReorderChipGeometryCacheKey",
    "PromptReorderGeometryCache",
    "PromptReorderGeometryViewportKey",
    "PromptReorderLayoutGeometryKey",
    "PromptReorderPlacementGeometryCacheKey",
    "PromptReorderSnapshotGeometryKey",
    "ReorderGeometrySnapshot",
    "chip_geometry_visual_reuse_key",
    "reorder_geometry_cache_context",
    "reorder_geometry_viewport_key",
    "reorder_geometry_viewport_rect",
    "reorder_layout_geometry_key",
    "reorder_snapshot_geometry_key",
]
