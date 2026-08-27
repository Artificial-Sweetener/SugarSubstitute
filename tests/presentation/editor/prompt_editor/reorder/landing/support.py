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

"""Provide shared prompt reorder landing geometry and diagnostics."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QPointF, QRectF, QSize
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
