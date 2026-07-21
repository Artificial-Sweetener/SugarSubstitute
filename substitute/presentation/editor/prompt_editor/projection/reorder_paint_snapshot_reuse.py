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

"""Reuse immutable reorder paint snapshots across exact and scroll-only refreshes."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF

from .reorder_visual_snapshot import (
    PromptReorderInlineObjectPaintFragment,
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
    PromptReorderTextPaintFragment,
)


@dataclass(frozen=True, slots=True)
class PromptReorderPaintSnapshotReuseResult:
    """Carry reusable snapshots and keys that still require exact extraction."""

    snapshots_by_chip_index: dict[int, PromptReorderProjectionPaintSnapshot]
    rebuild_keys_by_chip_index: dict[int, PromptReorderProjectionSnapshotKey]
    exact_reuse_count: int
    scroll_reuse_count: int


def reuse_reorder_paint_snapshots(
    keys_by_chip_index: dict[int, PromptReorderProjectionSnapshotKey],
    *,
    previous_snapshots_by_chip_index: dict[
        int,
        PromptReorderProjectionPaintSnapshot,
    ],
) -> PromptReorderPaintSnapshotReuseResult:
    """Reuse exact or safely translatable snapshots and identify rebuilds."""

    reused: dict[int, PromptReorderProjectionPaintSnapshot] = {}
    rebuild: dict[int, PromptReorderProjectionSnapshotKey] = {}
    exact_count = 0
    scroll_count = 0
    for chip_index, key in keys_by_chip_index.items():
        previous = previous_snapshots_by_chip_index.get(chip_index)
        if previous is None:
            rebuild[chip_index] = key
            continue
        if previous.key == key:
            reused[chip_index] = previous
            exact_count += 1
            continue
        if not _can_translate_snapshot(previous, key=key):
            rebuild[chip_index] = key
            continue
        vertical_delta = float(previous.key.scroll_offset - key.scroll_offset)
        reused[chip_index] = _translated_snapshot(
            previous,
            key=key,
            vertical_delta=vertical_delta,
        )
        scroll_count += 1
    return PromptReorderPaintSnapshotReuseResult(
        snapshots_by_chip_index=reused,
        rebuild_keys_by_chip_index=rebuild,
        exact_reuse_count=exact_count,
        scroll_reuse_count=scroll_count,
    )


def _can_translate_snapshot(
    snapshot: PromptReorderProjectionPaintSnapshot,
    *,
    key: PromptReorderProjectionSnapshotKey,
) -> bool:
    """Return whether only scroll changed and the old fragments were not clipped."""

    previous_key = snapshot.key
    if (
        previous_key.source_revision != key.source_revision
        or previous_key.viewport_rect != key.viewport_rect
        or previous_key.font_key != key.font_key
        or previous_key.palette_key != key.palette_key
        or previous_key.preview_generation != key.preview_generation
        or previous_key.segment_index != key.segment_index
        or previous_key.mode != key.mode
        or previous_key.scroll_offset == key.scroll_offset
    ):
        return False
    viewport_rect = QRectF(previous_key.viewport_rect)
    return bool(snapshot.viewport_rects) and all(
        rect.top() > viewport_rect.top() and rect.bottom() < viewport_rect.bottom()
        for rect in snapshot.viewport_rects
    )


def _translated_snapshot(
    snapshot: PromptReorderProjectionPaintSnapshot,
    *,
    key: PromptReorderProjectionSnapshotKey,
    vertical_delta: float,
) -> PromptReorderProjectionPaintSnapshot:
    """Return one paint snapshot translated by a pure viewport scroll delta."""

    translated_fragments = tuple(
        PromptReorderTextPaintFragment(
            text=fragment.text,
            font=fragment.font,
            baseline=fragment.baseline + QPointF(0.0, vertical_delta),
            text_rect=fragment.text_rect.translated(0.0, vertical_delta),
            color=fragment.color,
        )
        if isinstance(fragment, PromptReorderTextPaintFragment)
        else PromptReorderInlineObjectPaintFragment(
            renderer=fragment.renderer,
            rect=fragment.rect.translated(0.0, vertical_delta),
            run=fragment.run,
            token=fragment.token,
            base_font=fragment.base_font,
            palette=fragment.palette,
        )
        for fragment in snapshot.fragments
    )
    return PromptReorderProjectionPaintSnapshot(
        key=key,
        fragments=translated_fragments,
        source_ranges=snapshot.source_ranges,
        content_key=snapshot.content_key,
    )


__all__ = [
    "PromptReorderPaintSnapshotReuseResult",
    "reuse_reorder_paint_snapshots",
]
