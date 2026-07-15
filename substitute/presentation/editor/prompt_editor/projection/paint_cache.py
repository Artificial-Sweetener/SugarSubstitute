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

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QFont, QPainter, QPalette, QPixmap, QRegion

from substitute.application.appearance import SemanticPalette

from ..debug_probe import log_prompt_editor_probe
from .model import PromptProjectionDisplayMode, PromptProjectionSelection
from .paint_state import PromptProjectionPaintState

if TYPE_CHECKING:
    from .layout_engine import PromptProjectionLayout


@dataclass(frozen=True, slots=True)
class PromptProjectionContentCacheKey:
    """Identify one reusable viewport-local projection content pixmap."""

    source_revision: int
    projection_document_identity: int
    display_mode: PromptProjectionDisplayMode
    layout_snapshot_identity: int
    viewport_width: int
    viewport_height: int
    scroll_offset: int
    device_pixel_ratio: float
    font_key: str
    palette_cache_key: int
    text_color: int
    placeholder_color: int
    semantic_accent: tuple[int, int, int]
    semantic_error_foreground: tuple[int, int, int]
    layout_width: int
    content_left_inset: float
    content_width: int
    content_height: int
    visual_line_count: int
    text_fragment_count: int
    inline_object_count: int
    paint_state: PromptProjectionPaintState


class PromptProjectionPaintCache:
    """Own selection-free projection content cache policy and pixmap rendering."""

    def __init__(self) -> None:
        """Initialize an empty projection content cache."""

        self._cache_key: PromptProjectionContentCacheKey | None = None
        self._cache_pixmap: QPixmap | None = None
        self._skip_next_cache_build = False

    @property
    def cache_key(self) -> PromptProjectionContentCacheKey | None:
        """Return the currently cached projection content identity."""

        return self._cache_key

    @property
    def cache_pixmap(self) -> QPixmap | None:
        """Return the currently cached projection content pixmap."""

        return self._cache_pixmap

    def skip_next_cache_build(self) -> None:
        """Force the next cache-eligible paint to draw directly once."""

        self._skip_next_cache_build = True

    def paint_projection_content(
        self,
        painter: QPainter,
        *,
        active_layout: PromptProjectionLayout,
        base_layout: PromptProjectionLayout,
        selection: PromptProjectionSelection,
        scroll_offset: float,
        clip_rect: QRectF,
        viewport_rect: QRectF,
        excluded_region: QRegion | None,
        source_revision: int,
        device_pixel_ratio: float,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette,
    ) -> str:
        """Paint projection content directly or through a viewport pixmap cache."""

        log_prompt_editor_probe(
            "projection_paint_cache.paint.begin",
            active_layout_id=id(active_layout),
            base_layout_id=id(base_layout),
            active_document_id=id(active_layout.projection_document),
            base_document_id=id(base_layout.projection_document),
            active_projection_text=active_layout.projection_document.projection_text,
            base_projection_text=base_layout.projection_document.projection_text,
            selection_empty=selection.is_empty,
            excluded_region_present=excluded_region is not None,
            clip_rect=repr(clip_rect),
            viewport_rect=repr(viewport_rect),
            cache_key_present=self._cache_key is not None,
            skip_next_cache_build=self._skip_next_cache_build,
        )
        if active_layout is not base_layout:
            active_layout.draw(
                painter,
                selection=selection,
                scroll_offset=scroll_offset,
                clip_rect=clip_rect,
                excluded_region=excluded_region,
            )
            log_prompt_editor_probe(
                "projection_paint_cache.paint.end",
                result="preview",
                cache_key_present=self._cache_key is not None,
            )
            return "preview"

        if (
            not selection.is_empty
            or excluded_region is not None
            or clip_rect.isEmpty()
            or viewport_rect.isEmpty()
        ):
            base_layout.draw(
                painter,
                selection=selection,
                scroll_offset=scroll_offset,
                clip_rect=clip_rect,
                excluded_region=excluded_region,
            )
            log_prompt_editor_probe(
                "projection_paint_cache.paint.end",
                result="bypass",
                cache_key_present=self._cache_key is not None,
            )
            return "bypass"

        cache_key = self.cache_key_for(
            layout=base_layout,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            source_revision=source_revision,
            device_pixel_ratio=device_pixel_ratio,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        if (
            self._cache_key == cache_key
            and self._cache_pixmap is not None
            and not self._cache_pixmap.isNull()
        ):
            painter.drawPixmap(QPointF(0.0, 0.0), self._cache_pixmap)
            log_prompt_editor_probe(
                "projection_paint_cache.paint.end",
                result="hit",
                cache_key=repr(cache_key),
                cache_key_present=True,
            )
            return "hit"

        if self._skip_next_cache_build:
            self._skip_next_cache_build = False
            base_layout.draw(
                painter,
                selection=selection,
                scroll_offset=scroll_offset,
                clip_rect=clip_rect,
                excluded_region=excluded_region,
            )
            log_prompt_editor_probe(
                "projection_paint_cache.paint.end",
                result="bypass_source_edit",
                cache_key=repr(cache_key),
                cache_key_present=self._cache_key is not None,
            )
            return "bypass_source_edit"

        if _is_small_projection_content_repaint(
            clip_rect=clip_rect,
            viewport_rect=viewport_rect,
        ):
            base_layout.draw(
                painter,
                selection=selection,
                scroll_offset=scroll_offset,
                clip_rect=clip_rect,
                excluded_region=excluded_region,
            )
            log_prompt_editor_probe(
                "projection_paint_cache.paint.end",
                result="bypass_small_cache_miss",
                cache_key=repr(cache_key),
                cache_key_present=self._cache_key is not None,
            )
            return "bypass_small_cache_miss"

        pixmap = self.render_cache_pixmap(
            layout=base_layout,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            device_pixel_ratio=device_pixel_ratio,
        )
        self._cache_key = cache_key
        self._cache_pixmap = pixmap
        painter.drawPixmap(QPointF(0.0, 0.0), pixmap)
        log_prompt_editor_probe(
            "projection_paint_cache.paint.end",
            result="miss",
            cache_key=repr(cache_key),
            cache_key_present=True,
        )
        return "miss"

    def cache_key_for(
        self,
        *,
        layout: PromptProjectionLayout,
        viewport_rect: QRectF,
        scroll_offset: float,
        source_revision: int,
        device_pixel_ratio: float,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette,
    ) -> PromptProjectionContentCacheKey:
        """Return the projection content cache identity for prepared state."""

        content_size = layout.content_size()
        return PromptProjectionContentCacheKey(
            source_revision=source_revision,
            projection_document_identity=id(layout.projection_document),
            display_mode=layout.projection_document.display_mode,
            layout_snapshot_identity=id(layout._snapshot),
            viewport_width=int(round(viewport_rect.width())),
            viewport_height=int(round(viewport_rect.height())),
            scroll_offset=int(round(scroll_offset)),
            device_pixel_ratio=round(float(device_pixel_ratio), 3),
            font_key=font.toString(),
            palette_cache_key=int(palette.cacheKey()),
            text_color=palette.color(QPalette.ColorRole.Text).rgba(),
            placeholder_color=palette.color(QPalette.ColorRole.PlaceholderText).rgba(),
            semantic_accent=(
                semantic_palette.accent.red,
                semantic_palette.accent.green,
                semantic_palette.accent.blue,
            ),
            semantic_error_foreground=(
                semantic_palette.error_foreground.red,
                semantic_palette.error_foreground.green,
                semantic_palette.error_foreground.blue,
            ),
            layout_width=int(round(layout._text_width)),
            content_left_inset=round(layout._content_left_inset, 3),
            content_width=int(round(content_size.width())),
            content_height=int(round(content_size.height())),
            visual_line_count=layout.line_count(),
            text_fragment_count=layout.text_fragment_count(),
            inline_object_count=layout.inline_object_fragment_count(),
            paint_state=layout.paint_state,
        )

    def render_cache_pixmap(
        self,
        *,
        layout: PromptProjectionLayout,
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
            layout.draw(
                cache_painter,
                selection=None,
                scroll_offset=scroll_offset,
                clip_rect=viewport_rect,
                excluded_region=None,
            )
        finally:
            cache_painter.end()
        return pixmap

    def invalidate(self, *, reason: str) -> None:
        """Drop cached projection content after a visual-content change."""

        log_prompt_editor_probe(
            "projection_paint_cache.invalidate",
            reason=reason,
            cache_key_present=self._cache_key is not None,
        )
        if self._cache_key is None:
            return
        self._cache_key = None
        self._cache_pixmap = None


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
