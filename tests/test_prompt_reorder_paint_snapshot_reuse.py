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

"""Cover bounded reorder paint reuse across exact and scroll-only refreshes."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QColor, QFont

from substitute.presentation.editor.prompt_editor.projection.reorder_paint_snapshot_reuse import (
    reuse_reorder_paint_snapshots,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
    PromptReorderTextPaintFragment,
)


def test_reorder_paint_snapshot_reuse_translates_unclipped_scroll_content() -> None:
    """Interior fragments should translate while preserving immutable content identity."""

    previous = _snapshot(scroll_offset=0, top=20.0)
    next_key = _key(scroll_offset=8)

    result = reuse_reorder_paint_snapshots(
        {0: next_key},
        previous_snapshots_by_chip_index={0: previous},
    )

    translated = result.snapshots_by_chip_index[0]
    assert result.scroll_reuse_count == 1
    assert result.rebuild_keys_by_chip_index == {}
    assert translated.content_key is previous.content_key
    assert translated.text_fragments[0].text_rect.top() == 12.0
    assert translated.text_fragments[0].baseline.y() == 24.0


def test_reorder_paint_snapshot_reuse_rebuilds_viewport_edge_content() -> None:
    """A clipped edge fragment should be rebuilt against the current viewport."""

    previous = _snapshot(scroll_offset=0, top=0.0)
    next_key = _key(scroll_offset=8)

    result = reuse_reorder_paint_snapshots(
        {0: next_key},
        previous_snapshots_by_chip_index={0: previous},
    )

    assert result.snapshots_by_chip_index == {}
    assert result.rebuild_keys_by_chip_index == {0: next_key}
    assert result.scroll_reuse_count == 0


def _key(*, scroll_offset: int) -> PromptReorderProjectionSnapshotKey:
    """Return one deterministic preview paint key."""

    return PromptReorderProjectionSnapshotKey(
        source_revision=1,
        viewport_rect=QRect(0, 0, 200, 100),
        scroll_offset=scroll_offset,
        font_key="font",
        palette_key=2,
        preview_generation=3,
        geometry_generation=4,
        segment_index=0,
        mode="preview",
    )


def _snapshot(
    *,
    scroll_offset: int,
    top: float,
) -> PromptReorderProjectionPaintSnapshot:
    """Return one deterministic text-only paint snapshot."""

    content_key = ("content",)
    return PromptReorderProjectionPaintSnapshot(
        key=_key(scroll_offset=scroll_offset),
        fragments=(
            PromptReorderTextPaintFragment(
                text="alpha",
                font=QFont(),
                baseline=QPointF(4.0, top + 12.0),
                text_rect=QRectF(4.0, top, 30.0, 14.0),
                color=QColor(10, 20, 30),
            ),
        ),
        source_ranges=((0, 5),),
        content_key=content_key,
    )
