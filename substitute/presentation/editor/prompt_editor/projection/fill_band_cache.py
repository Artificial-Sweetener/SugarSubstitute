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

"""Own bounded prompt scene fill-band geometry caching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import parse_prompt_scene_projection_document
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    record_prompt_editor_work_count,
)

from .model import PromptProjectionDisplayMode


class PromptProjectionFillBandLayout(Protocol):
    """Expose the immutable-layout query required to build fill bands."""

    def source_range_row_rects(
        self,
        source_start: int,
        source_end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return visible row rectangles for one source range."""


@dataclass(frozen=True, slots=True)
class PromptFillBandRect:
    """Describe one visible prompt fill band in viewport coordinates."""

    rect: QRectF
    band_index: int


@dataclass(frozen=True, slots=True)
class PromptProjectionFillBandCacheKey:
    """Identify one committed projection view state for fill-band caching."""

    source_revision: int
    display_mode: PromptProjectionDisplayMode
    viewport_width: int
    viewport_height: int
    scroll_offset: int
    content_width: float
    content_left_inset: float


@dataclass(frozen=True, slots=True)
class PromptProjectionFillBandBuildRequest:
    """Carry miss-only source and viewport data required to build fill bands."""

    source_text: str
    viewport_rect: QRectF
    scroll_offset: float


@dataclass(frozen=True, slots=True)
class _PromptProjectionFillBandCacheEntry:
    """Retain one bounded fill-band result under its exact view key."""

    key: PromptProjectionFillBandCacheKey
    rects: tuple[PromptFillBandRect, ...]


class PromptProjectionFillBandCache:
    """Build and retain one revision-keyed visible fill-band snapshot."""

    def __init__(self) -> None:
        """Initialize an empty one-entry cache."""

        self._entry: _PromptProjectionFillBandCacheEntry | None = None

    def cached_rects(
        self,
        key: PromptProjectionFillBandCacheKey,
    ) -> tuple[PromptFillBandRect, ...] | None:
        """Return a matching snapshot before callers prepare miss-only source."""

        entry = self._entry
        if entry is not None and self._keys_match(entry.key, key):
            record_prompt_editor_work_count(PromptEditorWorkEvent.FILL_BAND_CACHE_HIT)
            return entry.rects
        return None

    def build_and_store(
        self,
        key: PromptProjectionFillBandCacheKey,
        request: PromptProjectionFillBandBuildRequest,
        *,
        layout: PromptProjectionFillBandLayout,
    ) -> tuple[PromptFillBandRect, ...]:
        """Build and retain one miss after the caller prepares source data."""

        rects = self._build_rects(request, layout=layout)
        self._entry = _PromptProjectionFillBandCacheEntry(key=key, rects=rects)
        record_prompt_editor_work_count(PromptEditorWorkEvent.FILL_BAND_CACHE_MISS)
        return rects

    @staticmethod
    def _keys_match(
        cached: PromptProjectionFillBandCacheKey,
        requested: PromptProjectionFillBandCacheKey,
    ) -> bool:
        """Return whether two keys address interchangeable visible geometry."""

        return bool(
            cached.source_revision == requested.source_revision
            and cached.display_mode is requested.display_mode
            and cached.viewport_width == requested.viewport_width
            and cached.viewport_height == requested.viewport_height
            and cached.scroll_offset == requested.scroll_offset
            and abs(cached.content_width - requested.content_width) < 0.01
            and abs(cached.content_left_inset - requested.content_left_inset) < 0.01
        )

    @staticmethod
    def _build_rects(
        request: PromptProjectionFillBandBuildRequest,
        *,
        layout: PromptProjectionFillBandLayout,
    ) -> tuple[PromptFillBandRect, ...]:
        """Build visible band rows from one prepared scene document."""

        scene_document = parse_prompt_scene_projection_document(request.source_text)
        if not scene_document.has_scenes:
            return ()

        band_rects: list[PromptFillBandRect] = []
        next_band_index = 0
        if scene_document.universal_text.strip():
            band_rects.extend(
                PromptFillBandRect(rect=rect, band_index=next_band_index)
                for rect in layout.source_range_row_rects(
                    scene_document.universal_range.start,
                    scene_document.universal_range.end,
                    viewport_rect=request.viewport_rect,
                    scroll_offset=request.scroll_offset,
                )
            )
            next_band_index += 1
        for scene_index, scene in enumerate(scene_document.scenes):
            band_index = next_band_index + scene_index
            band_rects.extend(
                PromptFillBandRect(rect=rect, band_index=band_index)
                for rect in layout.source_range_row_rects(
                    scene.marker.title_range.start,
                    scene.content_range.end,
                    viewport_rect=request.viewport_rect,
                    scroll_offset=request.scroll_offset,
                )
            )
        return tuple(band_rects)


__all__ = [
    "PromptFillBandRect",
    "PromptProjectionFillBandBuildRequest",
    "PromptProjectionFillBandCache",
    "PromptProjectionFillBandCacheKey",
    "PromptProjectionFillBandLayout",
]
