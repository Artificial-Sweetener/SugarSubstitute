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

"""Tests for projection content paint-cache identity."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from substitute.application.prompt_editor.document.views import (
    PromptRegionStructureView,
)


from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPixmap

from substitute.domain.appearance import RgbColor, SemanticPalette
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
    PromptLayoutRevision,
    PromptPaintIdentity,
    PromptPaintStateRevision,
    PromptProjectionIdentity,
    PromptProjectionRevision,
    PromptSemanticIdentity,
    PromptSemanticRevision,
    PromptSourceIdentity,
    PromptViewportIdentity,
    PromptViewportRevision,
)
from substitute.presentation.editor.prompt_editor.projection.caret_map_builder import (
    build_prompt_projection_caret_map,
)
from substitute.presentation.editor.prompt_editor.projection.content_selection_layer import (
    EMPTY_PROJECTION_SELECTION_LAYER,
)
from substitute.presentation.editor.prompt_editor.projection.content_media_state import (
    PromptProjectionContentMediaIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.mapping import (
    PromptProjectionMapping,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.paint_cache import (
    PromptProjectionPaintCache,
)
from substitute.presentation.editor.prompt_editor.projection.paint_input import (
    PromptProjectionPaintInput,
    PromptProjectionPaintStyleKey,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptProjectionInlineObjectRendererRegistry,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp


def test_projection_content_cache_key_tracks_prepared_and_style_inputs() -> None:
    """Paint-cache identity should include prepared lineage and visible style."""

    ensure_qapp()
    font = QFont()
    font.setPointSize(11)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Text, QColor("#202020"))
    semantic_palette = _semantic_palette(accent=RgbColor(1, 2, 3))
    layout = _layout_for(
        "alpha beta",
        font=font,
        palette=palette,
        semantic_palette=semantic_palette,
    )
    cache = PromptProjectionPaintCache()
    paint_identity = _paint_identity(source_revision=7)

    key = cache.cache_key_for(
        paint_input=layout.frame.paint_input,
        paint_identity=paint_identity,
        media_identity=_media_identity(),
    )

    assert key.paint_identity == paint_identity
    assert key.style.display_mode is PromptProjectionDisplayMode.PROJECTED
    assert key.style.font_key == font.toString()
    assert key.style.palette_cache_key == int(palette.cacheKey())
    assert key.style.semantic_accent == (1, 2, 3)
    assert (
        cache.cache_key_for(
            paint_input=layout.frame.paint_input,
            paint_identity=paint_identity,
            media_identity=_media_identity(revision=1),
        )
        != key
    )

    assert (
        _cache_key_for(
            cache,
            layout=layout,
            paint_identity=_paint_identity(source_revision=8),
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        != key
    )
    assert (
        _cache_key_for(
            cache,
            layout=layout,
            paint_identity=_paint_identity(source_revision=7, viewport_revision=2),
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        != key
    )
    assert (
        _cache_key_for(
            cache,
            layout=layout,
            paint_identity=paint_identity,
            font=font,
            palette=palette,
            semantic_palette=_semantic_palette(accent=RgbColor(9, 8, 7)),
        )
        != key
    )

    next_font = QFont(font)
    next_font.setPointSize(13)
    assert (
        _cache_key_for(
            cache,
            layout=layout,
            paint_identity=paint_identity,
            font=next_font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        != key
    )

    next_palette = QPalette(palette)
    next_palette.setColor(QPalette.ColorRole.Text, QColor("#303030"))
    assert (
        _cache_key_for(
            cache,
            layout=layout,
            paint_identity=paint_identity,
            font=font,
            palette=next_palette,
            semantic_palette=semantic_palette,
        )
        != key
    )

    inset_layout = _layout_for(
        "alpha beta",
        font=font,
        palette=palette,
        semantic_palette=semantic_palette,
        content_left_inset=18.0,
    )
    assert (
        _cache_key_for(
            cache,
            layout=inset_layout,
            paint_identity=_paint_identity(source_revision=7, layout_revision=2),
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        != key
    )


def test_prepared_frame_retains_paint_input_for_unchanged_style_publication() -> None:
    """Repeated frame synchronization must not rebuild unchanged paint inputs."""

    ensure_qapp()
    font = QFont()
    palette = QPalette()
    semantic_palette = _semantic_palette(accent=RgbColor(1, 2, 3))
    layout = _layout_for(
        "alpha beta",
        font=font,
        palette=palette,
        semantic_palette=semantic_palette,
    )
    paint_input = layout.frame.paint_input

    layout.frame.set_palette(QPalette(palette))
    layout.frame.set_semantic_palette(semantic_palette)

    assert layout.frame.paint_input is paint_input


def test_prepared_frame_rebuilds_paint_input_for_changed_style_publication() -> None:
    """Changed palette state must publish a new prepared paint input."""

    ensure_qapp()
    font = QFont()
    palette = QPalette()
    semantic_palette = _semantic_palette(accent=RgbColor(1, 2, 3))
    layout = _layout_for(
        "alpha beta",
        font=font,
        palette=palette,
        semantic_palette=semantic_palette,
    )
    paint_input = layout.frame.paint_input
    changed_palette = QPalette(palette)
    changed_palette.setColor(QPalette.ColorRole.Text, QColor("#303030"))

    layout.frame.set_palette(changed_palette)

    assert layout.frame.paint_input is not paint_input


def test_projection_content_cache_hit_key_consumes_only_prepared_style() -> None:
    """Keep font and palette queries out of cache-key lookup."""

    style_key = PromptProjectionPaintStyleKey(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        font_key="prepared-font",
        palette_cache_key=17,
        text_color=18,
        placeholder_color=19,
        semantic_accent=(1, 2, 3),
        semantic_error_foreground=(4, 5, 6),
    )
    paint_input = cast(PromptProjectionPaintInput, _PreparedStyleOnlyInput(style_key))

    key = PromptProjectionPaintCache().cache_key_for(
        paint_input=paint_input,
        paint_identity=_paint_identity(source_revision=7),
        media_identity=_media_identity(),
    )

    assert key.style.font_key == "prepared-font"
    assert key.style.palette_cache_key == 17


def test_projection_content_cache_hit_reuses_existing_identity() -> None:
    """Keep a warm full-viewport paint free of cache-key replacement."""

    ensure_qapp()
    layout = _layout_for(
        "alpha beta",
        font=QFont(),
        palette=QPalette(),
        semantic_palette=_semantic_palette(accent=RgbColor(1, 2, 3)),
    )
    cache = PromptProjectionPaintCache()
    paint_identity = _paint_identity(source_revision=7)
    viewport_rect = QRectF(0.0, 0.0, 240.0, 120.0)
    pixmap = QPixmap(240, 120)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        first_result = cache.paint_projection_content(
            painter,
            paint_input=layout.frame.paint_input,
            selection_layer=EMPTY_PROJECTION_SELECTION_LAYER,
            scroll_offset=0.0,
            clip_rect=viewport_rect,
            viewport_rect=viewport_rect,
            excluded_region=None,
            paint_identity=paint_identity,
            media_identity=_media_identity(),
            device_pixel_ratio=1.0,
        )
        first_key = cache.cache_key
        second_result = cache.paint_projection_content(
            painter,
            paint_input=layout.frame.paint_input,
            selection_layer=EMPTY_PROJECTION_SELECTION_LAYER,
            scroll_offset=0.0,
            clip_rect=viewport_rect,
            viewport_rect=viewport_rect,
            excluded_region=None,
            paint_identity=paint_identity,
            media_identity=_media_identity(),
            device_pixel_ratio=1.0,
        )
        second_key = cache.cache_key
        media_result = cache.paint_projection_content(
            painter,
            paint_input=layout.frame.paint_input,
            selection_layer=EMPTY_PROJECTION_SELECTION_LAYER,
            scroll_offset=0.0,
            clip_rect=viewport_rect,
            viewport_rect=viewport_rect,
            excluded_region=None,
            paint_identity=paint_identity,
            media_identity=_media_identity(revision=1),
            device_pixel_ratio=1.0,
        )
    finally:
        painter.end()

    assert first_result == "miss"
    assert second_result == "hit"
    assert first_key is second_key
    assert media_result == "miss"
    assert first_key is not cache.cache_key
    assert cache.cache_key is not None
    assert cache.cache_key.media_identity == _media_identity(revision=1)


class _PreparedStyleOnlyInput:
    """Expose only the style value allowed on cache-key lookup."""

    def __init__(self, style_key: PromptProjectionPaintStyleKey) -> None:
        """Store one already-prepared style key."""

        self.style_key = style_key


def _cache_key_for(
    cache: PromptProjectionPaintCache,
    *,
    layout: PromptLayoutEditToFrameCoordinator,
    paint_identity: PromptPaintIdentity,
    font: QFont,
    palette: QPalette,
    semantic_palette: SemanticPalette,
) -> object:
    """Return a content-cache key with stable non-varied paint inputs."""

    return cache.cache_key_for(
        paint_input=replace(
            layout.frame.paint_input,
            base_font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        ),
        paint_identity=paint_identity,
        media_identity=_media_identity(),
    )


def _media_identity(
    revision: int = 0,
) -> PromptProjectionContentMediaIdentity:
    """Return one explicit presentation-media revision for cache contracts."""

    return PromptProjectionContentMediaIdentity(revision=revision)


def _paint_identity(
    *,
    source_revision: int,
    layout_revision: int = 1,
    viewport_revision: int = 1,
) -> PromptPaintIdentity:
    """Return explicit prepared paint lineage for cache-key tests."""

    semantic = PromptSemanticIdentity(
        source=PromptSourceIdentity(source_revision, 10),
        semantic_revision=PromptSemanticRevision(source_revision),
    )
    projection = PromptProjectionIdentity(
        semantic=semantic,
        projection_revision=PromptProjectionRevision(source_revision),
    )
    layout = PromptLayoutIdentity(
        projection=projection,
        layout_revision=PromptLayoutRevision(layout_revision),
    )
    viewport = PromptViewportIdentity(
        viewport_revision=PromptViewportRevision(viewport_revision),
    )
    return PromptPaintIdentity(
        layout=layout,
        viewport=viewport,
        paint_state_revision=PromptPaintStateRevision(1),
    )


def _layout_for(
    text: str,
    *,
    font: QFont,
    palette: QPalette,
    semantic_palette: SemanticPalette,
    content_left_inset: float = 0.0,
) -> PromptLayoutEditToFrameCoordinator:
    """Return one laid-out plain-text projection for cache-key tests."""

    layout = PromptLayoutEditToFrameCoordinator(
        PromptProjectionInlineObjectRendererRegistry(())
    )
    layout.set_base_font(font)
    layout.frame.set_palette(palette)
    layout.frame.set_semantic_palette(semantic_palette)
    layout.set_content_left_inset(content_left_inset)
    layout.set_projection(_plain_text_document(text))
    layout.set_text_width(240.0)
    return layout


def _plain_text_document(text: str) -> PromptProjectionDocument:
    """Return one projected plain-text document."""

    run = PromptProjectionRun(
        run_id="text-run",
        kind=PromptProjectionRunKind.TEXT,
        source_start=0,
        source_end=len(text),
        display_text=text,
        source_positions=range(0, len(text) + 1),
        projection_start=0,
        projection_end=len(text),
    )
    mapping = PromptProjectionMapping(
        runs=(run,),
        source_length=len(text),
        projection_length=len(text),
    )
    caret_map = build_prompt_projection_caret_map(
        runs=(run,),
        tokens=(),
        source_length=len(text),
        projection_length=len(text),
    )
    return PromptProjectionDocument(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        source_text=text,
        projection_text=text,
        runs=(run,),
        tokens=(),
        mapping=mapping,
        caret_map=caret_map,
        region_structure=PromptRegionStructureView.empty(len(text)),
    )


def _semantic_palette(*, accent: RgbColor) -> SemanticPalette:
    """Return deterministic semantic colors for cache-key tests."""

    return SemanticPalette(
        accent=accent,
        error_foreground=RgbColor(180, 40, 60),
        warning_foreground=RgbColor(120, 160, 40),
    )
