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

"""Cover prompt reorder view render-state construction ownership."""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar, cast

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPaintEvent, QPixmap
from PySide6.QtWidgets import QApplication
from pytest import MonkeyPatch

import substitute.presentation.editor.prompt_editor.overlays.reorder_view as reorder_view_module
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_painter import (
    PromptChipPainter,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_view import (
    PromptReorderLandingPreviewPaintState,
    PromptReorderMarkerPaintState,
    PromptReorderView,
    PromptReorderViewRenderState,
    PromptReorderViewRenderInput,
    PromptReorderVisualStyle,
    prompt_reorder_chip_paint_states,
    prompt_reorder_chip_interaction_state,
    prompt_reorder_chip_interaction_states,
    prompt_reorder_view_render_state,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_raster_cache import (
    PromptReorderRasterCache,
    ReorderRasterEntry,
    ReorderRasterKey,
    ReorderRasterStyleKey,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
    PromptReorderTextPaintFragment,
    reorder_projection_paint_content_key,
)


def _style() -> PromptReorderVisualStyle:
    """Return a reorder visual style with state-distinct colors."""

    return PromptReorderVisualStyle(
        rest_fill=QColor(10, 10, 10, 10),
        rest_border=QColor(20, 20, 20, 20),
        hover_fill=QColor(30, 30, 30, 30),
        hover_border=QColor(40, 40, 40, 40),
        active_fill=QColor(50, 50, 50, 50),
        active_border=QColor(60, 60, 60, 60),
        drag_fill=QColor(70, 70, 70, 70),
        drag_border=QColor(80, 80, 80, 80),
        marker_color=QColor(90, 90, 90, 90),
    )


def _visual(left: float) -> PromptChipVisual:
    """Return one deterministic chip visual for render-state tests."""

    bubble = QRectF(left, 4.0, 30.0, 14.0)
    return PromptChipVisual(
        bubble_rects=(bubble,),
        fragment_union_rect=QRectF(bubble),
        hotspot_rect=QRect(int(left), 0, 40, 22),
        slot_before=QPointF(bubble.left(), bubble.center().y()),
        slot_after=QPointF(bubble.right(), bubble.center().y()),
        marker_height=bubble.height(),
    )


def test_reorder_visual_style_reuses_prepared_interaction_styles() -> None:
    """Repeated state mapping should not reconstruct equivalent Qt colors."""

    visual_style = _style()

    first_rest = visual_style.paint_style_for_segment(
        0,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
    )
    second_rest = visual_style.paint_style_for_segment(
        1,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
    )
    dragged = visual_style.paint_style_for_segment(
        1,
        dragged_segment_index=1,
        hovered_segment_index=None,
        active_segment_index=None,
    )

    assert first_rest is second_rest
    assert dragged is not first_rest
    assert dragged.fill_color == visual_style.drag_fill
    assert dragged.border_color == visual_style.drag_border


def _projection_snapshot(
    segment_index: int,
    *,
    left: float = 80.0,
    text: str = "alpha",
    preview_generation: int | None = 2,
    geometry_generation: int = 3,
) -> PromptReorderProjectionPaintSnapshot:
    """Return a deterministic projection paint snapshot for render-state tests."""

    fragments = (
        ()
        if not text
        else (
            PromptReorderTextPaintFragment(
                text=text,
                font=QFont(),
                baseline=QPointF(left + 4.0, 16.0),
                text_rect=QRectF(left + 4.0, 4.0, max(1.0, len(text) * 6.0), 14.0),
                color=QColor(10, 20, 30),
            ),
        )
    )
    return PromptReorderProjectionPaintSnapshot(
        key=PromptReorderProjectionSnapshotKey(
            source_revision=1,
            viewport_rect=QRect(0, 0, 300, 120),
            scroll_offset=0,
            font_key="test-font",
            palette_key=1,
            preview_generation=preview_generation,
            geometry_generation=geometry_generation,
            segment_index=segment_index,
            mode="preview",
        ),
        fragments=fragments,
        source_ranges=() if not text else ((0, len(text)),),
        content_key=reorder_projection_paint_content_key(fragments),
    )


def _raster_entry(
    *,
    segment_index: int = 0,
    left: float = 80.0,
) -> ReorderRasterEntry:
    """Return one deterministic raster entry for render-state tests."""

    if QApplication.instance() is None:
        QApplication([])
    logical_rect = QRectF(left, 0.0, 40.0, 22.0)
    return ReorderRasterEntry(
        key=ReorderRasterKey(
            content_key="test",
            device_pixel_ratio=1.0,
            style_key=ReorderRasterStyleKey(
                fill_rgba=1,
                border_rgba=2,
                outline_only=False,
                outline_width=1.0,
                opacity=1.0,
            ),
        ),
        segment_index=segment_index,
        pixmap=QPixmap(46, 28),
        logical_rect=logical_rect,
        raster_rect=QRectF(left - 3.0, -3.0, 46.0, 28.0),
    )


def test_chip_paint_states_map_visual_state_to_styles() -> None:
    """Chip paint construction should apply active, dragged, and hovered styles."""

    visual_style = _style()
    states = prompt_reorder_chip_paint_states(
        (0, 1, 2),
        geometries_by_index={},
        visuals_by_index={0: _visual(0.0), 1: _visual(40.0), 2: _visual(80.0)},
        visual_style=visual_style,
        dragged_segment_index=1,
        hovered_segment_index=2,
        active_segment_index=0,
        skip_dragged_segment=False,
    )

    assert [state.segment_index for state in states] == [0, 1, 2]
    assert states[0].style.fill_color == visual_style.active_fill
    assert states[1].style.fill_color == visual_style.drag_fill
    assert states[2].style.fill_color == visual_style.hover_fill


def test_preview_chip_paint_states_skip_dragged_segment() -> None:
    """Preview paint state should omit the lifted chip while preserving order."""

    states = prompt_reorder_chip_paint_states(
        (2, 1, 0),
        geometries_by_index={},
        visuals_by_index={0: _visual(0.0), 1: _visual(40.0), 2: _visual(80.0)},
        visual_style=_style(),
        dragged_segment_index=1,
        hovered_segment_index=None,
        active_segment_index=None,
        skip_dragged_segment=True,
    )

    assert [state.segment_index for state in states] == [2, 0]


def test_reorder_overlay_prefers_readable_proxy_text_on_dark_surfaces() -> None:
    """Drag proxy text falls back to a readable tone when the palette lies."""

    dark_surface = QColor(22, 24, 27)
    unreadable_preferred = QColor(0, 0, 0)

    resolved = reorder_view_module._readable_surface_text_color(
        preferred=unreadable_preferred,
        background=dark_surface,
    )

    assert resolved != unreadable_preferred
    assert reorder_view_module._contrast_ratio(resolved, dark_surface) >= 4.5


def test_chip_interaction_state_maps_overlay_properties_and_cursor() -> None:
    """Interaction state construction should leave mutation to the overlay caller."""

    visual_style = _style()
    pressed = prompt_reorder_chip_interaction_state(
        3,
        visual_style=visual_style,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
        pressed_segment_index=3,
    )
    hovered = prompt_reorder_chip_interaction_state(
        4,
        visual_style=visual_style,
        dragged_segment_index=None,
        hovered_segment_index=4,
        active_segment_index=None,
        pressed_segment_index=None,
    )

    assert pressed.pressed is True
    assert pressed.cursor_shape == Qt.CursorShape.ClosedHandCursor
    assert hovered.hovered is True
    assert hovered.cursor_shape == Qt.CursorShape.OpenHandCursor
    assert hovered.style.fill_color == visual_style.hover_fill


def test_chip_interaction_states_preserve_segment_index_order() -> None:
    """Interaction-state batches should follow the overlay-owned chip order."""

    states = prompt_reorder_chip_interaction_states(
        (4, 2),
        visual_style=_style(),
        dragged_segment_index=2,
        hovered_segment_index=None,
        active_segment_index=4,
        pressed_segment_index=None,
    )

    assert [state.segment_index for state in states] == [4, 2]
    assert states[0].active is True
    assert states[1].dragging is True


def test_reorder_view_is_editor_backed_overlay_paint_surface() -> None:
    """Reorder animation keeps parent text visible below transparent chrome."""

    if QApplication.instance() is None:
        QApplication([])
    view = PromptReorderView()

    assert not view.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert view.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert view.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not view.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert view.mask().isEmpty()


def test_reorder_view_paint_clips_to_owned_region_without_background_fill(
    monkeypatch: MonkeyPatch,
) -> None:
    """Painting should draw only owned chrome instead of filling row rectangles."""

    class _FakeRenderHint:
        """Expose the painter render hints used by the view."""

        Antialiasing = "antialiasing"

    class _FakePainter:
        """Record reorder view painter calls without touching the window system."""

        RenderHint = _FakeRenderHint
        instances: ClassVar[list["_FakePainter"]] = []

        def __init__(self, widget: object) -> None:
            """Record the widget being painted."""

            self.widget = widget
            self.calls: list[tuple[str, object, object | None]] = []
            _FakePainter.instances.append(self)

        def setClipRegion(self, region: object) -> None:
            """Record paint clipping."""

            self.calls.append(("setClipRegion", region, None))

        def setRenderHint(self, hint: object, enabled: bool) -> None:
            """Record render hint changes."""

            self.calls.append(("setRenderHint", hint, enabled))

        def setBrush(self, brush: object) -> None:
            """Record brush changes."""

            self.calls.append(("setBrush", brush, None))

        def setPen(self, pen: object) -> None:
            """Record pen changes."""

            self.calls.append(("setPen", pen, None))

        def drawRoundedRect(
            self,
            rect: object,
            x_radius: object,
            y_radius: object,
        ) -> None:
            """Record rounded rect drawing."""

            self.calls.append(("drawRoundedRect", rect, (x_radius, y_radius)))

        def end(self) -> None:
            """Record painter shutdown."""

            self.calls.append(("end", None, None))

    class _FakeRegion:
        """Provide the paint event region consumed by the view."""

        def boundingRect(self) -> QRect:
            """Return a deterministic dirty rect."""

            return QRect(0, 0, 24, 16)

    class _FakePaintEvent:
        """Provide the QPaintEvent subset consumed by the view."""

        def region(self) -> _FakeRegion:
            """Return the deterministic fake region."""

            return _FakeRegion()

    if QApplication.instance() is None:
        QApplication([])
    view = PromptReorderView()
    view.resize(32, 20)
    view.set_render_state(
        PromptReorderViewRenderState(
            marker=PromptReorderMarkerPaintState(
                rect=QRectF(4.0, 5.0, 8.0, 9.0),
                color=QColor(255, 0, 0),
            )
        )
    )
    assert view.mask().isEmpty()
    monkeypatch.setattr(reorder_view_module, "QPainter", _FakePainter)

    view.paintEvent(cast(QPaintEvent, _FakePaintEvent()))

    calls = _FakePainter.instances[0].calls
    call_names = [call[0] for call in calls]
    assert calls[0][0] == "setClipRegion"
    assert calls[1] == ("setRenderHint", "antialiasing", True)
    assert "fillRect" not in call_names
    assert "setCompositionMode" not in call_names


def test_reorder_view_paints_complete_snapshot_before_raster_is_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    """Deferred raster warming should preserve complete chip paint immediately."""

    class _FakeRenderHint:
        """Expose the painter render hint used by the view."""

        Antialiasing = "antialiasing"

    class _FakePainter:
        """Record snapshot translation without touching the window system."""

        RenderHint = _FakeRenderHint
        instances: ClassVar[list["_FakePainter"]] = []

        def __init__(self, widget: object) -> None:
            """Record the painter target."""

            self.widget = widget
            self.calls: list[tuple[str, object | None, object | None]] = []
            _FakePainter.instances.append(self)

        def setClipRegion(self, region: object) -> None:
            """Record paint clipping."""

            self.calls.append(("setClipRegion", region, None))

        def setRenderHint(self, hint: object, enabled: bool) -> None:
            """Record render hint changes."""

            self.calls.append(("setRenderHint", hint, enabled))

        def save(self) -> None:
            """Record painter state preservation."""

            self.calls.append(("save", None, None))

        def translate(self, dx: float, dy: float) -> None:
            """Record snapshot translation."""

            self.calls.append(("translate", dx, dy))

        def restore(self) -> None:
            """Record painter state restoration."""

            self.calls.append(("restore", None, None))

        def end(self) -> None:
            """Record painter shutdown."""

            self.calls.append(("end", None, None))

    class _FakeRegion:
        """Provide the paint event region consumed by the view."""

        def boundingRect(self) -> QRect:
            """Return a deterministic dirty rect."""

            return QRect(0, 0, 160, 32)

    class _FakePaintEvent:
        """Provide the paint event subset consumed by the view."""

        def region(self) -> _FakeRegion:
            """Return the deterministic fake region."""

            return _FakeRegion()

    if QApplication.instance() is None:
        QApplication([])
    visual = _visual(80.0)
    visual_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=visual,
        projection_snapshot=_projection_snapshot(0),
    )
    state = prompt_reorder_view_render_state(
        PromptReorderViewRenderInput(
            visual_style=_style(),
            preview_active=False,
            live_ordered_segment_indices=(0,),
            preview_ordered_segment_indices=(),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={0: visual},
            preview_visuals_by_index={},
            dragged_segment_index=None,
            hovered_segment_index=None,
            active_segment_index=None,
            live_visual_snapshots_by_index={0: visual_snapshot},
        )
    )
    view = PromptReorderView()
    view.resize(180, 40)
    view.set_render_state(state)
    chrome_calls: list[PromptChipVisual] = []
    projection_calls: list[PromptReorderProjectionPaintSnapshot] = []
    monkeypatch.setattr(reorder_view_module, "QPainter", _FakePainter)
    monkeypatch.setattr(
        PromptChipPainter,
        "paint_chrome",
        lambda self, *, painter, visual, style: chrome_calls.append(visual),
    )
    monkeypatch.setattr(
        reorder_view_module,
        "paint_reorder_projection_snapshot",
        lambda painter, snapshot: projection_calls.append(snapshot),
    )

    view.paintEvent(cast(QPaintEvent, _FakePaintEvent()))

    assert chrome_calls == [visual]
    assert projection_calls == [visual_snapshot.projection_snapshot]
    call_names = [call[0] for call in _FakePainter.instances[0].calls]
    assert call_names[-4:] == ["save", "translate", "restore", "end"]


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
