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

"""Verify prompt-safe reorder geometry-cache identity and reuse."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPainterPath

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderRowView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
    PromptReorderChipLineGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry_cache import (
    PromptReorderChipGeometryCache,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_visual_identity import (
    chip_geometry_visual_reuse_key,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry_cache_keys import (
    PromptReorderChipGeometryCacheKey,
    reorder_chip_geometry_cache_key,
    reorder_geometry_viewport_key,
    reorder_live_chip_geometry_cache_key,
    reorder_layout_geometry_key,
    reorder_placement_geometry_cache_key,
    reorder_snapshot_geometry_key,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry_diagnostics import (
    reorder_geometry_cache_context,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry_metrics import (
    PromptReorderGeometryMetrics,
)


def _snapshot(text: str = "alpha, beta") -> PromptReorderPreviewSnapshot:
    """Return one deterministic application reorder preview snapshot."""

    return PromptReorderPreviewSnapshot(
        text=text,
        chip_ranges_by_index={0: (0, 6), 1: (7, 11)},
        chip_rendered_ranges_by_index={0: (0, 6), 1: (7, 11)},
        chip_owned_ranges_by_index={0: ((0, 6),), 1: ((7, 11),)},
        gap_ranges_by_index={2: (12, 13)},
    )


def _layout_view() -> PromptReorderLayoutView:
    """Return one deterministic reorder layout view."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1)),),
        gaps=(
            PromptReorderGapView(
                gap_index=2,
                separator_text="\n",
                blank_line_count=1,
                placement=PromptReorderGapPlacement.AFTER_LAST_ROW,
            ),
        ),
    )


def _chip_geometry(
    *,
    chip_index: int = 0,
    source_start: int = 0,
    visual_left: int = 4,
    visual_revision: int = 1,
) -> PromptReorderChipGeometry:
    """Return one deterministic chip geometry for cache policy tests."""

    content_rect = QRectF(float(visual_left), 2.0, 40.0, 18.0)
    path = QPainterPath()
    path.addRect(content_rect)
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=chip_index,
            visual_revision=visual_revision,
        ),
        chip_index=chip_index,
        source_start=source_start,
        source_end=source_start + 5,
        rendered_start=source_start,
        rendered_end=source_start + 5,
        visual_lines=(
            PromptReorderChipLineGeometry(
                visual_line_index=0,
                line_rect=QRectF(0.0, 0.0, 100.0, 24.0),
                content_rect=content_rect,
                leading_anchor=QPointF(float(visual_left), 12.0),
                trailing_anchor=QPointF(float(visual_left + 40), 12.0),
            ),
        ),
        hotspot_rect=QRect(visual_left, 2, 40, 18),
        chrome_path=path,
        outline_bounds=content_rect,
        slot_before=QPointF(float(visual_left), 12.0),
        slot_after=QPointF(float(visual_left + 40), 12.0),
        marker_height=18.0,
    )


def test_reorder_snapshot_geometry_key_changes_with_semantic_inputs() -> None:
    """Snapshot cache identity should change when prompt semantics change."""

    first = reorder_snapshot_geometry_key(_snapshot())
    second = reorder_snapshot_geometry_key(_snapshot("alpha, gamma"))

    assert first == reorder_snapshot_geometry_key(_snapshot())
    assert first != second


def test_reorder_viewport_geometry_key_changes_with_view_inputs() -> None:
    """Viewport cache identity should include scroll and layout dimensions."""

    first = reorder_geometry_viewport_key(
        viewport_rect=QRectF(0.0, 0.0, 100.0, 50.0),
        scroll_offset=0.0,
        layout_width=100.0,
    )
    scrolled = reorder_geometry_viewport_key(
        viewport_rect=QRectF(0.0, 0.0, 100.0, 50.0),
        scroll_offset=8.0,
        layout_width=100.0,
    )
    resized = reorder_geometry_viewport_key(
        viewport_rect=QRectF(0.0, 0.0, 120.0, 50.0),
        scroll_offset=0.0,
        layout_width=120.0,
    )

    assert first != scrolled
    assert first != resized


def test_reorder_layout_geometry_key_includes_projection_layout_identity() -> None:
    """Visual layout identity should invalidate otherwise identical layout views."""

    layout_view = _layout_view()

    first = reorder_layout_geometry_key(layout_view, projection_layout_identity=1)
    second = reorder_layout_geometry_key(layout_view, projection_layout_identity=2)

    assert first != second


def test_reorder_geometry_cache_context_does_not_log_prompt_text() -> None:
    """Cache diagnostics should expose hashes and counts, not raw prompt text."""

    cache_key = reorder_chip_geometry_cache_key(
        snapshot=_snapshot("sensitive prompt text"),
        layout_view=_layout_view(),
        projection_layout_identity=1,
        viewport_rect=QRectF(0.0, 0.0, 100.0, 50.0),
        scroll_offset=0.0,
        layout_width=100.0,
    )

    context = reorder_geometry_cache_context(cache_key)

    assert context["geometry_cache_text_length"] == len("sensitive prompt text")
    assert "sensitive prompt text" not in " ".join(
        str(value) for value in context.values()
    )


def test_reorder_cache_keys_exclude_placement_gaps_from_chip_geometry() -> None:
    """Placement gaps should not invalidate otherwise exact chip geometry."""

    snapshot = _snapshot()
    layout_view = _layout_view()
    viewport_rect = QRectF(0.0, 0.0, 100.0, 50.0)

    chip_key = reorder_chip_geometry_cache_key(
        snapshot=snapshot,
        layout_view=layout_view,
        projection_layout_identity=1,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
        layout_width=100.0,
    )
    placement_key = reorder_placement_geometry_cache_key(
        snapshot=snapshot,
        layout_view=layout_view,
        projection_layout_identity=1,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
        layout_width=100.0,
    )

    changed_gaps = replace(snapshot, gap_ranges_by_index={9: (20, 21)})
    changed_chip_key = reorder_chip_geometry_cache_key(
        snapshot=changed_gaps,
        layout_view=layout_view,
        projection_layout_identity=1,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
        layout_width=100.0,
    )
    changed_placement_key = reorder_placement_geometry_cache_key(
        snapshot=changed_gaps,
        layout_view=layout_view,
        projection_layout_identity=1,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
        layout_width=100.0,
    )

    assert chip_key.snapshot.gap_ranges == ()
    assert placement_key.snapshot.gap_ranges == ((2, 12, 13),)
    assert changed_chip_key == chip_key
    assert changed_placement_key != placement_key
    assert chip_key.layout == placement_key.layout
    assert chip_key.viewport == placement_key.viewport
    assert chip_key != reorder_chip_geometry_cache_key(
        snapshot=snapshot,
        layout_view=layout_view,
        projection_layout_identity=2,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
        layout_width=100.0,
    )


def test_chip_geometry_visual_reuse_key_tracks_visual_inputs() -> None:
    """Per-chip visual reuse identity should reject changed visual geometry."""

    first = _chip_geometry()
    same = _chip_geometry()
    shifted = _chip_geometry(visual_left=8)
    revised = _chip_geometry(visual_revision=2)

    assert chip_geometry_visual_reuse_key(first) == chip_geometry_visual_reuse_key(same)
    assert chip_geometry_visual_reuse_key(first) != chip_geometry_visual_reuse_key(
        shifted
    )
    assert chip_geometry_visual_reuse_key(first) != chip_geometry_visual_reuse_key(
        revised
    )


def test_reorder_cache_reuses_preview_chip_geometry_by_visual_identity() -> None:
    """Preview geometry cache should reuse equal immutable chip geometries."""

    metrics = PromptReorderGeometryMetrics()
    cache = PromptReorderChipGeometryCache(metrics=metrics)
    cached_geometry = _chip_geometry()
    cached_snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={0: cached_geometry},
        ordered_chip_indices=(0,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=24.0,
        scroll_offset=0.0,
    )
    cache.store_preview(
        key=reorder_chip_geometry_cache_key(
            snapshot=_snapshot(),
            layout_view=_layout_view(),
            projection_layout_identity=1,
            viewport_rect=QRectF(0.0, 0.0, 100.0, 50.0),
            scroll_offset=0.0,
            layout_width=100.0,
        ),
        snapshot=cached_snapshot,
    )
    incoming_snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={0: _chip_geometry()},
        ordered_chip_indices=(0,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=24.0,
        scroll_offset=0.0,
    )

    reused_snapshot, reused_count, rebuilt_count, rejected_count = (
        cache.reuse_preview_geometries(incoming_snapshot)
    )

    assert reused_snapshot.geometries_by_chip_index[0] is cached_geometry
    assert reused_count == 1
    assert rebuilt_count == 0
    assert rejected_count == 0


def test_reorder_cache_reuses_live_geometry_for_exact_viewport() -> None:
    """Live geometry should remain authoritative while its full key is unchanged."""

    metrics = PromptReorderGeometryMetrics()
    cache = PromptReorderChipGeometryCache(metrics=metrics)
    key = reorder_live_chip_geometry_cache_key(
        source_text="alpha, beta",
        chip_rendered_ranges_by_index={0: (0, 6), 1: (7, 11)},
        chip_owned_ranges_by_index={0: ((0, 6),), 1: ((7, 11),)},
        layout_view=_layout_view(),
        projection_layout_identity=1,
        viewport_rect=QRectF(0.0, 0.0, 100.0, 50.0),
        scroll_offset=0.0,
        layout_width=100.0,
    )
    snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={0: _chip_geometry()},
        ordered_chip_indices=(0,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=24.0,
        scroll_offset=0.0,
    )

    cache.store_live(key=key, snapshot=snapshot)

    assert cache.live(key) is snapshot
    assert metrics.snapshot()["live_chip_geometry_cache_hit_count"] == 1


def test_reorder_cache_shares_exact_live_geometry_with_initial_preview() -> None:
    """An unchanged initial preview should not rebuild authoritative live geometry."""

    metrics = PromptReorderGeometryMetrics()
    cache = PromptReorderChipGeometryCache(metrics=metrics)
    snapshot = _snapshot()
    viewport_rect = QRectF(0.0, 0.0, 100.0, 50.0)
    live_key = reorder_live_chip_geometry_cache_key(
        source_text=snapshot.text,
        chip_rendered_ranges_by_index=snapshot.chip_rendered_ranges_by_index,
        chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
        layout_view=_layout_view(),
        projection_layout_identity=1,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
        layout_width=100.0,
    )
    preview_key = reorder_chip_geometry_cache_key(
        snapshot=snapshot,
        layout_view=_layout_view(),
        projection_layout_identity=1,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
        layout_width=100.0,
    )
    geometry_snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={0: _chip_geometry()},
        ordered_chip_indices=(0,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=24.0,
        scroll_offset=0.0,
    )

    cache.store_live(key=live_key, snapshot=geometry_snapshot)

    assert preview_key == live_key
    assert cache.preview(preview_key) is geometry_snapshot
    assert metrics.snapshot()["preview_chip_geometry_live_reuse_count"] == 1


def test_reorder_cache_shares_exact_preview_geometry_with_drag_base() -> None:
    """Equal preview and base projections should own one chip geometry snapshot."""

    metrics = PromptReorderGeometryMetrics()
    cache = PromptReorderChipGeometryCache(metrics=metrics)
    key = reorder_chip_geometry_cache_key(
        snapshot=_snapshot(),
        layout_view=_layout_view(),
        projection_layout_identity=1,
        viewport_rect=QRectF(0.0, 0.0, 100.0, 50.0),
        scroll_offset=0.0,
        layout_width=100.0,
    )
    geometry_snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={0: _chip_geometry()},
        ordered_chip_indices=(0,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=24.0,
        scroll_offset=0.0,
    )

    cache.store_preview(key=key, snapshot=geometry_snapshot)

    assert cache.base_drag(key) is geometry_snapshot
    cache.clear_preview(reason="test")
    assert cache.base_drag(key) is geometry_snapshot
    counters = metrics.snapshot()
    assert counters["base_chip_geometry_cache_hit_count"] == 2
    assert counters["base_chip_geometry_preview_reuse_count"] == 1
    assert counters["base_chip_geometry_cache_miss_count"] == 0


def test_reorder_cache_offers_live_geometry_when_only_scroll_changes() -> None:
    """Live scroll reuse should reject semantic changes but accept a new offset."""

    metrics = PromptReorderGeometryMetrics()
    cache = PromptReorderChipGeometryCache(metrics=metrics)

    def cache_key(
        *, source_text: str, scroll_offset: float
    ) -> PromptReorderChipGeometryCacheKey:
        """Build one live cache key for this policy test."""

        return reorder_live_chip_geometry_cache_key(
            source_text=source_text,
            chip_rendered_ranges_by_index={0: (0, 6), 1: (7, 11)},
            chip_owned_ranges_by_index={0: ((0, 6),), 1: ((7, 11),)},
            layout_view=_layout_view(),
            projection_layout_identity=1,
            viewport_rect=QRectF(0.0, 0.0, 100.0, 50.0),
            scroll_offset=scroll_offset,
            layout_width=100.0,
        )

    initial_key = cache_key(source_text="alpha, beta", scroll_offset=0.0)
    snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={0: _chip_geometry()},
        ordered_chip_indices=(0,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=24.0,
        scroll_offset=0.0,
    )
    cache.store_live(key=initial_key, snapshot=snapshot)

    scrolled_key = cache_key(source_text="alpha, beta", scroll_offset=24.0)
    changed_key = cache_key(source_text="alpha, gamma", scroll_offset=24.0)

    assert cache.live_scroll_candidate(scrolled_key) == (initial_key, snapshot)
    assert cache.live_scroll_candidate(changed_key) is None
