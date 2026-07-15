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

"""Cover prompt reorder landing-shadow presentation ownership."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QPointF, QRect, QRectF, QSize
from PySide6.QtGui import QColor

from substitute.application.prompt_editor import (
    PromptLineDropTarget,
    PromptReorderChipView,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_shadow import (
    PromptReorderHeldShadowCaptureInput,
    PromptReorderLandingShadowPresenter,
    PromptReorderLandingShadowRequest,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
    reorder_visual_bubble_union_rect,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_view import (
    PromptReorderVisualStyle,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipLineGeometry,
    chrome_path_from_rects,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
)


class _LandingShadowLog:
    """Record presenter diagnostics without invoking strict log validation."""

    def __init__(self) -> None:
        """Initialize captured event and timing records."""

        self.events: list[tuple[str, dict[str, object]]] = []
        self.timings: list[tuple[str, dict[str, object]]] = []

    def event(self, event: str, **context: object) -> None:
        """Record one event call."""

        self.events.append((event, context))

    def timing(self, event: str, *, started_at: float, **context: object) -> float:
        """Record one timing call and return a deterministic elapsed value."""

        _ = started_at
        self.timings.append((event, context))
        return 0.0


def _presenter() -> tuple[PromptReorderLandingShadowPresenter, _LandingShadowLog]:
    """Return a landing-shadow presenter with captured diagnostics."""

    log = _LandingShadowLog()
    return (
        PromptReorderLandingShadowPresenter(
            telemetry=PromptReorderTelemetry(),
            log_event=log.event,
            log_timing=log.timing,
        ),
        log,
    )


def _chip_view(index: int = 1) -> PromptReorderChipView:
    """Return one reorder chip view for presenter geometry construction."""

    return PromptReorderChipView(
        index=index,
        text="beta",
        serialized_text="beta",
        display_text="beta",
        display_source_start=0,
        display_source_end=4,
        selection_start=0,
        selection_end=4,
        separator_text_after=", ",
        has_separator_after=True,
    )


def _line(
    rect: QRectF,
    *,
    visual_line_index: int = 0,
) -> PromptReorderChipLineGeometry:
    """Return one visual line geometry around a content rect."""

    return PromptReorderChipLineGeometry(
        visual_line_index=visual_line_index,
        line_rect=QRectF(0.0, rect.top(), 240.0, rect.height()),
        content_rect=QRectF(rect),
        leading_anchor=QPointF(rect.left(), rect.center().y()),
        trailing_anchor=QPointF(rect.right(), rect.center().y()),
    )


def _geometry(
    *rects: QRectF,
    chip_index: int = 1,
    visual_revision: int = 1,
) -> PromptReorderChipGeometry:
    """Return semantic reorder chip geometry for presenter tests."""

    if not rects:
        rects = (QRectF(12.0, 10.0, 42.0, 16.0),)
    lines = tuple(
        _line(rect, visual_line_index=index) for index, rect in enumerate(rects)
    )
    outline = reorder_visual_bubble_union_rect(
        tuple(line.content_rect for line in lines)
    )
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=chip_index,
            visual_revision=visual_revision,
        ),
        chip_index=chip_index,
        source_start=0,
        source_end=4,
        rendered_start=0,
        rendered_end=4,
        visual_lines=lines,
        hotspot_rect=outline.adjusted(-5.0, -3.0, 5.0, 3.0).toAlignedRect(),
        chrome_path=chrome_path_from_rects(tuple(line.content_rect for line in lines)),
        outline_bounds=outline,
        slot_before=QPointF(rects[0].left(), rects[0].center().y()),
        slot_after=QPointF(rects[-1].right(), rects[-1].center().y()),
        marker_height=max(rect.height() for rect in rects),
    )


def _placement(
    target: PromptLineDropTarget,
    *,
    anchor: QRectF,
) -> PromptReorderPlacementGeometry:
    """Return one active placement for a target."""

    return PromptReorderPlacementGeometry(
        placement_id=PromptReorderPlacementId(
            target_kind="line",
            row_index=target.row_index,
            insertion_index=target.insertion_index,
            gap_index=None,
            blank_line_index=None,
            visual_line_index=0,
            ordinal=target.insertion_index,
        ),
        target=target,
        hit_rect=QRectF(anchor),
        insertion_anchor_rect=QRectF(anchor),
        visual_line_rect=QRectF(0.0, anchor.top(), 240.0, anchor.height()),
        expected_landing_rect=None,
        source_before=0,
        source_after=4,
    )


def _request(
    *,
    target: PromptLineDropTarget | None = None,
    placement: PromptReorderPlacementGeometry | None = None,
    landing_geometry: PromptReorderChipGeometry | None = None,
    include_dragged_segment: bool = True,
) -> PromptReorderLandingShadowRequest:
    """Return a presenter request with stable visual inputs."""

    return PromptReorderLandingShadowRequest(
        gesture_id=10,
        event_id=20,
        dragged_segment_index=1,
        active_target=target,
        active_placement=placement,
        dragged_segment=_chip_view() if include_dragged_segment else None,
        content_rect=QRectF(0.0, 0.0, 240.0, 160.0),
        overlay_rect=QRectF(0.0, 0.0, 240.0, 160.0),
        preview_layout_active=True,
        preview_snapshot_available=True,
        preview_visual_count=3,
        landing_geometry=landing_geometry,
        target_visual=None,
        preview_geometry_target_identity=None,
        expected_preview_target_identity=None,
        preview_target_identity_matches=False,
    )


def _empty_capture(
    *,
    live_geometry: PromptReorderChipGeometry | None = None,
    base_drag_geometry: PromptReorderChipGeometry | None = None,
    live_visual: PromptChipVisual | None = None,
    chip_size: QSize | None = None,
    proxy_size: QSize | None = None,
    proxy_size_hint: QSize | None = None,
) -> PromptReorderHeldShadowCaptureInput:
    """Return capture input with no geometry candidates unless overridden."""

    return PromptReorderHeldShadowCaptureInput(
        chip_index=1,
        live_geometry=live_geometry,
        base_drag_geometry=base_drag_geometry,
        live_visual=live_visual,
        chip_size=QSize() if chip_size is None else chip_size,
        proxy_size=QSize() if proxy_size is None else proxy_size,
        proxy_size_hint=QSize() if proxy_size_hint is None else proxy_size_hint,
        gesture_id=10,
        event_id=20,
    )


def _event_names(log: _LandingShadowLog) -> Iterator[str]:
    """Yield recorded event names in order."""

    for event, _context in log.events:
        yield event


def _visual_style() -> PromptReorderVisualStyle:
    """Return deterministic reorder colors for paint-state tests."""

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


def test_landing_shadow_capture_prefers_live_chip_geometry() -> None:
    """Held-shadow capture should use projection-owned live geometry first."""

    presenter, log = _presenter()

    presenter.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(QRectF(8.0, 9.0, 44.0, 15.0)),
            chip_size=QSize(90, 30),
        )
    )

    held = presenter.held_shadow_geometry
    assert held is not None
    assert held.source == "live_chip_geometry"
    assert held.outline_size.width() == 44.0
    assert presenter.counters.held_shadow_capture_count == 1
    assert "preview_shadow.held_size_captured" in set(_event_names(log))


def test_landing_shadow_capture_uses_fallback_sources() -> None:
    """Held-shadow capture should fall back through prepared visual/widget sources."""

    presenter, _log = _presenter()

    presenter.capture_held_shadow(
        _empty_capture(
            live_visual=PromptChipVisual(
                bubble_rects=(QRectF(2.0, 3.0, 30.0, 12.0),),
                fragment_union_rect=QRectF(2.0, 3.0, 30.0, 12.0),
                hotspot_rect=QRect(0, 0, 40, 20),
                slot_before=QPointF(2.0, 9.0),
                slot_after=QPointF(32.0, 9.0),
                marker_height=12.0,
            )
        )
    )

    held = presenter.held_shadow_geometry
    assert held is not None
    assert held.source == "live_chip_visual"
    assert not held.low_confidence

    presenter.reset_drag_state()
    presenter.capture_held_shadow(_empty_capture(chip_size=QSize(22, 13)))

    held = presenter.held_shadow_geometry
    assert held is not None
    assert held.source == "chip_widget"
    assert held.low_confidence


def test_landing_shadow_missing_geometry_records_missing_without_exception() -> None:
    """Missing held-shadow inputs should be diagnostic-only and non-throwing."""

    presenter, log = _presenter()

    presenter.capture_held_shadow(_empty_capture())

    assert presenter.held_shadow_geometry is None
    assert presenter.counters.held_shadow_missing_count == 1
    assert "preview_shadow.held_size_missing" in set(_event_names(log))


def test_pending_landing_shadow_preserves_held_wrapped_rows() -> None:
    """Pending fallback should translate held bubble rows without collapsing them."""

    presenter, _log = _presenter()
    presenter.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(
                QRectF(8.0, 9.0, 52.0, 14.0),
                QRectF(8.0, 31.0, 38.0, 14.0),
            )
        )
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(120.0, 50.0, 8.0, 18.0))

    visual = presenter.pending_shadow_preview_visual(
        _request(target=target, placement=placement),
        reason="test",
    )

    held = presenter.held_shadow_geometry
    assert visual is not None
    assert held is not None
    assert len(visual.bubble_rects) == len(held.normalized_bubble_rects)
    assert max(rect.height() for rect in visual.bubble_rects) == max(
        rect.height() for rect in held.normalized_bubble_rects
    )


def test_missing_preview_geometry_uses_placement_owned_held_shadow() -> None:
    """Missing preview geometry should still yield a placement-owned shadow."""

    presenter, _log = _presenter()
    presenter.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0))

    result = presenter.landing_preview_for_active_target(
        _request(target=target, placement=placement, landing_geometry=None)
    )

    assert result.geometry is not None
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_bounds == QRectF(
        result.geometry.hotspot_rect
    )
    held = presenter.held_shadow_geometry
    assert held is not None
    assert result.geometry.outline_bounds.width() == held.outline_size.width()


def test_authoritative_preview_geometry_wins_over_placement_owned_shadow() -> None:
    """Landing preview must use the same preview geometry that chips settle to."""

    presenter, _log = _presenter()
    presenter.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(140.0, 80.0, 8.0, 18.0))
    preview_geometry = _geometry(QRectF(24.0, 22.0, 52.0, 14.0))

    result = presenter.landing_preview_for_active_target(
        _request(
            target=target,
            placement=placement,
            landing_geometry=preview_geometry,
        )
    )

    assert result.geometry is preview_geometry
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_bounds == QRectF(
        preview_geometry.hotspot_rect
    )


def test_landing_shadow_updates_when_target_placement_changes() -> None:
    """Target changes should derive landing geometry from the new placement."""

    presenter, _log = _presenter()
    presenter.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    first_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    second_target = PromptLineDropTarget(row_index=0, insertion_index=2)
    first_result = presenter.landing_preview_for_active_target(
        _request(
            target=first_target,
            placement=_placement(first_target, anchor=QRectF(40.0, 40.0, 8.0, 18.0)),
        )
    )
    second_result = presenter.landing_preview_for_active_target(
        _request(
            target=second_target,
            placement=_placement(
                second_target,
                anchor=QRectF(150.0, 40.0, 8.0, 18.0),
            ),
        )
    )

    assert first_result.geometry is not None
    assert second_result.geometry is not None
    assert second_result.geometry.hotspot_rect != first_result.geometry.hotspot_rect
    assert second_result.active_placement is not None
    assert second_result.active_placement.target == second_target


def test_drag_landing_preview_paint_state_uses_geometry() -> None:
    """Drag landing paint state should expose geometry and record preview context."""

    presenter, log = _presenter()
    presenter.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
    )

    result = presenter.landing_preview_paint_state(
        request,
        visual_style=_visual_style(),
    )

    assert result.paint_state is not None
    assert result.paint_state.geometry is not None
    assert result.paint_state.visual is None
    assert result.paint_state.style.outline_only is True
    assert result.paint_state.style.opacity > 0.8
    assert presenter.last_landing_preview_geometry == result.paint_state.geometry
    assert presenter.last_landing_preview_visual is not None
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_chip_index == 1
    assert "landing_preview.paint" in {event for event, _context in log.timings}


def test_pending_landing_shadow_paint_state_uses_held_visual() -> None:
    """Pending landing paint state should expose held-shadow visual fallback."""

    presenter, _log = _presenter()
    presenter.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
        landing_geometry=None,
        include_dragged_segment=False,
    )

    result = presenter.landing_preview_paint_state(
        request,
        visual_style=_visual_style(),
    )

    assert result.paint_state is not None
    assert result.paint_state.geometry is None
    assert result.paint_state.visual is not None
    assert result.paint_state.style.outline_only is True
    assert result.paint_state.style.opacity < 0.6
    assert presenter.counters.pending_shadow_fallback_count == 1
    assert presenter.counters.pending_shadow_replaced_marker_count == 1


def test_missing_landing_inputs_return_empty_paint_state() -> None:
    """Landing paint construction should return no state without geometry or held metrics."""

    presenter, _log = _presenter()
    target = PromptLineDropTarget(row_index=0, insertion_index=0)

    result = presenter.landing_preview_paint_state(
        _request(
            target=target,
            placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
            landing_geometry=None,
            include_dragged_segment=False,
        ),
        visual_style=_visual_style(),
    )

    assert result.paint_state is None
