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

"""Paint and cache prepared prompt diagnostic underlines."""

from __future__ import annotations

from collections.abc import Callable
import math
from time import perf_counter
from typing import Final

from PySide6.QtCore import QObject, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from substitute.application.prompt_editor import PromptDiagnostic

from .layout_engine import PromptProjectionLayout
from .model import PromptProjectionSelection

_DIAGNOSTIC_WAVE_GOLDEN_RATIO = 1.61803399
_DIAGNOSTIC_WAVE_MIN_RADIUS = 1.0
_DIAGNOSTIC_WAVE_PEN_WIDTH = 1.2
_DIAGNOSTIC_WAVE_RADIUS = 2.0
_DIAGNOSTIC_WAVE_TILE_TARGET_WIDTH = 100.0
_DIAGNOSTIC_WAVE_PIXMAP_CACHE: dict[tuple[int, float, float, float], QPixmap] = {}
_DIAGNOSTIC_FRAGMENT_CACHE_LIMIT: Final[int] = 512
_DIAGNOSTIC_FRAGMENT_WARM_BUDGET_MS: Final[float] = 4.0
_DIAGNOSTIC_FRAGMENT_WARM_BATCH_LIMIT: Final[int] = 4

type DiagnosticFragmentCacheKey = tuple[
    str,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
]


class PromptDiagnosticPainter:
    """Own diagnostic underline painting and fragment geometry cache state."""

    def __init__(
        self,
        *,
        parent: QObject,
        is_alive: Callable[[], bool],
        request_update: Callable[[], None],
    ) -> None:
        """Create a budgeted diagnostic paint cache owner."""

        self._is_alive = is_alive
        self._request_update = request_update
        self._layout_revision = 0
        self._fragment_cache: dict[DiagnosticFragmentCacheKey, tuple[QRectF, ...]] = {}
        self._warm_timer = QTimer(parent)
        self._warm_timer.setSingleShot(True)
        self._warm_timer.setInterval(0)
        self._warm_timer.timeout.connect(self._warm_missing_fragments)
        self._warm_requested = False
        self._diagnostics: tuple[PromptDiagnostic, ...] = ()
        self._layout: PromptProjectionLayout | None = None
        self._source_revision = 0
        self._viewport_rect = QRectF()
        self._scroll_offset = 0.0

    @property
    def layout_revision(self) -> int:
        """Return the diagnostic layout revision used in fragment cache keys."""

        return self._layout_revision

    @property
    def fragment_cache(self) -> dict[DiagnosticFragmentCacheKey, tuple[QRectF, ...]]:
        """Return cached diagnostic fragments for tests and guardrails."""

        return self._fragment_cache

    def advance_layout_revision(self, *, reason: str) -> int:
        """Advance diagnostic geometry revision after layout-affecting changes."""

        del reason
        self._layout_revision += 1
        return self._layout_revision

    def stop_warm(self) -> None:
        """Stop pending diagnostic cache warming."""

        self._warm_timer.stop()
        self._warm_requested = False

    def paint(
        self,
        painter: QPainter,
        *,
        diagnostics: tuple[PromptDiagnostic, ...],
        selection: PromptProjectionSelection,
        layout: PromptProjectionLayout,
        preview_layout: PromptProjectionLayout | None,
        viewport_rect: QRectF,
        scroll_offset: float,
        source_revision: int,
        color: QColor,
    ) -> None:
        """Paint prepared diagnostic underline fragments."""

        if not diagnostics:
            return
        diagnostic_cache_pending_count = 0
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            for diagnostic in diagnostics:
                if not selection.is_empty and _ranges_overlap(
                    selection.start,
                    selection.end,
                    diagnostic.source_start,
                    diagnostic.source_end,
                ):
                    continue
                if preview_layout is not None:
                    for rect in preview_layout.source_range_fragments(
                        start=diagnostic.source_start,
                        end=diagnostic.source_end,
                        viewport_rect=viewport_rect,
                        scroll_offset=scroll_offset,
                    ):
                        _draw_diagnostic_wave(painter, rect=rect, color=color)
                    continue
                cache_key = _diagnostic_fragment_cache_key(
                    diagnostic=diagnostic,
                    source_revision=source_revision,
                    layout_revision=self._layout_revision,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                )
                fragments = self._fragment_cache.get(cache_key)
                if fragments is None:
                    diagnostic_cache_pending_count += 1
                    continue
                for rect in fragments:
                    _draw_diagnostic_wave(painter, rect=rect, color=color)
        finally:
            painter.restore()
        if diagnostic_cache_pending_count:
            self.schedule_warm(
                reason="paint_cache_miss",
                diagnostics=diagnostics,
                layout=layout,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
                source_revision=source_revision,
            )

    def schedule_warm(
        self,
        *,
        reason: str,
        diagnostics: tuple[PromptDiagnostic, ...],
        layout: PromptProjectionLayout,
        viewport_rect: QRectF,
        scroll_offset: float,
        source_revision: int,
    ) -> None:
        """Queue budgeted diagnostic fragment discovery outside paint events."""

        del reason
        if not self._is_alive():
            return
        if not diagnostics:
            return
        if self._warm_requested:
            return
        self._diagnostics = diagnostics
        self._layout = layout
        self._viewport_rect = QRectF(viewport_rect)
        self._scroll_offset = scroll_offset
        self._source_revision = source_revision
        self._warm_requested = True
        self._warm_timer.start(0)

    def diagnostic_fragments_for_paint(
        self,
        diagnostic: PromptDiagnostic,
        *,
        layout: PromptProjectionLayout,
        viewport_rect: QRectF,
        scroll_offset: float,
        source_revision: int,
    ) -> tuple[QRectF, ...]:
        """Return cached diagnostic underline fragments for one paint pass."""

        cache_key = _diagnostic_fragment_cache_key(
            diagnostic=diagnostic,
            source_revision=source_revision,
            layout_revision=self._layout_revision,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        cached_fragments = self._fragment_cache.get(cache_key)
        if cached_fragments is not None:
            return cached_fragments
        fragments = tuple(
            layout.source_range_fragments(
                start=diagnostic.source_start,
                end=diagnostic.source_end,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            )
        )
        if len(self._fragment_cache) >= _DIAGNOSTIC_FRAGMENT_CACHE_LIMIT:
            self.clear_fragment_cache(reason="cache_limit")
        self._fragment_cache[cache_key] = fragments
        return fragments

    def clear_fragment_cache(self, *, reason: str) -> None:
        """Discard cached diagnostic underline fragments after geometry changes."""

        del reason
        if not self._fragment_cache:
            return
        self._fragment_cache.clear()

    def preserve_fragment_cache_for_incremental_edit(
        self,
        *,
        diagnostics: tuple[PromptDiagnostic, ...],
        source_revision: int,
        start: int,
        end: int,
        replacement_text: str,
        next_layout_revision: int,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Keep unaffected diagnostic fragments after an accepted local edit."""

        if not self._fragment_cache:
            return
        delta = len(replacement_text) - (end - start)
        previous_cache = self._fragment_cache
        next_cache: dict[DiagnosticFragmentCacheKey, tuple[QRectF, ...]] = {}
        diagnostics_by_range = {
            (diagnostic.source_start, diagnostic.source_end): diagnostic
            for diagnostic in diagnostics
        }
        previous_layout_revision = next_layout_revision - 1
        for cache_key, fragments in previous_cache.items():
            (
                _diagnostic_id,
                _source_revision,
                layout_revision,
                diagnostic_start,
                diagnostic_end,
                viewport_x,
                viewport_y,
                viewport_width,
                viewport_height,
                scroll_offset,
            ) = cache_key
            if layout_revision != previous_layout_revision:
                continue
            if _diagnostic_cache_range_intersects_edit(
                diagnostic_start,
                diagnostic_end,
                start=start,
                end=end,
            ):
                continue
            remapped_start = _remap_diagnostic_cache_position_after_source_edit(
                diagnostic_start,
                start=start,
                end=end,
                delta=delta,
            )
            remapped_end = _remap_diagnostic_cache_position_after_source_edit(
                diagnostic_end,
                start=start,
                end=end,
                delta=delta,
            )
            if remapped_start is None or remapped_end is None:
                continue
            diagnostic = diagnostics_by_range.get((remapped_start, remapped_end))
            if diagnostic is None:
                continue
            preserved_fragments = _shift_diagnostic_cache_fragments_after_edit(
                fragments,
                diagnostic_start=diagnostic_start,
                edit_start=start,
                edit_end=end,
                y_delta=fragment_y_delta,
            )
            next_cache[
                (
                    diagnostic.diagnostic_id,
                    source_revision,
                    next_layout_revision,
                    diagnostic.source_start,
                    diagnostic.source_end,
                    viewport_x,
                    viewport_y,
                    viewport_width,
                    viewport_height,
                    scroll_offset,
                )
            ] = preserved_fragments
        self._fragment_cache = next_cache

    def _warm_missing_fragments(self) -> None:
        """Populate missing diagnostic fragment cache entries in small GUI chunks."""

        self._warm_requested = False
        if not self._is_alive() or not self._diagnostics or self._layout is None:
            return
        started_at = perf_counter()
        warmed_count = 0
        remaining_count = 0
        for diagnostic in self._diagnostics:
            cache_key = _diagnostic_fragment_cache_key(
                diagnostic=diagnostic,
                source_revision=self._source_revision,
                layout_revision=self._layout_revision,
                viewport_rect=self._viewport_rect,
                scroll_offset=self._scroll_offset,
            )
            if cache_key in self._fragment_cache:
                continue
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            if (
                warmed_count >= _DIAGNOSTIC_FRAGMENT_WARM_BATCH_LIMIT
                or elapsed_ms >= _DIAGNOSTIC_FRAGMENT_WARM_BUDGET_MS
            ):
                remaining_count += 1
                continue
            self.diagnostic_fragments_for_paint(
                diagnostic,
                layout=self._layout,
                viewport_rect=self._viewport_rect,
                scroll_offset=self._scroll_offset,
                source_revision=self._source_revision,
            )
            warmed_count += 1
        if warmed_count:
            self._request_update()
        if remaining_count and self._layout is not None:
            self.schedule_warm(
                reason="warm_budget",
                diagnostics=self._diagnostics,
                layout=self._layout,
                viewport_rect=self._viewport_rect,
                scroll_offset=self._scroll_offset,
                source_revision=self._source_revision,
            )


def _draw_diagnostic_wave(
    painter: QPainter,
    *,
    rect: QRectF,
    color: QColor,
) -> None:
    """Draw one diagnostic wave under a laid-out source fragment."""

    if rect.width() <= 0.0 or rect.height() <= 0.0:
        return
    device_pixel_ratio = max(1.0, float(painter.device().devicePixelRatioF()))
    tile = _diagnostic_wave_pixmap(
        color=color,
        radius=_DIAGNOSTIC_WAVE_RADIUS,
        pen_width=_DIAGNOSTIC_WAVE_PEN_WIDTH,
        device_pixel_ratio=device_pixel_ratio,
    )
    wave_height = tile.height() / device_pixel_ratio
    center_y = rect.bottom() - 2.0
    target = QRectF(
        rect.left(),
        center_y - wave_height / 2.0,
        rect.width(),
        wave_height,
    )
    painter.save()
    painter.setBrushOrigin(target.topLeft())
    painter.fillRect(target, QBrush(tile))
    painter.restore()


def _diagnostic_wave_pixmap(
    *,
    color: QColor,
    radius: float,
    pen_width: float,
    device_pixel_ratio: float,
) -> QPixmap:
    """Return a cached transparent tile for diagnostic waves."""

    normalized_radius = max(_DIAGNOSTIC_WAVE_MIN_RADIUS, radius)
    normalized_ratio = max(1.0, device_pixel_ratio)
    cache_key = (
        int(color.rgba()),
        round(normalized_radius, 2),
        round(pen_width, 2),
        round(normalized_ratio, 2),
    )
    cached = _DIAGNOSTIC_WAVE_PIXMAP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    half_period = max(
        2.0,
        normalized_radius * _DIAGNOSTIC_WAVE_GOLDEN_RATIO,
    )
    logical_width = math.ceil(
        _DIAGNOSTIC_WAVE_TILE_TARGET_WIDTH / (2.0 * half_period)
    ) * (2.0 * half_period)
    logical_height = max(
        1.0,
        normalized_radius * 2.0 + pen_width,
    )
    pixmap = QPixmap(
        max(1, math.ceil(logical_width * normalized_ratio)),
        max(1, math.ceil(logical_height * normalized_ratio)),
    )
    pixmap.setDevicePixelRatio(normalized_ratio)
    pixmap.fill(Qt.GlobalColor.transparent)

    path = _diagnostic_wave_path(
        width=logical_width,
        center_y=logical_height / 2.0,
        radius=normalized_radius,
        half_period=half_period,
    )
    wave_pen = QPen(color, pen_width)
    wave_pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    tile_painter = QPainter(pixmap)
    try:
        tile_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        tile_painter.setPen(wave_pen)
        tile_painter.setBrush(Qt.BrushStyle.NoBrush)
        tile_painter.drawPath(path)
    finally:
        tile_painter.end()

    _DIAGNOSTIC_WAVE_PIXMAP_CACHE[cache_key] = pixmap
    return pixmap


def _diagnostic_wave_path(
    *,
    width: float,
    center_y: float,
    radius: float,
    half_period: float,
) -> QPainterPath:
    """Return a smooth repeated wave path for prompt diagnostics."""

    path = QPainterPath()
    path.moveTo(0.0, center_y)
    x = 0.0
    direction = 1.0
    while x < width:
        next_x = min(width, x + half_period)
        path.quadTo(
            x + (next_x - x) / 2.0,
            center_y + radius * direction,
            next_x,
            center_y,
        )
        x = next_x
        direction *= -1.0
    return path


def _diagnostic_fragment_cache_key(
    *,
    diagnostic: PromptDiagnostic,
    source_revision: int,
    layout_revision: int,
    viewport_rect: QRectF,
    scroll_offset: float,
) -> DiagnosticFragmentCacheKey:
    """Return a stable paint-geometry cache key for one diagnostic."""

    return (
        diagnostic.diagnostic_id,
        source_revision,
        layout_revision,
        diagnostic.source_start,
        diagnostic.source_end,
        _diagnostic_cache_coordinate(viewport_rect.x()),
        _diagnostic_cache_coordinate(viewport_rect.y()),
        _diagnostic_cache_coordinate(viewport_rect.width()),
        _diagnostic_cache_coordinate(viewport_rect.height()),
        _diagnostic_cache_coordinate(scroll_offset),
    )


def _diagnostic_cache_coordinate(value: float) -> int:
    """Quantize one geometry coordinate for diagnostic fragment caching."""

    return int(round(value * 100.0))


def _remap_diagnostic_cache_position_after_source_edit(
    position: int,
    *,
    start: int,
    end: int,
    delta: int,
) -> int | None:
    """Return a diagnostic cache position shifted across a non-overlapping edit."""

    if start == end:
        if position > start:
            return position + delta
        return position
    if position >= end:
        return position + delta
    if position > start:
        return None
    return position


def _diagnostic_cache_range_intersects_edit(
    diagnostic_start: int,
    diagnostic_end: int,
    *,
    start: int,
    end: int,
) -> bool:
    """Return whether cached diagnostic geometry crosses an edited source range."""

    if start == end:
        return diagnostic_start < start < diagnostic_end
    return diagnostic_start < end and diagnostic_end > start


def _shift_diagnostic_cache_fragments_after_edit(
    fragments: tuple[QRectF, ...],
    *,
    diagnostic_start: int,
    edit_start: int,
    edit_end: int,
    y_delta: float,
) -> tuple[QRectF, ...]:
    """Return cached diagnostic fragments shifted after a hard-line source edit."""

    if y_delta == 0.0:
        return fragments
    downstream_boundary = edit_start if edit_start == edit_end else edit_end
    if diagnostic_start < downstream_boundary:
        return fragments
    return tuple(rect.translated(0.0, y_delta) for rect in fragments)


def _ranges_overlap(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> bool:
    """Return whether two half-open source ranges overlap."""

    return first_start < second_end and second_start < first_end
