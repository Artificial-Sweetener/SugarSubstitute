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

"""Retain bounded diagnostic fragment geometry across prompt revisions."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Final

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)

from .diagnostic_render_layer import (
    PromptDiagnosticFragmentKey,
    PromptDiagnosticViewportIdentity,
)

_DIAGNOSTIC_FRAGMENT_CACHE_LIMIT: Final[int] = 512


class PromptDiagnosticFragmentCache:
    """Own bounded least-recently-used diagnostic fragment geometry."""

    def __init__(self, *, capacity: int = _DIAGNOSTIC_FRAGMENT_CACHE_LIMIT) -> None:
        """Create a cache with a positive hard entry budget."""

        if capacity <= 0:
            raise ValueError("diagnostic fragment cache capacity must be positive")
        self._capacity = capacity
        self._entries: OrderedDict[
            PromptDiagnosticFragmentKey,
            tuple[QRectF, ...],
        ] = OrderedDict()

    @property
    def entries(
        self,
    ) -> Mapping[PromptDiagnosticFragmentKey, tuple[QRectF, ...]]:
        """Expose a read-only view for owner diagnostics and tests."""

        return MappingProxyType(self._entries)

    def get(
        self,
        key: PromptDiagnosticFragmentKey,
    ) -> tuple[QRectF, ...] | None:
        """Return and promote one cached fragment tuple."""

        fragments = self._entries.get(key)
        if fragments is not None:
            self._entries.move_to_end(key)
        return fragments

    def contains(self, key: PromptDiagnosticFragmentKey) -> bool:
        """Return whether one exact revision key is retained."""

        return key in self._entries

    def put(
        self,
        key: PromptDiagnosticFragmentKey,
        fragments: tuple[QRectF, ...],
    ) -> None:
        """Retain one entry and evict only the least-recently-used overflow."""

        self._entries[key] = fragments
        self._entries.move_to_end(key)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)

    def get_or_build(
        self,
        key: PromptDiagnosticFragmentKey,
        build: Callable[[], tuple[QRectF, ...]],
    ) -> tuple[QRectF, ...]:
        """Return retained fragments or publish one newly built tuple."""

        cached = self.get(key)
        if cached is not None:
            return cached
        fragments = build()
        self.put(key, fragments)
        return fragments

    def clear(self) -> None:
        """Discard all entries after an incompatible owner revision."""

        self._entries.clear()

    def preserve_for_incremental_edit(
        self,
        *,
        diagnostics: Sequence[PromptDiagnostic],
        start: int,
        end: int,
        replacement_text: str,
        previous_layout_identity: PromptLayoutIdentity,
        next_layout_identity: PromptLayoutIdentity,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Remap unaffected entries across one accepted incremental edit."""

        if not self._entries:
            return
        delta = len(replacement_text) - (end - start)
        diagnostics_by_range = {
            (diagnostic.source_start, diagnostic.source_end): diagnostic
            for diagnostic in diagnostics
        }
        preserved: OrderedDict[
            PromptDiagnosticFragmentKey,
            tuple[QRectF, ...],
        ] = OrderedDict()
        for key, fragments in self._entries.items():
            if key.viewport.layout_identity != previous_layout_identity:
                continue
            if _range_intersects_edit(
                key.source_start,
                key.source_end,
                start=start,
                end=end,
            ):
                continue
            remapped_start = _remap_position(
                key.source_start,
                start=start,
                end=end,
                delta=delta,
            )
            remapped_end = _remap_position(
                key.source_end,
                start=start,
                end=end,
                delta=delta,
            )
            if remapped_start is None or remapped_end is None:
                continue
            diagnostic = diagnostics_by_range.get((remapped_start, remapped_end))
            if diagnostic is None:
                continue
            next_key = PromptDiagnosticFragmentKey(
                diagnostic_id=diagnostic.diagnostic_id,
                source_start=diagnostic.source_start,
                source_end=diagnostic.source_end,
                viewport=PromptDiagnosticViewportIdentity(
                    layout_identity=next_layout_identity,
                    viewport_x=key.viewport.viewport_x,
                    viewport_y=key.viewport.viewport_y,
                    viewport_width=key.viewport.viewport_width,
                    viewport_height=key.viewport.viewport_height,
                    scroll_offset=key.viewport.scroll_offset,
                ),
            )
            preserved[next_key] = _shift_fragments_after_edit(
                fragments,
                diagnostic_start=key.source_start,
                edit_start=start,
                edit_end=end,
                y_delta=fragment_y_delta,
            )
        self._entries = preserved


def diagnostic_fragment_key(
    *,
    diagnostic: PromptDiagnostic,
    layout_identity: PromptLayoutIdentity,
    viewport_rect: QRectF,
    scroll_offset: float,
) -> PromptDiagnosticFragmentKey:
    """Build one stable diagnostic geometry revision key."""

    return PromptDiagnosticFragmentKey(
        diagnostic_id=diagnostic.diagnostic_id,
        source_start=diagnostic.source_start,
        source_end=diagnostic.source_end,
        viewport=diagnostic_viewport_identity(
            layout_identity=layout_identity,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        ),
    )


def diagnostic_viewport_identity(
    *,
    layout_identity: PromptLayoutIdentity,
    viewport_rect: QRectF,
    scroll_offset: float,
) -> PromptDiagnosticViewportIdentity:
    """Build one stable diagnostic layout-and-viewport revision identity."""

    return PromptDiagnosticViewportIdentity(
        layout_identity=layout_identity,
        viewport_x=_cache_coordinate(viewport_rect.x()),
        viewport_y=_cache_coordinate(viewport_rect.y()),
        viewport_width=_cache_coordinate(viewport_rect.width()),
        viewport_height=_cache_coordinate(viewport_rect.height()),
        scroll_offset=_cache_coordinate(scroll_offset),
    )


def _cache_coordinate(value: float) -> int:
    """Quantize one geometry coordinate for stable cache identity."""

    return int(round(value * 100.0))


def _remap_position(
    position: int,
    *,
    start: int,
    end: int,
    delta: int,
) -> int | None:
    """Shift a position across a non-overlapping source edit."""

    if start == end:
        if position > start:
            return position + delta
        return position
    if position >= end:
        return position + delta
    if position > start:
        return None
    return position


def _range_intersects_edit(
    diagnostic_start: int,
    diagnostic_end: int,
    *,
    start: int,
    end: int,
) -> bool:
    """Return whether one diagnostic range crosses an edited source range."""

    if start == end:
        return diagnostic_start < start < diagnostic_end
    return diagnostic_start < end and diagnostic_end > start


def _shift_fragments_after_edit(
    fragments: tuple[QRectF, ...],
    *,
    diagnostic_start: int,
    edit_start: int,
    edit_end: int,
    y_delta: float,
) -> tuple[QRectF, ...]:
    """Translate downstream cached fragments after hard-line topology changes."""

    if y_delta == 0.0:
        return fragments
    downstream_boundary = edit_start if edit_start == edit_end else edit_end
    if diagnostic_start < downstream_boundary:
        return fragments
    return tuple(rect.translated(0.0, y_delta) for rect in fragments)


__all__ = [
    "PromptDiagnosticFragmentCache",
    "diagnostic_fragment_key",
    "diagnostic_viewport_identity",
]
