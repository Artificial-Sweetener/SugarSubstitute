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

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QPalette

from substitute.domain.appearance import RgbColor, SemanticPalette
from substitute.presentation.editor.prompt_editor.projection.caret_map_builder import (
    build_prompt_projection_caret_map,
)
from substitute.presentation.editor.prompt_editor.projection.layout_engine import (
    PromptProjectionLayout,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.paint_cache import (
    PromptProjectionPaintCache,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptProjectionInlineObjectRendererRegistry,
)
from tests.prompt_projection_test_helpers import ensure_qapp


def test_projection_content_cache_key_tracks_revision_view_and_style_inputs() -> None:
    """Paint-cache identity should include every visible cache input."""

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
    viewport = QRectF(0.0, 0.0, 240.0, 120.0)

    key = cache.cache_key_for(
        layout=layout,
        viewport_rect=viewport,
        scroll_offset=4.0,
        source_revision=7,
        device_pixel_ratio=1.0,
        font=font,
        palette=palette,
        semantic_palette=semantic_palette,
    )

    assert key.source_revision == 7
    assert key.projection_document_identity == id(layout.projection_document)
    assert key.display_mode is PromptProjectionDisplayMode.PROJECTED
    assert key.layout_snapshot_identity == id(layout._snapshot)  # noqa: SLF001
    assert key.viewport_width == 240
    assert key.viewport_height == 120
    assert key.scroll_offset == 4
    assert key.device_pixel_ratio == 1.0
    assert key.font_key == font.toString()
    assert key.palette_cache_key == int(palette.cacheKey())
    assert key.semantic_accent == (1, 2, 3)

    assert (
        _cache_key_for(
            cache,
            layout=layout,
            viewport=viewport,
            source_revision=8,
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
            viewport=QRectF(0.0, 0.0, 260.0, 120.0),
            source_revision=7,
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
            viewport=viewport,
            source_revision=7,
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
            viewport=viewport,
            source_revision=7,
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
            viewport=viewport,
            source_revision=7,
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
            viewport=viewport,
            source_revision=7,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        != key
    )


def _cache_key_for(
    cache: PromptProjectionPaintCache,
    *,
    layout: PromptProjectionLayout,
    viewport: QRectF,
    source_revision: int,
    font: QFont,
    palette: QPalette,
    semantic_palette: SemanticPalette,
) -> object:
    """Return a content-cache key with stable non-varied paint inputs."""

    return cache.cache_key_for(
        layout=layout,
        viewport_rect=viewport,
        scroll_offset=4.0,
        source_revision=source_revision,
        device_pixel_ratio=1.0,
        font=font,
        palette=palette,
        semantic_palette=semantic_palette,
    )


def _layout_for(
    text: str,
    *,
    font: QFont,
    palette: QPalette,
    semantic_palette: SemanticPalette,
    content_left_inset: float = 0.0,
) -> PromptProjectionLayout:
    """Return one laid-out plain-text projection for cache-key tests."""

    layout = PromptProjectionLayout(PromptProjectionInlineObjectRendererRegistry(()))
    layout.set_base_font(font)
    layout.set_palette(palette)
    layout.set_semantic_palette(semantic_palette)
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
    )


def _semantic_palette(*, accent: RgbColor) -> SemanticPalette:
    """Return deterministic semantic colors for cache-key tests."""

    return SemanticPalette(
        accent=accent,
        error_foreground=RgbColor(180, 40, 60),
        warning_foreground=RgbColor(120, 160, 40),
    )
