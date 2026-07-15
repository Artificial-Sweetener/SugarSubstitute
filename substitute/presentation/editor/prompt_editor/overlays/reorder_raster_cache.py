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

"""Rasterize complete reorder chips for frame-time pixmap blitting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap

from ..projection.reorder_visual_snapshot import (
    PromptReorderInlineObjectPaintFragment,
    PromptReorderTextPaintFragment,
    paint_reorder_projection_snapshot,
)
from .chip_painter import PromptChipPaintStyle, PromptChipPainter
from .reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
    translated_snapshot_offset,
)

_RASTER_PADDING = 3.0


@dataclass(frozen=True, slots=True)
class ReorderRasterStyleKey:
    """Identify chrome style inputs that affect the chip pixmap."""

    fill_rgba: int
    border_rgba: int
    outline_only: bool
    outline_width: float
    opacity: float


@dataclass(frozen=True, slots=True)
class ReorderRasterKey:
    """Identify a complete chip pixmap against content, style, and DPR."""

    content_key: object
    device_pixel_ratio: float
    style_key: ReorderRasterStyleKey


@dataclass(frozen=True, slots=True)
class ReorderRasterEntry:
    """Carry one complete-chip pixmap and the geometry needed to draw it."""

    key: ReorderRasterKey
    segment_index: int
    pixmap: QPixmap
    logical_rect: QRectF
    raster_rect: QRectF
    source_ranges: tuple[tuple[int, int], ...]
    suppression_eligible: bool

    def top_left_for_rect(self, rect: QRectF) -> QPointF:
        """Return the pixmap top-left needed to align it to a logical chip rect."""

        return QPointF(
            rect.left() - (self.logical_rect.left() - self.raster_rect.left()),
            rect.top() - (self.logical_rect.top() - self.raster_rect.top()),
        )


@dataclass(frozen=True, slots=True)
class ReorderRasterCacheCounters:
    """Summarize complete-chip raster cache activity."""

    hit_count: int = 0
    miss_count: int = 0
    stale_count: int = 0
    store_count: int = 0
    clear_count: int = 0
    build_count: int = 0
    build_elapsed_ms_max: float = 0.0
    build_failed_count: int = 0

    def as_dict(self) -> dict[str, int | float]:
        """Return JSON-safe counters for tests and diagnostics."""

        return {
            "raster_cache_hit_count": self.hit_count,
            "raster_cache_miss_count": self.miss_count,
            "raster_cache_stale_count": self.stale_count,
            "raster_cache_store_count": self.store_count,
            "raster_cache_clear_count": self.clear_count,
            "raster_build_count": self.build_count,
            "raster_build_elapsed_ms_max": self.build_elapsed_ms_max,
            "raster_build_failed_count": self.build_failed_count,
        }


class PromptReorderRasterCache:
    """Store DPR-aware complete-chip pixmaps for one reorder interaction."""

    def __init__(self) -> None:
        """Initialize an empty reorder raster cache."""

        self._entries_by_index: dict[int, ReorderRasterEntry] = {}
        self._chip_painter = PromptChipPainter()
        self._hit_count = 0
        self._miss_count = 0
        self._stale_count = 0
        self._store_count = 0
        self._clear_count = 0
        self._build_count = 0
        self._build_elapsed_ms_max = 0.0
        self._build_failed_count = 0

    def clear(self) -> None:
        """Clear all pixmaps and count the invalidation."""

        if self._entries_by_index:
            self._clear_count += 1
        self._entries_by_index.clear()

    def entries_for_snapshots(
        self,
        *,
        snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot],
        styles_by_index: Mapping[int, PromptChipPaintStyle],
        device_pixel_ratio: float,
    ) -> dict[int, ReorderRasterEntry]:
        """Return fresh raster entries, building missing entries off the frame path."""

        entries: dict[int, ReorderRasterEntry] = {}
        for segment_index, snapshot in snapshots_by_index.items():
            style = styles_by_index.get(segment_index)
            if style is None:
                continue
            key = self._key_for_snapshot(
                snapshot=snapshot,
                style=style,
                device_pixel_ratio=device_pixel_ratio,
            )
            existing = self._entries_by_index.get(segment_index)
            if existing is not None and existing.key == key:
                self._hit_count += 1
                entries[segment_index] = existing
                continue
            if existing is None:
                self._miss_count += 1
            else:
                self._stale_count += 1
            entry = self._build_entry(
                segment_index=segment_index,
                snapshot=snapshot,
                style=style,
                key=key,
            )
            if entry is None:
                continue
            self._entries_by_index[segment_index] = entry
            self._store_count += 1
            entries[segment_index] = entry
        return entries

    def counters(self) -> ReorderRasterCacheCounters:
        """Return current cache counters."""

        return ReorderRasterCacheCounters(
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            stale_count=self._stale_count,
            store_count=self._store_count,
            clear_count=self._clear_count,
            build_count=self._build_count,
            build_elapsed_ms_max=self._build_elapsed_ms_max,
            build_failed_count=self._build_failed_count,
        )

    def _build_entry(
        self,
        *,
        segment_index: int,
        snapshot: PromptReorderChipVisualSnapshot,
        style: PromptChipPaintStyle,
        key: ReorderRasterKey,
    ) -> ReorderRasterEntry | None:
        """Rasterize one complete chip into a transparent pixmap."""

        started_at = time.perf_counter()
        try:
            logical_rect = QRectF(snapshot.visual.hotspot_rect)
            raster_rect = QRectF(logical_rect)
            raster_rect.adjust(
                -_RASTER_PADDING,
                -_RASTER_PADDING,
                _RASTER_PADDING,
                _RASTER_PADDING,
            )
            dpr = max(key.device_pixel_ratio, 1.0)
            pixmap_size = QSize(
                max(1, int(round(raster_rect.width() * dpr))),
                max(1, int(round(raster_rect.height() * dpr))),
            )
            pixmap = QPixmap(pixmap_size)
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.translate(-raster_rect.left(), -raster_rect.top())
                self._chip_painter.paint_chrome(
                    painter=painter,
                    visual=snapshot.visual,
                    style=style,
                )
                dx, dy = translated_snapshot_offset(
                    painted_rect=logical_rect,
                    snapshot=snapshot,
                )
                painter.translate(dx, dy)
                paint_reorder_projection_snapshot(
                    painter,
                    snapshot.projection_snapshot,
                )
            finally:
                painter.end()
        except Exception:
            self._build_failed_count += 1
            return None
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        self._build_elapsed_ms_max = max(self._build_elapsed_ms_max, elapsed_ms)
        self._build_count += 1
        return ReorderRasterEntry(
            key=key,
            segment_index=segment_index,
            pixmap=pixmap,
            logical_rect=logical_rect,
            raster_rect=raster_rect,
            source_ranges=snapshot.source_ranges,
            suppression_eligible=True,
        )

    @staticmethod
    def _key_for_snapshot(
        *,
        snapshot: PromptReorderChipVisualSnapshot,
        style: PromptChipPaintStyle,
        device_pixel_ratio: float,
    ) -> ReorderRasterKey:
        """Return the cache identity for one snapshot/style/DPR tuple."""

        return ReorderRasterKey(
            content_key=_snapshot_content_key(snapshot),
            device_pixel_ratio=device_pixel_ratio,
            style_key=ReorderRasterStyleKey(
                fill_rgba=style.fill_color.rgba(),
                border_rgba=style.border_color.rgba(),
                outline_only=style.outline_only,
                outline_width=style.outline_width,
                opacity=style.opacity,
            ),
        )


def _snapshot_content_key(snapshot: PromptReorderChipVisualSnapshot) -> object:
    """Return a placement-independent identity for one complete chip pixmap."""

    visual = snapshot.visual
    origin = QPointF(visual.hotspot_rect.topLeft())
    return (
        snapshot.segment_index,
        snapshot.source_ranges,
        _rect_size_key(QRectF(visual.hotspot_rect)),
        tuple(_relative_rect_key(rect, origin=origin) for rect in visual.bubble_rects),
        _relative_rect_key(visual.fragment_union_rect, origin=origin),
        tuple(
            _fragment_content_key(fragment, origin=origin)
            for fragment in snapshot.projection_snapshot.fragments
        ),
    )


def _fragment_content_key(
    fragment: object,
    *,
    origin: QPointF,
) -> object:
    """Return a placement-independent projection fragment identity."""

    if isinstance(fragment, PromptReorderTextPaintFragment):
        return (
            "text",
            fragment.text,
            fragment.font.toString(),
            fragment.color.rgba(),
            _relative_point_key(fragment.baseline, origin=origin),
            _relative_rect_key(fragment.text_rect, origin=origin),
        )
    if isinstance(fragment, PromptReorderInlineObjectPaintFragment):
        return (
            "inline",
            _relative_rect_key(fragment.rect, origin=origin),
            repr(fragment.run),
            repr(fragment.token),
            fragment.base_font.toString(),
            int(fragment.palette.cacheKey()),
        )
    return ("unknown", repr(fragment))


def _rect_size_key(rect: QRectF) -> tuple[float, float]:
    """Return a rounded width/height identity for a rect."""

    return (_rounded(rect.width()), _rounded(rect.height()))


def _relative_rect_key(
    rect: QRectF,
    *,
    origin: QPointF,
) -> tuple[float, float, float, float]:
    """Return one rect normalized to a chip-local coordinate space."""

    return (
        _rounded(rect.left() - origin.x()),
        _rounded(rect.top() - origin.y()),
        _rounded(rect.width()),
        _rounded(rect.height()),
    )


def _relative_point_key(
    point: QPointF,
    *,
    origin: QPointF,
) -> tuple[float, float]:
    """Return one point normalized to a chip-local coordinate space."""

    return (_rounded(point.x() - origin.x()), _rounded(point.y() - origin.y()))


def _rounded(value: float) -> float:
    """Return stable cache-key precision for projection coordinates."""

    return round(float(value), 3)


__all__ = [
    "PromptReorderRasterCache",
    "ReorderRasterCacheCounters",
    "ReorderRasterEntry",
    "ReorderRasterKey",
    "ReorderRasterStyleKey",
]
