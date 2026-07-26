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

"""Define immutable prompt search-highlight rendering commands."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)


@dataclass(frozen=True, slots=True)
class PromptSearchHighlightLayerKey:
    """Identify one exact search, layout, and palette state."""

    layout_identity: PromptLayoutIdentity
    match_ranges: tuple[tuple[int, int], ...]
    active_match_index: int | None
    palette_key: int


@dataclass(frozen=True, slots=True)
class PromptSearchHighlightRect:
    """Describe one immutable viewport-local highlight command."""

    left: float
    top: float
    width: float
    height: float
    color_rgba: int


@dataclass(frozen=True, slots=True)
class PromptSearchHighlightGeometryRect:
    """Describe one color-neutral document-space match fragment."""

    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class PromptSearchHighlightLayer:
    """Contain sorted document-space search commands for one revision."""

    key: PromptSearchHighlightLayerKey | None
    rects: tuple[PromptSearchHighlightRect, ...]
    tops: tuple[float, ...]
    maximum_height: float


EMPTY_SEARCH_HIGHLIGHT_LAYER = PromptSearchHighlightLayer(
    key=None,
    rects=(),
    tops=(),
    maximum_height=0.0,
)


__all__ = [
    "EMPTY_SEARCH_HIGHLIGHT_LAYER",
    "PromptSearchHighlightLayer",
    "PromptSearchHighlightLayerKey",
    "PromptSearchHighlightGeometryRect",
    "PromptSearchHighlightRect",
]
