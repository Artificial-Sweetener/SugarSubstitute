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

"""Cover focused prompt reorder landing session, resolution, and paint ownership."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from PySide6.QtCore import QPointF, QRect, QRectF, QSize
from PySide6.QtGui import QColor

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
    prompt_chip_bubble_union_rect,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_diagnostics import (
    PromptReorderLandingDiagnostics,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_events import (
    PromptReorderLandingEventPublisher,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderHeldShadowCaptureInput,
    PromptReorderHeldShadowGeometry,
    PromptReorderLandingShadowRequest,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_paint import (
    PromptReorderLandingPaintOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_resolution import (
    PromptReorderLandingResolutionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_session import (
    PromptReorderLandingSessionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_state import (
    PromptReorderLandingStateOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_style import (
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
    """Record owner diagnostics without invoking strict log validation."""

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


def _owners() -> tuple[
    PromptReorderLandingSessionOwner,
    PromptReorderLandingResolutionOwner,
    PromptReorderLandingPaintOwner,
    _LandingShadowLog,
]:
    """Return composed landing session, resolution, and paint owners with events."""

    log = _LandingShadowLog()
    telemetry = PromptReorderTelemetry()
    state = PromptReorderLandingStateOwner()
    diagnostics = PromptReorderLandingDiagnostics(
        telemetry=telemetry,
        log_event=log.event,
    )
    events = PromptReorderLandingEventPublisher(
        telemetry=telemetry,
        log_event=log.event,
        log_timing=log.timing,
    )
    session = PromptReorderLandingSessionOwner(
        state=state,
        diagnostics=diagnostics,
        events=events,
    )
    resolution = PromptReorderLandingResolutionOwner(
        telemetry=telemetry,
        state=state,
        diagnostics=diagnostics,
        events=events,
    )
    return (
        session,
        resolution,
        PromptReorderLandingPaintOwner(
            telemetry=telemetry,
            resolution=resolution,
            state=state,
            diagnostics=diagnostics,
            events=events,
        ),
        log,
    )


def _chip_view(index: int = 1) -> PromptReorderChipView:
    """Return one reorder chip view for owner geometry construction."""

    return PromptReorderChipView(
        index=index,
        partition_index=0,
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
    """Return semantic reorder chip geometry for owner tests."""

    if not rects:
        rects = (QRectF(12.0, 10.0, 42.0, 16.0),)
    lines = tuple(
        _line(rect, visual_line_index=index) for index, rect in enumerate(rects)
    )
    outline = prompt_chip_bubble_union_rect(tuple(line.content_rect for line in lines))
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
    """Return a owner request with stable visual inputs."""

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

    session, _resolution, paint, log = _owners()

    session.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(QRectF(8.0, 9.0, 44.0, 15.0)),
            chip_size=QSize(90, 30),
        )
    )

    held = session.publication.held_shadow_geometry
    assert held is not None
    assert held.source == "live_chip_geometry"
    assert held.outline_size.width() == 44.0
    assert paint.counters.held_shadow_capture_count == 1
    assert "preview_shadow.held_size_captured" in set(_event_names(log))


def test_landing_shadow_capture_uses_fallback_sources() -> None:
    """Held-shadow capture should fall back through prepared visual/widget sources."""

    session, _resolution, _paint, _log = _owners()

    session.capture_held_shadow(
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

    held = session.publication.held_shadow_geometry
    assert held is not None
    assert held.source == "live_chip_visual"
    assert not held.low_confidence

    session.reset_drag_state()
    session.capture_held_shadow(_empty_capture(chip_size=QSize(22, 13)))

    held = session.publication.held_shadow_geometry
    assert held is not None
    assert held.source == "chip_widget"
    assert held.low_confidence


def test_landing_shadow_missing_geometry_records_missing_without_exception() -> None:
    """Missing held-shadow inputs should be diagnostic-only and non-throwing."""

    session, _resolution, paint, log = _owners()

    session.capture_held_shadow(_empty_capture())

    assert session.publication.held_shadow_geometry is None
    assert paint.counters.held_shadow_missing_count == 1
    assert "preview_shadow.held_size_missing" in set(_event_names(log))


def test_pending_landing_shadow_preserves_held_wrapped_rows() -> None:
    """Pending fallback should translate held bubble rows without collapsing them."""

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(
                QRectF(8.0, 9.0, 52.0, 14.0),
                QRectF(8.0, 31.0, 38.0, 14.0),
            )
        )
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(120.0, 50.0, 8.0, 18.0))

    visual = resolution.pending_shadow_preview_visual(
        _request(target=target, placement=placement),
        reason="test",
    )

    held = session.publication.held_shadow_geometry
    assert visual is not None
    assert held is not None
    assert len(visual.bubble_rects) == len(held.normalized_bubble_rects)
    assert max(rect.height() for rect in visual.bubble_rects) == max(
        rect.height() for rect in held.normalized_bubble_rects
    )


def test_missing_preview_geometry_uses_placement_owned_held_shadow() -> None:
    """Missing preview geometry should still yield a placement-owned shadow."""

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0))

    result = resolution.landing_preview_for_active_target(
        _request(target=target, placement=placement, landing_geometry=None)
    )

    assert result.geometry is not None
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_bounds == QRectF(
        result.geometry.hotspot_rect
    )
    held = session.publication.held_shadow_geometry
    assert held is not None
    assert result.geometry.outline_bounds.width() == held.outline_size.width()


def test_authoritative_preview_geometry_wins_over_placement_owned_shadow() -> None:
    """Landing preview must use the same preview geometry that chips settle to."""

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(140.0, 80.0, 8.0, 18.0))
    preview_geometry = _geometry(QRectF(24.0, 22.0, 52.0, 14.0))

    result = resolution.landing_preview_for_active_target(
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

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    first_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    second_target = PromptLineDropTarget(row_index=0, insertion_index=2)
    first_result = resolution.landing_preview_for_active_target(
        _request(
            target=first_target,
            placement=_placement(first_target, anchor=QRectF(40.0, 40.0, 8.0, 18.0)),
        )
    )
    second_result = resolution.landing_preview_for_active_target(
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

    session, _resolution, paint, log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
    )

    result = paint.landing_preview_paint_state(
        request,
        visual_style=_visual_style(),
    )

    assert result.paint_state is not None
    assert result.paint_state.geometry is not None
    assert result.paint_state.visual is None
    assert result.paint_state.style.outline_only is True
    assert result.paint_state.style.opacity > 0.8
    assert session.publication.last_preview_geometry == result.paint_state.geometry
    assert session.publication.last_preview_visual is not None
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_chip_index == 1
    assert "landing_preview.paint" in {event for event, _context in log.timings}


def test_landing_paint_cache_reuses_only_exact_strong_input_identity() -> None:
    """Exact requests should reuse while equal replacement objects miss."""

    session, _resolution, paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
    )
    style = _visual_style()

    first = paint.landing_preview_paint_state(request, visual_style=style)
    ready = paint.landing_preview_paint_state(request, visual_style=style)
    reused = paint.landing_preview_paint_state(request, visual_style=style)
    replacement = paint.landing_preview_paint_state(
        replace(request, dragged_segment=_chip_view()),
        visual_style=style,
    )

    assert ready is not first
    assert reused is ready
    assert replacement is not ready
    assert paint.counters.paint_cache_hit_count == 1
    assert paint.counters.paint_cache_miss_count == 3


def test_pending_landing_shadow_paint_state_uses_held_visual() -> None:
    """Pending landing paint state should expose held-shadow visual fallback."""

    session, _resolution, paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
        landing_geometry=None,
        include_dragged_segment=False,
    )

    result = paint.landing_preview_paint_state(
        request,
        visual_style=_visual_style(),
    )

    assert result.paint_state is not None
    assert result.paint_state.geometry is None
    assert result.paint_state.visual is not None
    assert result.paint_state.style.outline_only is True
    assert result.paint_state.style.opacity < 0.6
    assert paint.counters.pending_shadow_fallback_count == 1
    assert paint.counters.pending_shadow_replaced_marker_count == 1


def test_missing_landing_inputs_return_empty_paint_state() -> None:
    """Landing paint construction should return no state without geometry or held metrics."""

    _session, _resolution, paint, _log = _owners()
    target = PromptLineDropTarget(row_index=0, insertion_index=0)

    result = paint.landing_preview_paint_state(
        _request(
            target=target,
            placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
            landing_geometry=None,
            include_dragged_segment=False,
        ),
        visual_style=_visual_style(),
    )

    assert result.paint_state is None


def test_stale_landing_shadow_rejection_records_fallback_state() -> None:
    """A placement for another target must reject and expose marker fallback."""

    session, resolution, paint, log = _owners()
    active_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    stale_target = PromptLineDropTarget(row_index=1, insertion_index=2)
    request = _request(
        target=active_target,
        placement=_placement(
            stale_target,
            anchor=QRectF(100.0, 50.0, 8.0, 18.0),
        ),
    )

    accepted = resolution.landing_shadow_matches_active_target(
        request,
        _geometry(QRectF(100.0, 50.0, 52.0, 14.0)),
        emit_rejection=True,
    )

    assert accepted is False
    assert session.publication.last_rejected_target == active_target
    assert paint.counters.stale_shadow_rejected_count == 1
    assert tuple(_event_names(log))[-2:] == (
        "preview_shadow.rejected_stale_target",
        "preview_geometry.lightweight_marker_used",
    )


def test_pending_shadow_diagnostics_compare_wrapped_and_authoritative_shapes() -> None:
    """Pending chrome must retain mismatch events and diagnostic accounting."""

    session, resolution, paint, log = _owners()
    session.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(
                QRectF(8.0, 9.0, 52.0, 14.0),
                QRectF(8.0, 31.0, 38.0, 14.0),
            )
        )
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
        landing_geometry=_geometry(QRectF(100.0, 50.0, 52.0, 14.0)),
    )

    visual = resolution.pending_shadow_preview_visual(request, reason="characterize")

    assert visual is not None
    event_names = tuple(_event_names(log))
    assert "preview_shadow.pending_authoritative_delta" in event_names
    assert "diagnostic.pending_authoritative_shadow_bubble_count_delta" in event_names
    assert paint.counters.expected_diagnostic_count == 1


def test_landing_diagnostics_own_classification_counters_and_reset() -> None:
    """The diagnostic owner must classify and reset without owner state."""

    log = _LandingShadowLog()
    diagnostics = PromptReorderLandingDiagnostics(
        telemetry=PromptReorderTelemetry(),
        log_event=log.event,
    )
    held_rects = (
        QRectF(0.0, 0.0, 52.0, 14.0),
        QRectF(0.0, 22.0, 38.0, 14.0),
    )
    held = PromptReorderHeldShadowGeometry(
        chip_index=1,
        normalized_bubble_rects=held_rects,
        chrome_bounds=prompt_chip_bubble_union_rect(held_rects),
        hotspot_bounds=QRectF(0.0, 0.0, 62.0, 42.0),
        source="test",
    )
    pending_visual = PromptChipVisual(
        bubble_rects=held_rects,
        fragment_union_rect=prompt_chip_bubble_union_rect(held_rects),
        hotspot_rect=QRect(0, 0, 62, 42),
        slot_before=QPointF(0.0, 7.0),
        slot_after=QPointF(38.0, 29.0),
        marker_height=14.0,
    )

    diagnostics.pending_shadow_shape(
        _request(landing_geometry=_geometry(QRectF(0.0, 0.0, 52.0, 14.0))),
        pending_visual,
        held,
        reason="owner-contract",
    )

    assert diagnostics.counters.expected_diagnostic_count == 1
    assert diagnostics.counters.anomaly_count == 1
    diagnostics.reset()
    assert diagnostics.counters.expected_diagnostic_count == 0
    assert diagnostics.counters.anomaly_count == 0


def test_landing_state_owner_publishes_only_authoritative_transitions() -> None:
    """Landing state must be immutable, revisioned, and skip duplicate reasons."""

    owner = PromptReorderLandingStateOwner()
    initial = owner.publication

    owner.set_skip_reason("none")
    owner.record_missing_held_shadow()

    assert owner.publication is initial
    assert owner.counters.held_shadow_missing_count == 1

    held_rects = (QRectF(0.0, 0.0, 52.0, 14.0),)
    held = PromptReorderHeldShadowGeometry(
        chip_index=1,
        normalized_bubble_rects=held_rects,
        chrome_bounds=prompt_chip_bubble_union_rect(held_rects),
        hotspot_bounds=QRectF(0.0, 0.0, 62.0, 20.0),
        source="test",
    )
    assert owner.adopt_held_shadow(held) is True
    captured = owner.publication
    assert captured.revision == initial.revision + 1
    assert captured.held_shadow_geometry is held
    assert owner.adopt_held_shadow(held) is False
    assert owner.publication is captured

    owner.reset()

    assert owner.publication.revision == captured.revision + 1
    assert owner.publication.held_shadow_geometry is None
    assert owner.counters.held_shadow_capture_count == 0


def test_landing_event_publisher_owns_skip_event_classification() -> None:
    """Operational skip reasons must map to stable event names and context."""

    log = _LandingShadowLog()
    events = PromptReorderLandingEventPublisher(
        telemetry=PromptReorderTelemetry(),
        log_event=log.event,
        log_timing=log.timing,
    )
    request = _request()

    for reason in (
        "no_dragged_segment",
        "no_active_target",
        "no_preview_layout",
        "missing_authoritative_geometry",
    ):
        events.preview_skipped(request, reason)

    assert tuple(_event_names(log)) == (
        "landing_preview.skipped_no_dragged_segment",
        "landing_preview.skipped_no_active_target",
        "landing_preview.skipped_no_preview_layout",
        "landing_preview.skipped_no_geometry",
    )
    assert "dragged_segment_index" not in log.events[0][1]
    assert log.events[-1][1]["preview_visual_count"] == request.preview_visual_count
