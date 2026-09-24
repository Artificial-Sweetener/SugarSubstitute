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

"""Own visible prompt fill-band presentation and cache identity."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from .fill_band_cache import (
    PromptFillBandRect,
    PromptProjectionFillBandBuildRequest,
    PromptProjectionFillBandCache,
    PromptProjectionFillBandCacheKey,
)
from .freshness_controller import PromptProjectionFreshnessController
from .reorder_geometry import (
    PromptProjectionReorderGeometry,
    PromptProjectionReorderGeometryState,
)
from .theme import scene_zebra_color


class PromptProjectionFillBandOwner:
    """Publish cached scene bands from one freshness-consistent view state."""

    def __init__(
        self,
        *,
        freshness: PromptProjectionFreshnessController,
        display_mode: Callable[[], PromptProjectionDisplayMode],
        current_source_identity: Callable[[], PromptSourceIdentity],
        committed_source_text: Callable[[], str],
        live_source_text: Callable[[], str],
        viewport_rect: Callable[[], QRectF],
        scroll_offset: Callable[[], float],
        content_width: Callable[[], float],
        content_left_inset: Callable[[], float],
        reorder_geometry: PromptProjectionReorderGeometry,
        geometry_state: Callable[[], PromptProjectionReorderGeometryState],
    ) -> None:
        """Bind the live inputs sampled together for each passive band read."""

        self._freshness = freshness
        self._display_mode = display_mode
        self._current_source_identity = current_source_identity
        self._committed_source_text = committed_source_text
        self._live_source_text = live_source_text
        self._viewport_rect = viewport_rect
        self._scroll_offset = scroll_offset
        self._content_width = content_width
        self._content_left_inset = content_left_inset
        self._reorder_geometry = reorder_geometry
        self._geometry_state = geometry_state
        self._cache = PromptProjectionFillBandCache()

    def visible_rects(self) -> tuple[PromptFillBandRect, ...]:
        """Return bands matching the currently paintable projection geometry."""

        display_mode = self._display_mode()
        if display_mode is PromptProjectionDisplayMode.RAW:
            return ()
        viewport_rect = self._viewport_rect()
        scroll_offset = self._scroll_offset()
        key = PromptProjectionFillBandCacheKey(
            source_identity=self._freshness.fill_band_source_identity(
                current_source_identity=self._current_source_identity()
            ),
            display_mode=display_mode,
            viewport_width=int(round(viewport_rect.width())),
            viewport_height=int(round(viewport_rect.height())),
            scroll_offset=int(round(scroll_offset)),
            content_width=self._freshness.fill_band_content_width(
                current_content_width=self._content_width()
            ),
            content_left_inset=self._content_left_inset(),
        )
        cached_rects = self._cache.cached_rects(key)
        if cached_rects is not None:
            return cached_rects
        return self._cache.build_and_store(
            key,
            PromptProjectionFillBandBuildRequest(
                source_text=self._freshness.fill_band_source_text(
                    committed_source_text=self._committed_source_text(),
                    live_source_text=self._live_source_text(),
                ),
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            ),
            reorder_geometry=self._reorder_geometry,
            geometry_state=self._geometry_state(),
        )

    @staticmethod
    def color() -> QColor:
        """Return the themed alternating color painted beneath scene rows."""

        return scene_zebra_color()


__all__ = ["PromptProjectionFillBandOwner"]
