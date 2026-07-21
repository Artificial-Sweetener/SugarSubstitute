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

"""Build viewport-local reorder paint snapshots from prepared projection state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPalette

from .model import PromptProjectionDocument
from .painter import PromptProjectionPainter
from .reorder_visual_snapshot import (
    PromptReorderInlineObjectPaintFragment,
    PromptReorderProjectionPaintFragment,
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
    PromptReorderTextPaintFragment,
    reorder_projection_paint_content_key,
)
from .snapshot import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .tokens import PromptProjectionInlineObjectRendererRegistry
from .visible_line_range import (
    PromptProjectionSourceLineIndex,
    visible_projection_lines,
)


class PromptReorderPaintSnapshotBuilder:
    """Own extraction of chip paint fragments from one prepared viewport layout."""

    def __init__(
        self,
        *,
        projection_document: PromptProjectionDocument,
        lines: Sequence[PromptProjectionLineSnapshot],
        painter: PromptProjectionPainter,
        inline_object_renderers: PromptProjectionInlineObjectRendererRegistry,
        base_font: QFont,
        palette: QPalette,
    ) -> None:
        """Bind immutable layout inputs needed for one snapshot extraction batch."""

        self._projection_document = projection_document
        self._lines = lines
        self._painter = painter
        self._inline_object_renderers = inline_object_renderers
        self._base_font = base_font
        self._palette = palette

    def build(
        self,
        *,
        key: PromptReorderProjectionSnapshotKey,
        source_ranges: Sequence[tuple[int, int]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderProjectionPaintSnapshot:
        """Return cached-paint-ready fragments for one visible reorder chip."""

        source_line_index = self._visible_source_line_index(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        return self._build_from_visible_lines(
            key=key,
            source_ranges=source_ranges,
            source_line_index=source_line_index,
            scroll_offset=scroll_offset,
        )

    def build_many(
        self,
        *,
        keys_by_chip_index: Mapping[int, PromptReorderProjectionSnapshotKey],
        source_ranges_by_chip_index: Mapping[int, Sequence[tuple[int, int]]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Build a chip snapshot batch from one indexed visible-line window."""

        source_line_index = self._visible_source_line_index(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        return {
            chip_index: self._build_from_visible_lines(
                key=key,
                source_ranges=source_ranges_by_chip_index.get(chip_index, ()),
                source_line_index=source_line_index,
                scroll_offset=scroll_offset,
            )
            for chip_index, key in keys_by_chip_index.items()
        }

    def _build_from_visible_lines(
        self,
        *,
        key: PromptReorderProjectionSnapshotKey,
        source_ranges: Sequence[tuple[int, int]],
        source_line_index: PromptProjectionSourceLineIndex,
        scroll_offset: float,
    ) -> PromptReorderProjectionPaintSnapshot:
        """Build one snapshot from a shared viewport-local source-line index."""

        normalized_ranges = _normalized_source_ranges(source_ranges)
        fragments: list[PromptReorderProjectionPaintFragment] = []
        relevant_lines = _relevant_source_lines(
            source_line_index,
            source_ranges=normalized_ranges,
        )
        for line in relevant_lines:
            for fragment in line.fragments:
                if isinstance(fragment, PromptProjectionTextFragment):
                    fragments.extend(
                        self._text_paint_fragments(
                            fragment,
                            source_ranges=normalized_ranges,
                            scroll_offset=scroll_offset,
                        )
                    )
                    continue
                inline_fragment = self._inline_object_paint_fragment(
                    fragment,
                    source_ranges=normalized_ranges,
                    scroll_offset=scroll_offset,
                )
                if inline_fragment is not None:
                    fragments.append(inline_fragment)
        frozen_fragments = tuple(fragments)
        return PromptReorderProjectionPaintSnapshot(
            key=key,
            fragments=frozen_fragments,
            source_ranges=normalized_ranges,
            content_key=reorder_projection_paint_content_key(frozen_fragments),
        )

    def _visible_source_line_index(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptProjectionSourceLineIndex:
        """Return one source index over the current vertical viewport window."""

        visible_lines = visible_projection_lines(
            self._lines,
            document_top=viewport_rect.top() + scroll_offset,
            document_bottom=viewport_rect.bottom() + scroll_offset,
        )
        return PromptProjectionSourceLineIndex(visible_lines)

    def _text_paint_fragments(
        self,
        fragment: PromptProjectionTextFragment,
        *,
        source_ranges: tuple[tuple[int, int], ...],
        scroll_offset: float,
    ) -> tuple[PromptReorderTextPaintFragment, ...]:
        """Return chip-owned slices from one prepared projection text fragment."""

        if not fragment.source_positions:
            return ()
        chunks = _source_position_chunks(
            fragment.source_positions[: len(fragment.text)],
            source_ranges=source_ranges,
        )
        if not chunks:
            return ()
        font = self._painter.font_for_fragment(fragment)
        color = self._painter.text_color_for_fragment(fragment)
        return tuple(
            _text_paint_fragment(
                fragment,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                font=font,
                color=color,
                scroll_offset=scroll_offset,
            )
            for chunk_start, chunk_end in chunks
            if chunk_end > chunk_start
        )

    def _inline_object_paint_fragment(
        self,
        fragment: PromptProjectionInlineObjectFragment,
        *,
        source_ranges: tuple[tuple[int, int], ...],
        scroll_offset: float,
    ) -> PromptReorderInlineObjectPaintFragment | None:
        """Return one chip-owned inline object from prepared projection state."""

        if not _source_positions_overlap(fragment.source_positions, source_ranges):
            return None
        run = self._projection_document.run_by_id(fragment.run_id)
        token = self._projection_document.token_by_id(fragment.token_id)
        renderer = self._inline_object_renderers.renderer_for(fragment.renderer_key)
        if run is None or token is None or renderer is None:
            return None
        return PromptReorderInlineObjectPaintFragment(
            renderer=renderer,
            rect=fragment.rect.translated(0.0, -scroll_offset),
            run=run,
            token=token,
            base_font=QFont(self._base_font),
            palette=QPalette(self._palette),
        )


def _text_paint_fragment(
    fragment: PromptProjectionTextFragment,
    *,
    chunk_start: int,
    chunk_end: int,
    font: QFont,
    color: QColor,
    scroll_offset: float,
) -> PromptReorderTextPaintFragment:
    """Build one prepared text slice without rediscovering layout style."""

    left = fragment.rect.left() + fragment.boundary_offsets[chunk_start]
    right = fragment.rect.left() + fragment.boundary_offsets[chunk_end]
    return PromptReorderTextPaintFragment(
        text=fragment.text[chunk_start:chunk_end],
        font=QFont(font),
        baseline=QPointF(left, fragment.baseline - scroll_offset),
        text_rect=QRectF(
            left,
            fragment.rect.top() - scroll_offset,
            max(0.0, right - left),
            fragment.rect.height(),
        ),
        color=QColor(color),
    )


def _normalized_source_ranges(
    source_ranges: Sequence[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    """Return non-empty source ranges in deterministic order."""

    return tuple(sorted((start, end) for start, end in source_ranges if end > start))


def _relevant_source_lines(
    source_line_index: PromptProjectionSourceLineIndex,
    *,
    source_ranges: tuple[tuple[int, int], ...],
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return indexed visible lines whose source bounds can belong to one chip."""

    if not source_ranges:
        return ()
    range_start = source_ranges[0][0]
    range_end = max(end for _start, end in source_ranges)
    return source_line_index.lines_intersecting(range_start, range_end)


def _source_positions_overlap(
    source_positions: Sequence[int],
    source_ranges: tuple[tuple[int, int], ...],
) -> bool:
    """Return whether any source position belongs to the supplied ranges."""

    if len(source_ranges) == 1:
        start, end = source_ranges[0]
        return any(start <= position < end for position in source_positions)
    return any(
        start <= position < end
        for position in source_positions
        for start, end in source_ranges
    )


def _source_position_chunks(
    source_positions: Sequence[int],
    *,
    source_ranges: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    """Return contiguous fragment-local chunks owned by supplied source ranges."""

    if not source_ranges:
        return ()
    if len(source_ranges) == 1:
        start, end = source_ranges[0]
        return _single_source_range_chunks(
            source_positions,
            range_start=start,
            range_end=end,
        )
    chunks: list[tuple[int, int]] = []
    chunk_start: int | None = None
    for index, source_position in enumerate(source_positions):
        owned = any(start <= source_position < end for start, end in source_ranges)
        if owned and chunk_start is None:
            chunk_start = index
        elif not owned and chunk_start is not None:
            chunks.append((chunk_start, index))
            chunk_start = None
    if chunk_start is not None:
        chunks.append((chunk_start, len(source_positions)))
    return tuple(chunks)


def _single_source_range_chunks(
    source_positions: Sequence[int],
    *,
    range_start: int,
    range_end: int,
) -> tuple[tuple[int, int], ...]:
    """Return owned chunks using the common single-range fast path."""

    chunks: list[tuple[int, int]] = []
    chunk_start: int | None = None
    for index, source_position in enumerate(source_positions):
        owned = range_start <= source_position < range_end
        if owned and chunk_start is None:
            chunk_start = index
        elif not owned and chunk_start is not None:
            chunks.append((chunk_start, index))
            chunk_start = None
    if chunk_start is not None:
        chunks.append((chunk_start, len(source_positions)))
    return tuple(chunks)


__all__ = ["PromptReorderPaintSnapshotBuilder"]
