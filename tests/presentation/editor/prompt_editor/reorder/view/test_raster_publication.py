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

"""Verify prompt reorder raster publication contracts."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_raster_cache import (
    PromptReorderRasterCache,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_raster_publication import (
    PromptReorderRasterPublicationOwner,
)

from .support import (
    _style,
    _visual,
    _projection_snapshot,
)


def test_reorder_raster_cache_hits_moved_chips_and_rejects_stale_dpr() -> None:
    """Raster cache identity should include content and DPR, not absolute position."""

    if QApplication.instance() is None:
        QApplication([])
    cache = PromptReorderRasterCache()
    visual = _visual(80.0)
    snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=visual,
        projection_snapshot=_projection_snapshot(0, left=80.0),
    )
    moved_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=_visual(120.0),
        projection_snapshot=_projection_snapshot(
            0,
            left=120.0,
            preview_generation=99,
            geometry_generation=100,
        ),
    )
    style = _style().paint_style_for_segment(
        0,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
    )

    first = cache.entries_for_snapshots(
        snapshots_by_index={0: snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    second = cache.entries_for_snapshots(
        snapshots_by_index={0: moved_snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    third = cache.entries_for_snapshots(
        snapshots_by_index={0: snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=2.0,
    )
    counters = cache.counters().as_dict()

    assert first[0] is second[0]
    assert third[0] is not second[0]
    assert counters["raster_cache_miss_count"] == 1
    assert counters["raster_cache_hit_count"] == 1
    assert counters["raster_cache_stale_count"] == 1
    assert counters["raster_build_count"] == 2


def test_reorder_raster_cache_retains_alternating_segment_variants() -> None:
    """Live and preview variants should coexist instead of evicting each other."""

    if QApplication.instance() is None:
        QApplication([])
    cache = PromptReorderRasterCache()
    visual = _visual(80.0)
    first_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=visual,
        projection_snapshot=_projection_snapshot(0, left=80.0),
    )
    second_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=visual,
        projection_snapshot=replace(
            _projection_snapshot(0, left=80.0),
            content_key=("second-variant",),
        ),
    )
    style = _style().paint_style_for_segment(
        0,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
    )

    first = cache.entries_for_snapshots(
        snapshots_by_index={0: first_snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    second = cache.entries_for_snapshots(
        snapshots_by_index={0: second_snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    revisited = cache.entries_for_snapshots(
        snapshots_by_index={0: first_snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    counters = cache.counters().as_dict()

    assert first[0] is revisited[0]
    assert second[0] is not first[0]
    assert counters["raster_cache_hit_count"] == 1
    assert counters["raster_cache_stale_count"] == 1
    assert counters["raster_build_count"] == 2


def test_reorder_raster_publication_owns_lane_reuse_and_warm_invalidation() -> None:
    """Publish warmed entries once and reuse one exact render-state mapping."""

    app = QApplication.instance() or QApplication([])
    parent = QObject()
    entries_changed: list[None] = []
    owner = PromptReorderRasterPublicationOwner(
        parent=parent,
        entries_changed=lambda: entries_changed.append(None),
    )
    snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=_visual(80.0),
        projection_snapshot=_projection_snapshot(0, left=80.0),
    )
    style = _style().paint_style_for_segment(
        0,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
    )

    cold = owner.entries_for(
        "live",
        snapshots_by_index={0: snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    app.processEvents()
    warm = owner.entries_for(
        "live",
        snapshots_by_index={0: snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    reused = owner.entries_for(
        "live",
        snapshots_by_index={0: snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    moved_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=_visual(120.0),
        projection_snapshot=_projection_snapshot(
            0,
            left=120.0,
            preview_generation=99,
            geometry_generation=100,
        ),
    )
    moved = owner.entries_for(
        "live",
        snapshots_by_index={0: moved_snapshot},
        styles_by_index={0: style},
        device_pixel_ratio=1.0,
    )
    counters = owner.counters().as_dict()

    assert not cold
    assert entries_changed == [None]
    assert 0 in warm
    assert reused is warm
    assert moved is not warm
    assert moved[0] is warm[0]
    assert counters["raster_entries_render_cache_miss_count"] == 3
    assert counters["raster_entries_render_cache_hit_count"] == 1
    assert counters["raster_build_count"] == 1
