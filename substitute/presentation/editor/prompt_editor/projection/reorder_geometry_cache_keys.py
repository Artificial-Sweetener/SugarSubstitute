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

"""Own complete immutable cache identity for prompt reorder geometry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
)

from .reorder_preview import PromptReorderProjectionSnapshot


@dataclass(frozen=True, slots=True)
class PromptReorderGeometryViewportKey:
    """Identify viewport inputs affecting reorder geometry positions."""

    viewport_left: int
    viewport_top: int
    viewport_width: int
    viewport_height: int
    scroll_offset: int
    layout_width_x100: int


@dataclass(frozen=True, slots=True)
class PromptReorderSnapshotGeometryKey:
    """Identify semantic snapshot inputs affecting reorder geometry."""

    text: str
    chip_rendered_ranges: tuple[tuple[int, int, int], ...]
    chip_owned_ranges: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    gap_ranges: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderLayoutGeometryKey:
    """Identify one reorder layout and projection frame instance."""

    projection_layout_identity: int
    rows: tuple[tuple[int, tuple[int, ...]], ...]
    gaps: tuple[tuple[int, int, str, str], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderChipGeometryCacheKey:
    """Identify one chip geometry cache entry."""

    snapshot: PromptReorderSnapshotGeometryKey
    layout: PromptReorderLayoutGeometryKey
    viewport: PromptReorderGeometryViewportKey


@dataclass(frozen=True, slots=True)
class PromptReorderPlacementGeometryCacheKey:
    """Identify one placement geometry cache entry."""

    snapshot: PromptReorderSnapshotGeometryKey
    layout: PromptReorderLayoutGeometryKey
    viewport: PromptReorderGeometryViewportKey


ReorderGeometrySnapshot = PromptReorderProjectionSnapshot | PromptReorderPreviewSnapshot


def reorder_chip_geometry_cache_key(
    *,
    snapshot: ReorderGeometrySnapshot,
    layout_view: PromptReorderLayoutView,
    projection_layout_identity: int,
    viewport_rect: QRectF,
    scroll_offset: float,
    layout_width: float,
) -> PromptReorderChipGeometryCacheKey:
    """Return complete identity for one projected chip snapshot."""

    return PromptReorderChipGeometryCacheKey(
        snapshot=reorder_chip_snapshot_geometry_key(snapshot),
        layout=reorder_layout_geometry_key(
            layout_view,
            projection_layout_identity=projection_layout_identity,
        ),
        viewport=reorder_geometry_viewport_key(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=layout_width,
        ),
    )


def reorder_live_chip_geometry_cache_key(
    *,
    source_text: str,
    chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
    chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    layout_view: PromptReorderLayoutView,
    projection_layout_identity: int,
    viewport_rect: QRectF,
    scroll_offset: float,
    layout_width: float,
) -> PromptReorderChipGeometryCacheKey:
    """Return complete identity for stable live chip geometry."""

    return PromptReorderChipGeometryCacheKey(
        snapshot=reorder_chip_snapshot_geometry_key_from_parts(
            source_text=source_text,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        ),
        layout=reorder_layout_geometry_key(
            layout_view,
            projection_layout_identity=projection_layout_identity,
        ),
        viewport=reorder_geometry_viewport_key(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=layout_width,
        ),
    )


def reorder_placement_geometry_cache_key(
    *,
    snapshot: ReorderGeometrySnapshot,
    layout_view: PromptReorderLayoutView,
    projection_layout_identity: int,
    viewport_rect: QRectF,
    scroll_offset: float,
    layout_width: float,
) -> PromptReorderPlacementGeometryCacheKey:
    """Return complete identity for one placement snapshot."""

    return PromptReorderPlacementGeometryCacheKey(
        snapshot=reorder_snapshot_geometry_key(snapshot),
        layout=reorder_layout_geometry_key(
            layout_view,
            projection_layout_identity=projection_layout_identity,
        ),
        viewport=reorder_geometry_viewport_key(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=layout_width,
        ),
    )


def reorder_geometry_viewport_key(
    *,
    viewport_rect: QRectF,
    scroll_offset: float,
    layout_width: float,
) -> PromptReorderGeometryViewportKey:
    """Return rounded device-independent viewport identity."""

    return PromptReorderGeometryViewportKey(
        viewport_left=int(round(viewport_rect.left())),
        viewport_top=int(round(viewport_rect.top())),
        viewport_width=int(round(viewport_rect.width())),
        viewport_height=int(round(viewport_rect.height())),
        scroll_offset=int(round(scroll_offset)),
        layout_width_x100=int(round(layout_width * 100.0)),
    )


def reorder_geometry_viewport_rect(
    viewport_key: PromptReorderGeometryViewportKey,
) -> QRectF:
    """Restore the viewport rectangle represented by one cache key."""

    return QRectF(
        viewport_key.viewport_left,
        viewport_key.viewport_top,
        viewport_key.viewport_width,
        viewport_key.viewport_height,
    )


def same_geometry_inputs_except_scroll(
    first: PromptReorderChipGeometryCacheKey,
    second: PromptReorderChipGeometryCacheKey,
) -> bool:
    """Return whether two chip keys differ only by vertical scroll."""

    first_viewport = first.viewport
    second_viewport = second.viewport
    return (
        first.snapshot == second.snapshot
        and first.layout == second.layout
        and first_viewport.viewport_left == second_viewport.viewport_left
        and first_viewport.viewport_top == second_viewport.viewport_top
        and first_viewport.viewport_width == second_viewport.viewport_width
        and first_viewport.viewport_height == second_viewport.viewport_height
        and first_viewport.layout_width_x100 == second_viewport.layout_width_x100
        and first_viewport.scroll_offset != second_viewport.scroll_offset
    )


def reorder_snapshot_geometry_key(
    snapshot: ReorderGeometrySnapshot,
) -> PromptReorderSnapshotGeometryKey:
    """Return semantic identity for either supported snapshot representation."""

    return PromptReorderSnapshotGeometryKey(
        text=_snapshot_text(snapshot),
        chip_rendered_ranges=tuple(
            sorted(
                (chip_index, range_start, range_end)
                for chip_index, (
                    range_start,
                    range_end,
                ) in snapshot.chip_rendered_ranges_by_index.items()
            )
        ),
        chip_owned_ranges=tuple(
            sorted(
                (chip_index, tuple(sorted(owned_ranges)))
                for chip_index, owned_ranges in snapshot.chip_owned_ranges_by_index.items()
            )
        ),
        gap_ranges=_sorted_ranges(snapshot.gap_ranges_by_index),
    )


def reorder_chip_snapshot_geometry_key(
    snapshot: ReorderGeometrySnapshot,
) -> PromptReorderSnapshotGeometryKey:
    """Return only snapshot inputs affecting chip geometry."""

    return reorder_chip_snapshot_geometry_key_from_parts(
        source_text=_snapshot_text(snapshot),
        chip_rendered_ranges_by_index=snapshot.chip_rendered_ranges_by_index,
        chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
    )


def reorder_chip_snapshot_geometry_key_from_parts(
    *,
    source_text: str,
    chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
    chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
) -> PromptReorderSnapshotGeometryKey:
    """Return chip identity without unrelated placement gap ranges."""

    return PromptReorderSnapshotGeometryKey(
        text=source_text,
        chip_rendered_ranges=tuple(
            sorted(
                (chip_index, range_start, range_end)
                for chip_index, (
                    range_start,
                    range_end,
                ) in chip_rendered_ranges_by_index.items()
            )
        ),
        chip_owned_ranges=tuple(
            sorted(
                (chip_index, tuple(sorted(owned_ranges)))
                for chip_index, owned_ranges in chip_owned_ranges_by_index.items()
            )
        ),
        gap_ranges=(),
    )


def reorder_layout_geometry_key(
    layout_view: PromptReorderLayoutView,
    *,
    projection_layout_identity: int,
) -> PromptReorderLayoutGeometryKey:
    """Return identity for a layout view and its projection frame."""

    return PromptReorderLayoutGeometryKey(
        projection_layout_identity=projection_layout_identity,
        rows=tuple(
            (row.row_index, tuple(row.chip_indices)) for row in layout_view.rows
        ),
        gaps=tuple(
            (
                gap.gap_index,
                gap.blank_line_count,
                gap.placement.value,
                gap.separator_text,
            )
            for gap in layout_view.gaps
        ),
    )


def _snapshot_text(snapshot: ReorderGeometrySnapshot) -> str:
    """Return source text from either snapshot representation."""

    if isinstance(snapshot, PromptReorderProjectionSnapshot):
        return snapshot.document_view.source_text
    return snapshot.text


def _sorted_ranges(
    ranges_by_index: Mapping[int, tuple[int, int]],
) -> tuple[tuple[int, int, int], ...]:
    """Return deterministic range tuples for cache identity."""

    return tuple(
        sorted(
            (range_index, range_start, range_end)
            for range_index, (
                range_start,
                range_end,
            ) in ranges_by_index.items()
        )
    )


__all__ = [
    "PromptReorderChipGeometryCacheKey",
    "PromptReorderGeometryViewportKey",
    "PromptReorderLayoutGeometryKey",
    "PromptReorderPlacementGeometryCacheKey",
    "PromptReorderSnapshotGeometryKey",
    "ReorderGeometrySnapshot",
    "reorder_chip_geometry_cache_key",
    "reorder_geometry_viewport_key",
    "reorder_geometry_viewport_rect",
    "reorder_live_chip_geometry_cache_key",
    "reorder_layout_geometry_key",
    "reorder_placement_geometry_cache_key",
    "reorder_snapshot_geometry_key",
    "same_geometry_inputs_except_scroll",
]
