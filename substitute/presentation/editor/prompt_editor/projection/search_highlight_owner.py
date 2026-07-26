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

"""Prepare revision-keyed prompt search highlight commands."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)
from substitute.presentation.editor.prompt_editor.geometry.aggregate import (
    PromptProjectionGeometry,
)

from .search_highlight_layer import (
    EMPTY_SEARCH_HIGHLIGHT_LAYER,
    PromptSearchHighlightGeometryRect,
    PromptSearchHighlightLayer,
    PromptSearchHighlightLayerKey,
    PromptSearchHighlightRect,
)

type PromptSearchHighlightGeometryKey = tuple[
    PromptLayoutIdentity,
    tuple[tuple[int, int], ...],
]


class PromptSearchHighlightLayerOwner:
    """Own search geometry preparation and revision reuse."""

    def __init__(self) -> None:
        """Create an empty prepared search layer."""

        self._layer = EMPTY_SEARCH_HIGHLIGHT_LAYER
        self._geometry_key: PromptSearchHighlightGeometryKey | None = None
        self._geometry_by_match: tuple[
            tuple[PromptSearchHighlightGeometryRect, ...],
            ...,
        ] = ()

    @property
    def layer(self) -> PromptSearchHighlightLayer:
        """Return the currently prepared immutable layer."""

        return self._layer

    def prepare(
        self,
        *,
        geometry: PromptProjectionGeometry,
        layout_identity: PromptLayoutIdentity,
        match_ranges: tuple[tuple[int, int], ...],
        active_match_index: int | None,
        palette: QPalette,
    ) -> bool:
        """Publish document-space commands only when search identity changes."""

        key = PromptSearchHighlightLayerKey(
            layout_identity=layout_identity,
            match_ranges=match_ranges,
            active_match_index=active_match_index,
            palette_key=int(palette.cacheKey()),
        )
        if self._layer.key == key:
            return False
        geometry_key = (layout_identity, match_ranges)
        if self._geometry_key != geometry_key:
            self._geometry_by_match = tuple(
                tuple(
                    PromptSearchHighlightGeometryRect(
                        left=rect.left(),
                        top=rect.top(),
                        width=rect.width(),
                        height=rect.height(),
                    )
                    for rect in geometry.selection.source_range_document_fragments(
                        start=start,
                        end=start + length,
                    )
                )
                for start, length in match_ranges
            )
            self._geometry_key = geometry_key
        passive_rgba = int(self.match_color(palette, active=False).rgba())
        active_rgba = int(self.match_color(palette, active=True).rgba())
        rects: list[PromptSearchHighlightRect] = []
        for match_index, match_rects in enumerate(self._geometry_by_match):
            color_rgba = (
                active_rgba if match_index == active_match_index else passive_rgba
            )
            rects.extend(
                PromptSearchHighlightRect(
                    left=rect.left,
                    top=rect.top,
                    width=rect.width,
                    height=rect.height,
                    color_rgba=color_rgba,
                )
                for rect in match_rects
            )
        rects.sort(key=lambda rect: (rect.top, rect.left))
        self._layer = PromptSearchHighlightLayer(
            key=key,
            rects=tuple(rects),
            tops=tuple(rect.top for rect in rects),
            maximum_height=max((rect.height for rect in rects), default=0.0),
        )
        return True

    def clear(self) -> bool:
        """Publish an empty search layer when highlights disappear."""

        if self._layer is EMPTY_SEARCH_HIGHLIGHT_LAYER:
            return False
        self._layer = EMPTY_SEARCH_HIGHLIGHT_LAYER
        return True

    @staticmethod
    def match_color(palette: QPalette, *, active: bool) -> QColor:
        """Return the passive or active search fill color."""

        color = QColor(palette.color(QPalette.ColorRole.Highlight))
        color.setAlpha(150 if active else 90)
        return color


__all__ = ["PromptSearchHighlightLayerOwner"]
