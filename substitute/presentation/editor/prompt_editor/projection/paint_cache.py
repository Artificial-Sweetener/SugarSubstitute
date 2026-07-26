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

"""Cache viewport-local pixmaps for prepared prompt projection paint."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap, QRegion

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptPaintIdentity,
)

from ..debug_probe import log_prompt_editor_probe, prompt_editor_probe_enabled
from .content_selection_layer import (
    EMPTY_PROJECTION_SELECTION_LAYER,
    PromptProjectionSelectionLayer,
)
from .content_media_state import PromptProjectionContentMediaIdentity
from .paint_cache_telemetry import (
    PromptProjectionContentCacheKey,
    PromptProjectionContentCacheSnapshot,
    PromptProjectionPaintCacheTelemetry,
)
from .paint_input import PromptProjectionPaintInput
from .painter import PromptProjectionPainter


class PromptProjectionPaintCache:
    """Own selection-free projection content cache policy and pixmap rendering."""

    def __init__(self) -> None:
        """Initialize an empty projection content cache."""

        self._cache_key: PromptProjectionContentCacheKey | None = None
        self._cache_pixmap: QPixmap | None = None
        self._telemetry = PromptProjectionPaintCacheTelemetry()
        self._painter = PromptProjectionPainter()

    @property
    def cache_key(self) -> PromptProjectionContentCacheKey | None:
        """Return the currently cached projection content identity."""

        return self._cache_key

    @property
    def cache_pixmap(self) -> QPixmap | None:
        """Return the currently cached projection content pixmap."""

        return self._cache_pixmap

    @property
    def snapshot(self) -> PromptProjectionContentCacheSnapshot:
        """Return immutable diagnostic state without exposing cache mutation."""

        pixmap = self._cache_pixmap
        return self._telemetry.snapshot(
            key=self._cache_key,
            has_pixmap=pixmap is not None and not pixmap.isNull(),
        )

    def paint_direct(
        self,
        painter: QPainter,
        *,
        paint_input: PromptProjectionPaintInput,
        selection_layer: PromptProjectionSelectionLayer,
        scroll_offset: float,
        clip_rect: QRectF,
        excluded_region: QRegion | None = None,
    ) -> None:
        """Draw prepared projection content without cache lookup or mutation."""

        self._painter.draw(
            painter,
            paint_input=paint_input,
            selection_layer=selection_layer,
            scroll_offset=scroll_offset,
            clip_rect=clip_rect,
            excluded_region=excluded_region,
        )
        self._telemetry.record("direct", paint_identity=None)

    def paint_projection_content(
        self,
        painter: QPainter,
        *,
        paint_input: PromptProjectionPaintInput,
        selection_layer: PromptProjectionSelectionLayer,
        scroll_offset: float,
        clip_rect: QRectF,
        viewport_rect: QRectF,
        excluded_region: QRegion | None,
        paint_identity: PromptPaintIdentity,
        media_identity: PromptProjectionContentMediaIdentity,
        device_pixel_ratio: float,
    ) -> str:
        """Paint projection content directly or through a viewport pixmap cache."""

        probe_enabled = prompt_editor_probe_enabled()
        if probe_enabled:
            log_prompt_editor_probe(
                "projection_paint_cache.paint.begin",
                paint_input_id=id(paint_input),
                projection_document_id=id(paint_input.projection_document),
                projection_text=paint_input.projection_document.projection_text,
                selection_empty=selection_layer.is_empty,
                excluded_region_present=excluded_region is not None,
                clip_rect=repr(clip_rect),
                viewport_rect=repr(viewport_rect),
                cache_key_present=self._cache_key is not None,
            )

        if (
            not selection_layer.is_empty
            or excluded_region is not None
            or clip_rect.isEmpty()
            or viewport_rect.isEmpty()
        ):
            self._painter.draw(
                painter,
                paint_input=paint_input,
                selection_layer=selection_layer,
                scroll_offset=scroll_offset,
                clip_rect=clip_rect,
                excluded_region=excluded_region,
            )
            if probe_enabled:
                log_prompt_editor_probe(
                    "projection_paint_cache.paint.end",
                    result="bypass",
                    cache_key_present=self._cache_key is not None,
                )
            self._telemetry.record("bypass", paint_identity=paint_identity)
            return "bypass"

        style_key = paint_input.style_key
        if style_key is None:
            raise ValueError("paint cache keys require a prepared semantic palette")
        cached_key = self._cache_key
        if (
            cached_key is not None
            and cached_key.paint_identity is paint_identity
            and cached_key.style == style_key
            and cached_key.media_identity == media_identity
            and self._cache_pixmap is not None
            and not self._cache_pixmap.isNull()
        ):
            painter.drawPixmap(QPointF(0.0, 0.0), self._cache_pixmap)
            if probe_enabled:
                log_prompt_editor_probe(
                    "projection_paint_cache.paint.end",
                    result="hit",
                    cache_key=repr(cached_key),
                    cache_key_present=True,
                )
            self._telemetry.record("hit", paint_identity=paint_identity)
            return "hit"

        if _is_small_projection_content_repaint(
            clip_rect=clip_rect,
            viewport_rect=viewport_rect,
        ):
            self._painter.draw(
                painter,
                paint_input=paint_input,
                selection_layer=selection_layer,
                scroll_offset=scroll_offset,
                clip_rect=clip_rect,
                excluded_region=excluded_region,
            )
            if probe_enabled:
                log_prompt_editor_probe(
                    "projection_paint_cache.paint.end",
                    result="bypass_small_cache_miss",
                    cache_key_present=self._cache_key is not None,
                )
            self._telemetry.record(
                "bypass_small_cache_miss",
                paint_identity=paint_identity,
            )
            return "bypass_small_cache_miss"

        cache_key = PromptProjectionContentCacheKey(
            paint_identity=paint_identity,
            style=style_key,
            media_identity=media_identity,
        )
        pixmap = self.render_cache_pixmap(
            paint_input=paint_input,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            device_pixel_ratio=device_pixel_ratio,
        )
        self._cache_key = cache_key
        self._cache_pixmap = pixmap
        painter.drawPixmap(QPointF(0.0, 0.0), pixmap)
        if probe_enabled:
            log_prompt_editor_probe(
                "projection_paint_cache.paint.end",
                result="miss",
                cache_key=repr(cache_key),
                cache_key_present=True,
            )
        self._telemetry.record("miss", paint_identity=paint_identity)
        return "miss"

    def cache_key_for(
        self,
        *,
        paint_input: PromptProjectionPaintInput,
        paint_identity: PromptPaintIdentity,
        media_identity: PromptProjectionContentMediaIdentity,
    ) -> PromptProjectionContentCacheKey:
        """Return the projection content cache identity for prepared state."""

        style_key = paint_input.style_key
        if style_key is None:
            raise ValueError("paint cache keys require a prepared semantic palette")
        return PromptProjectionContentCacheKey(
            paint_identity=paint_identity,
            style=style_key,
            media_identity=media_identity,
        )

    def render_cache_pixmap(
        self,
        *,
        paint_input: PromptProjectionPaintInput,
        viewport_rect: QRectF,
        scroll_offset: float,
        device_pixel_ratio: float,
    ) -> QPixmap:
        """Render the selection-free projection layer into a viewport pixmap."""

        bounded_device_pixel_ratio = max(1.0, float(device_pixel_ratio))
        pixel_size = QSize(
            max(1, int(math.ceil(viewport_rect.width() * bounded_device_pixel_ratio))),
            max(1, int(math.ceil(viewport_rect.height() * bounded_device_pixel_ratio))),
        )
        pixmap = QPixmap(pixel_size)
        pixmap.setDevicePixelRatio(bounded_device_pixel_ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        cache_painter = QPainter(pixmap)
        cache_painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        try:
            self._painter.draw(
                cache_painter,
                paint_input=paint_input,
                selection_layer=EMPTY_PROJECTION_SELECTION_LAYER,
                scroll_offset=scroll_offset,
                clip_rect=viewport_rect,
                excluded_region=None,
            )
        finally:
            cache_painter.end()
        return pixmap


def _is_small_projection_content_repaint(
    *,
    clip_rect: QRectF,
    viewport_rect: QRectF,
) -> bool:
    """Return whether direct drawing is cheaper than rebuilding viewport cache."""

    if clip_rect.isEmpty() or viewport_rect.isEmpty():
        return False
    if (
        abs(clip_rect.width() - viewport_rect.width()) < 1.0
        and abs(clip_rect.height() - viewport_rect.height()) < 1.0
    ):
        return False
    viewport_area = max(1.0, viewport_rect.width() * viewport_rect.height())
    clip_area = max(0.0, clip_rect.width() * clip_rect.height())
    return clip_area <= viewport_area * 0.35
