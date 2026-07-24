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

"""Synchronize prepared projection geometry into one viewport frame."""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtWidgets import QAbstractScrollArea

from substitute.application.appearance import SemanticPalette

from .applicator import PromptProjectionApplicator
from .frame_state import (
    PromptProjectionFrameStatePublisher,
    PromptProjectionLayoutWidthResolver,
)
from .freshness_controller import PromptProjectionFreshnessController
from .layout_engine import PromptProjectionLayout
from .model import PromptProjectionDisplayMode
from .region_chrome import PromptRegionChrome
from .reorder_preview_projection import PromptReorderPreviewProjectionService
from .source_document import PromptProjectionSourceDocument
from .source_line_chrome import PromptSourceLineChrome
from .theme import semantic_palette_from_theme


class PromptProjectionFrameSynchronizer:
    """Own layout, chrome, scroll, freshness, and frame-state synchronization."""

    def __init__(
        self,
        *,
        host: QAbstractScrollArea,
        layout: PromptProjectionLayout,
        applicator: PromptProjectionApplicator,
        reorder_preview: PromptReorderPreviewProjectionService,
        frame_state: PromptProjectionFrameStatePublisher,
        width_resolver: PromptProjectionLayoutWidthResolver,
        freshness: PromptProjectionFreshnessController,
        region_chrome: PromptRegionChrome,
        source_document: PromptProjectionSourceDocument,
        source_line_chrome: PromptSourceLineChrome,
        scroll_offset: Callable[[], float],
        scroll_range_sink: Callable[[int, int], None],
        content_height_sink: Callable[[float], None],
    ) -> None:
        """Store stable frame collaborators without adding per-frame discovery."""

        self._host = host
        self._layout = layout
        self._applicator = applicator
        self._reorder_preview = reorder_preview
        self._frame_state = frame_state
        self._width_resolver = width_resolver
        self._freshness = freshness
        self._region_chrome = region_chrome
        self._source_document = source_document
        self._source_line_chrome = source_line_chrome
        self._scroll_offset = scroll_offset
        self._scroll_range_sink = scroll_range_sink
        self._content_height_sink = content_height_sink

    def sync(
        self,
        *,
        display_mode: PromptProjectionDisplayMode,
        commit_projection: bool = False,
    ) -> None:
        """Prepare and publish one complete layout-backed viewport frame."""

        layout_width = self._width_resolver.resolve()
        semantic_palette = semantic_palette_from_theme()
        sync_result = self._applicator.sync_layout_state(
            layout=self._layout,
            reorder_preview_layout=self._reorder_preview.preview_layout,
            reorder_base_drag_layout=self._reorder_preview.base_drag_layout,
            layout_width=layout_width,
            font=self._host.font(),
            palette=self._host.palette(),
            semantic_palette=semantic_palette,
            content_left_inset=self._source_line_chrome.content_left_inset,
        )
        layout_identity = self._frame_state.publish_layout(self._layout)
        self._prepare_region_chrome(
            self._layout,
            semantic_palette=semantic_palette,
        )
        preview_layout = self._reorder_preview.preview_layout
        if preview_layout is not None:
            self._prepare_region_chrome(
                preview_layout,
                semantic_palette=semantic_palette,
            )
        self._source_document.sync_default_font(self._host.font())
        self._source_document.sync_text_width(layout_width)

        viewport = self._host.viewport()
        viewport_height = max(1, viewport.height())
        scroll_range = max(
            0,
            math.ceil(sync_result.content_height - viewport_height),
        )
        vertical_scroll_bar = self._host.verticalScrollBar()
        vertical_scroll_bar.setPageStep(viewport_height)
        vertical_scroll_bar.setRange(0, scroll_range)
        self._scroll_range_sink(viewport_height, scroll_range)
        should_emit_height = self._freshness.sync_layout_metrics(
            commit_projection=commit_projection,
            reorder_preview_active=self._reorder_preview.is_active(),
            layout_identity=layout_identity,
            content_height=sync_result.content_height,
            content_width=sync_result.content_width,
            layout_width=sync_result.layout_width,
            display_mode=display_mode,
        )
        if should_emit_height:
            self._content_height_sink(sync_result.content_height)
        self._frame_state.publish_widget_viewport(
            viewport,
            horizontal_scroll=int(self._host.horizontalScrollBar().value()),
            vertical_scroll=int(round(self._scroll_offset())),
        )
        self._frame_state.publish_prepared_paint(self._layout)

    def _prepare_region_chrome(
        self,
        layout: PromptProjectionLayout,
        *,
        semantic_palette: SemanticPalette,
    ) -> None:
        """Prepare region chrome only for projected documents with separators."""

        if (
            layout.projection_document.display_mode
            is PromptProjectionDisplayMode.PROJECTED
            and layout.projection_document.region_structure.separators
        ):
            self._region_chrome.prepare(
                layout,
                semantic_palette=semantic_palette,
            )
