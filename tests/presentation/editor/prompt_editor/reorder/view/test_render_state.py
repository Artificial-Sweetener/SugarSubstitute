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

"""Verify prompt reorder render state contracts."""

from __future__ import annotations


from PySide6.QtCore import QRect, QRectF

from substitute.presentation.editor.prompt_editor.overlays.reorder_render_state import (
    PromptReorderLandingPreviewPaintState,
    PromptReorderViewRenderInput,
    prompt_reorder_view_render_state,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
)

from .support import (
    _style,
    _visual,
    _projection_snapshot,
    _raster_entry,
)


def test_reorder_view_render_state_assembles_prepared_paint_state() -> None:
    """Render-state construction should prepare chips, marker, and landing input."""

    visual_style = _style()
    landing_preview = PromptReorderLandingPreviewPaintState(
        style=visual_style.outline_style(opacity=0.5, outline_width=1.0),
        visual=_visual(120.0),
    )

    state = prompt_reorder_view_render_state(
        PromptReorderViewRenderInput(
            visual_style=visual_style,
            preview_active=True,
            live_ordered_segment_indices=(0, 1),
            preview_ordered_segment_indices=(1, 0),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={0: _visual(0.0), 1: _visual(40.0)},
            preview_visuals_by_index={0: _visual(80.0), 1: _visual(120.0)},
            dragged_segment_index=1,
            hovered_segment_index=None,
            active_segment_index=0,
            marker_rect=QRectF(10.0, 20.0, 4.0, 16.0),
            landing_preview=landing_preview,
            gesture_id=7,
            event_id=9,
        )
    )

    assert state.preview_active is True
    assert state.live_chips == ()
    assert [chip.segment_index for chip in state.preview_chips] == [0]
    assert state.marker is not None
    assert state.marker.rect == QRectF(10.0, 20.0, 4.0, 16.0)
    assert state.marker.color == visual_style.marker_color
    assert state.landing_preview is landing_preview
    assert state.gesture_id == 7
    assert state.event_id == 9


def test_reorder_view_render_state_uses_animation_paint_rect_overrides() -> None:
    """Animated chips should paint at presenter rects before final geometry settles."""

    state = prompt_reorder_view_render_state(
        PromptReorderViewRenderInput(
            visual_style=_style(),
            preview_active=True,
            live_ordered_segment_indices=(0,),
            preview_ordered_segment_indices=(0,),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={0: _visual(0.0)},
            preview_visuals_by_index={0: _visual(80.0)},
            dragged_segment_index=None,
            hovered_segment_index=None,
            active_segment_index=None,
            paint_rect_overrides_by_index={0: QRectF(12.0, 6.0, 40.0, 22.0)},
        )
    )

    assert len(state.preview_chips) == 1
    animated_chip = state.preview_chips[0]
    assert animated_chip.geometry is None
    assert animated_chip.visual is not None
    assert animated_chip.visual.hotspot_rect == QRect(12, 6, 40, 22)
    assert animated_chip.visual.bubble_rects[0].left() == 12.0
    assert animated_chip.visual.bubble_rects[0].top() == 10.0


def test_reorder_view_render_state_keeps_visual_snapshot_with_animation_override() -> (
    None
):
    """Animated chips should retain text snapshots while their visual rect changes."""

    base_visual = _visual(80.0)
    visual_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=base_visual,
        projection_snapshot=_projection_snapshot(0),
    )

    state = prompt_reorder_view_render_state(
        PromptReorderViewRenderInput(
            visual_style=_style(),
            preview_active=True,
            live_ordered_segment_indices=(0,),
            preview_ordered_segment_indices=(0,),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={0: _visual(0.0)},
            preview_visuals_by_index={0: base_visual},
            dragged_segment_index=None,
            hovered_segment_index=None,
            active_segment_index=None,
            preview_visual_snapshots_by_index={0: visual_snapshot},
            paint_rect_overrides_by_index={0: QRectF(12.0, 6.0, 40.0, 22.0)},
        )
    )

    assert len(state.preview_chips) == 1
    animated_chip = state.preview_chips[0]
    assert animated_chip.visual is not None
    assert animated_chip.visual.hotspot_rect == QRect(12, 6, 40, 22)
    assert animated_chip.visual_snapshot is visual_snapshot


def test_reorder_view_render_state_keeps_raster_with_animation_override() -> None:
    """Animated chips should carry complete-chip rasters with translated visuals."""

    raster_entry = _raster_entry()

    state = prompt_reorder_view_render_state(
        PromptReorderViewRenderInput(
            visual_style=_style(),
            preview_active=True,
            live_ordered_segment_indices=(0,),
            preview_ordered_segment_indices=(0,),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={0: _visual(0.0)},
            preview_visuals_by_index={0: _visual(80.0)},
            dragged_segment_index=None,
            hovered_segment_index=None,
            active_segment_index=None,
            preview_raster_entries_by_index={0: raster_entry},
            paint_rect_overrides_by_index={0: QRectF(12.0, 6.0, 40.0, 22.0)},
        )
    )

    assert len(state.preview_chips) == 1
    animated_chip = state.preview_chips[0]
    assert animated_chip.visual is not None
    assert animated_chip.visual.hotspot_rect == QRect(12, 6, 40, 22)
    assert animated_chip.raster_entry is raster_entry
    assert state.raster_paint_count == 1


def test_reorder_chip_empty_projection_snapshot_does_not_own_surface_text() -> None:
    """A chrome-only snapshot must not suppress the surface's projected text."""

    visual = _visual(80.0)
    empty_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=visual,
        projection_snapshot=_projection_snapshot(0, text=""),
    )
    state = prompt_reorder_view_render_state(
        PromptReorderViewRenderInput(
            visual_style=_style(),
            preview_active=True,
            live_ordered_segment_indices=(0,),
            preview_ordered_segment_indices=(0,),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={},
            preview_visuals_by_index={0: visual},
            dragged_segment_index=None,
            hovered_segment_index=None,
            active_segment_index=None,
            preview_visual_snapshots_by_index={0: empty_snapshot},
        )
    )

    assert len(state.preview_chips) == 1
    assert state.preview_chips[0].owns_projection_text is False
