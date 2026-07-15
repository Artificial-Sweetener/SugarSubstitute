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

"""Own prompt reorder held-chip and landing-shadow presentation state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, QSizeF

from substitute.application.prompt_editor import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderChipView,
    PromptReorderDropTarget,
)

from ..projection.observability import (
    reorder_drag_rect_context,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipLineGeometry,
    chip_geometry_context,
    chrome_path_from_rects,
)
from ..projection.reorder_drop_targets import PromptReorderDropTargetVisual
from ..projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    placement_geometry_context,
)
from ..projection.reorder_state import PromptReorderPreviewTargetIdentity
from .chip_visuals import PromptChipVisual
from .reorder_telemetry import (
    PromptReorderTelemetry,
    reorder_visual_bubble_union_rect,
)
from .reorder_view import (
    PromptReorderLandingPreviewPaintState,
    PromptReorderVisualStyle,
    prompt_reorder_visual_for_chip_geometry,
)

_LANDING_PREVIEW_OUTLINE_OPACITY = 0.82
_LANDING_PREVIEW_OUTLINE_WIDTH = 1.25
_PENDING_LANDING_PREVIEW_OUTLINE_OPACITY = 0.52
_TARGET_LANDING_MISMATCH_X = 24.0
_INITIAL_LANDING_SHADOW_MIN_WIDTH = 24.0
_SHADOW_SHAPE_MISMATCH = 1.0


class _EventLogger(Protocol):
    """Log one prompt-safe reorder interaction event."""

    def __call__(self, event: str, **context: object) -> None:
        """Emit the supplied event and structural context."""


class _TimingLogger(Protocol):
    """Log one prompt-safe reorder interaction timing measurement."""

    def __call__(
        self,
        event: str,
        *,
        started_at: float,
        **context: object,
    ) -> float:
        """Emit the supplied timing event and return elapsed milliseconds."""


@dataclass(frozen=True, slots=True)
class PromptReorderHeldShadowGeometry:
    """Describe immutable visible chip chrome captured for one drag."""

    chip_index: int
    normalized_bubble_rects: tuple[QRectF, ...]
    chrome_bounds: QRectF
    hotspot_bounds: QRectF
    source: str
    low_confidence: bool = False

    @property
    def hotspot_size(self) -> QSizeF:
        """Return diagnostic hotspot size retained for instrumentation."""

        return QSizeF(self.hotspot_bounds.size())

    @property
    def outline_size(self) -> QSizeF:
        """Return diagnostic visible chrome size retained for instrumentation."""

        return QSizeF(self.chrome_bounds.size())


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowCounters:
    """Expose landing-shadow instrumentation owned by the presenter."""

    initial_shadow_sync_count: int = 0
    initial_shadow_ready_count: int = 0
    stale_shadow_rejected_count: int = 0
    held_shadow_capture_count: int = 0
    held_shadow_missing_count: int = 0
    pending_shadow_fallback_count: int = 0
    pending_shadow_replaced_marker_count: int = 0
    anomaly_count: int = 0
    expected_diagnostic_count: int = 0
    paint_cache_hit_count: int = 0
    paint_cache_miss_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptReorderHeldShadowCaptureInput:
    """Carry prepared held-chip geometry candidates for drag-start capture."""

    chip_index: int
    live_geometry: PromptReorderChipGeometry | None
    base_drag_geometry: PromptReorderChipGeometry | None
    live_visual: PromptChipVisual | None
    chip_size: QSize
    proxy_size: QSize
    proxy_size_hint: QSize
    gesture_id: int | None
    event_id: int | None


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowRequest:
    """Carry current visual reorder state needed to prepare landing feedback."""

    gesture_id: int | None
    event_id: int | None
    dragged_segment_index: int | None
    active_target: PromptReorderDropTarget | None
    active_placement: PromptReorderPlacementGeometry | None
    dragged_segment: PromptReorderChipView | None
    content_rect: QRectF
    overlay_rect: QRectF
    preview_layout_active: bool
    preview_snapshot_available: bool
    preview_visual_count: int
    landing_geometry: PromptReorderChipGeometry | None
    target_visual: PromptReorderDropTargetVisual | None
    preview_geometry_target_identity: PromptReorderPreviewTargetIdentity | None
    expected_preview_target_identity: PromptReorderPreviewTargetIdentity | None
    preview_target_identity_matches: bool


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowGeometryResult:
    """Return landing geometry together with any placement state update."""

    geometry: PromptReorderChipGeometry | None
    active_placement: PromptReorderPlacementGeometry | None


@dataclass(frozen=True, slots=True)
class PromptReorderLandingShadowPaintResult:
    """Return prepared landing paint state and any placement state update."""

    paint_state: PromptReorderLandingPreviewPaintState | None
    active_placement: PromptReorderPlacementGeometry | None


@dataclass(frozen=True, slots=True)
class PromptReorderInitialShadowSyncResult:
    """Return the first-shadow sync decision and any placement state update."""

    should_flush: bool
    active_placement: PromptReorderPlacementGeometry | None


@dataclass(slots=True)
class PromptReorderLandingShadowPresenter:
    """Own reorder landing-shadow capture, fallback geometry, and diagnostics."""

    telemetry: PromptReorderTelemetry
    log_event: _EventLogger
    log_timing: _TimingLogger
    held_shadow_geometry: PromptReorderHeldShadowGeometry | None = None
    last_landing_preview_visual: PromptChipVisual | None = None
    last_landing_preview_target: PromptReorderDropTarget | None = None
    last_landing_preview_event_id: int | None = None
    last_landing_preview_geometry: PromptReorderChipGeometry | None = None
    last_landing_preview_skip_reason: str = "none"
    last_rejected_landing_shadow_target: PromptReorderDropTarget | None = None
    _initial_landing_shadow_sync_used: bool = False
    _initial_landing_shadow_ready: bool = False
    _paint_result_cache_key: tuple[object, ...] | None = None
    _paint_result_cache: PromptReorderLandingShadowPaintResult | None = None
    _counters: PromptReorderLandingShadowCounters = PromptReorderLandingShadowCounters()

    @property
    def initial_landing_shadow_sync_used(self) -> bool:
        """Return whether the one allowed immediate first-shadow sync was used."""

        return self._initial_landing_shadow_sync_used

    @property
    def initial_landing_shadow_ready(self) -> bool:
        """Return whether a chip-shaped landing shadow is ready for the gesture."""

        return self._initial_landing_shadow_ready

    @property
    def counters(self) -> PromptReorderLandingShadowCounters:
        """Return immutable landing-shadow instrumentation counters."""

        return self._counters

    def reset_session_state(self) -> None:
        """Clear all landing-shadow state for a new overlay session."""

        self.reset_drag_state()

    def reset_drag_state(self) -> None:
        """Clear per-drag landing-shadow state and counters."""

        self.held_shadow_geometry = None
        self.last_landing_preview_visual = None
        self.last_landing_preview_target = None
        self.last_landing_preview_event_id = None
        self.last_landing_preview_geometry = None
        self.last_landing_preview_skip_reason = "none"
        self.last_rejected_landing_shadow_target = None
        self._initial_landing_shadow_sync_used = False
        self._initial_landing_shadow_ready = False
        self._clear_paint_cache()
        self._counters = PromptReorderLandingShadowCounters()

    def clear_preview_state(self) -> None:
        """Clear cached preview shadow details without resetting counters."""

        self.last_landing_preview_visual = None
        self.last_landing_preview_target = None
        self.last_landing_preview_event_id = None
        self.last_landing_preview_geometry = None
        self.last_landing_preview_skip_reason = "none"
        self.last_rejected_landing_shadow_target = None
        self._clear_paint_cache()

    def clear_held_shadow(self) -> None:
        """Clear held-shadow geometry when chip geometry is discarded."""

        self.held_shadow_geometry = None
        self.last_landing_preview_skip_reason = "none"
        self._clear_paint_cache()

    def capture_held_shadow(
        self,
        capture: PromptReorderHeldShadowCaptureInput,
    ) -> None:
        """Capture immutable visible chrome metrics for the active drag."""

        if self.held_shadow_geometry is not None:
            return
        if capture.live_geometry is not None:
            self._store_held_shadow_geometry(
                chip_index=capture.chip_index,
                bubble_rects=tuple(
                    line.content_rect for line in capture.live_geometry.visual_lines
                ),
                hotspot_bounds=QRectF(capture.live_geometry.hotspot_rect),
                source="live_chip_geometry",
                gesture_id=capture.gesture_id,
                event_id=capture.event_id,
            )
            return
        if capture.base_drag_geometry is not None:
            self._store_held_shadow_geometry(
                chip_index=capture.chip_index,
                bubble_rects=tuple(
                    line.content_rect
                    for line in capture.base_drag_geometry.visual_lines
                ),
                hotspot_bounds=QRectF(capture.base_drag_geometry.hotspot_rect),
                source="base_drag_chip_geometry",
                gesture_id=capture.gesture_id,
                event_id=capture.event_id,
            )
            return
        if capture.live_visual is not None:
            self._store_held_shadow_geometry(
                chip_index=capture.chip_index,
                bubble_rects=capture.live_visual.bubble_rects,
                hotspot_bounds=QRectF(capture.live_visual.hotspot_rect),
                source="live_chip_visual",
                gesture_id=capture.gesture_id,
                event_id=capture.event_id,
            )
            return
        if not capture.chip_size.isEmpty():
            chip_rect = QRectF(QPointF(0.0, 0.0), QSizeF(capture.chip_size))
            self._store_held_shadow_geometry(
                chip_index=capture.chip_index,
                bubble_rects=(chip_rect,),
                hotspot_bounds=chip_rect,
                source="chip_widget",
                low_confidence=True,
                gesture_id=capture.gesture_id,
                event_id=capture.event_id,
            )
            return
        proxy_size = capture.proxy_size
        if proxy_size.isEmpty():
            proxy_size = capture.proxy_size_hint
        if not proxy_size.isEmpty():
            proxy_rect = QRectF(QPointF(0.0, 0.0), QSizeF(proxy_size))
            self._store_held_shadow_geometry(
                chip_index=capture.chip_index,
                bubble_rects=(proxy_rect,),
                hotspot_bounds=proxy_rect,
                source="drag_proxy",
                low_confidence=True,
                gesture_id=capture.gesture_id,
                event_id=capture.event_id,
            )
            return
        self._increment_counter("held_shadow_missing_count")
        self.log_event(
            "preview_shadow.held_size_missing",
            gesture_id=capture.gesture_id,
            event_id=capture.event_id,
            dragged_segment_index=capture.chip_index,
            shadow_origin="missing",
        )

    def has_valid_initial_landing_shadow(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> PromptReorderLandingShadowGeometryResult:
        """Return whether the active drag has a chip-shaped landing shadow."""

        placement_owned = self.placement_owned_landing_geometry(
            request,
            reason="initial_shadow_probe",
        )
        geometry = placement_owned.geometry or request.landing_geometry
        valid = self.is_chip_shaped_landing_shadow(request, geometry)
        if valid and placement_owned.geometry is None and geometry is not None:
            valid = self.landing_shadow_matches_active_target(
                request,
                geometry,
                emit_rejection=False,
            )
        self.log_event(
            "preview_sync.initial_shadow_probe",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            has_preview_snapshot=request.preview_snapshot_available,
            has_landing_geometry=geometry is not None,
            is_chip_shaped=(
                geometry is not None
                and self.is_chip_shaped_landing_shadow(request, geometry)
            ),
            initial_shadow_ready=self._initial_landing_shadow_ready,
            initial_shadow_sync_used=self._initial_landing_shadow_sync_used,
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )
        return PromptReorderLandingShadowGeometryResult(
            geometry=geometry if valid else None,
            active_placement=placement_owned.active_placement,
        )

    def should_flush_initial_landing_shadow_sync(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        base_drag_layout_available: bool,
    ) -> PromptReorderInitialShadowSyncResult:
        """Return and consume the one allowed immediate first-shadow sync request."""

        if (
            request.dragged_segment_index is None
            or not base_drag_layout_available
            or request.active_target is None
        ):
            return PromptReorderInitialShadowSyncResult(
                should_flush=False,
                active_placement=request.active_placement,
            )
        probe = self.has_valid_initial_landing_shadow(request)
        if probe.geometry is not None:
            self.mark_initial_landing_shadow_ready(request, probe.geometry)
            return PromptReorderInitialShadowSyncResult(
                should_flush=False,
                active_placement=probe.active_placement,
            )
        if self._initial_landing_shadow_sync_used:
            self.log_event(
                "preview_sync.initial_shadow_already_used",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
                active_target_kind=reorder_drag_target_kind(request.active_target),
                has_preview_snapshot=request.preview_snapshot_available,
                **chip_geometry_context(
                    request.landing_geometry,
                    prefix="landing_geometry",
                ),
            )
            return PromptReorderInitialShadowSyncResult(
                should_flush=False,
                active_placement=probe.active_placement,
            )
        self._initial_landing_shadow_sync_used = True
        self._increment_counter("initial_shadow_sync_count")
        self.log_event(
            "preview_sync.immediate_initial_shadow_missing",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            has_preview_snapshot=request.preview_snapshot_available,
            **chip_geometry_context(
                request.landing_geometry,
                prefix="landing_geometry",
            ),
        )
        return PromptReorderInitialShadowSyncResult(
            should_flush=True,
            active_placement=probe.active_placement,
        )

    def landing_preview_paint_state(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        visual_style: PromptReorderVisualStyle,
    ) -> PromptReorderLandingShadowPaintResult:
        """Return prepared landing-preview paint state for the passive view."""

        if request.dragged_segment is None:
            return self._build_landing_preview_paint_state(
                request,
                visual_style=visual_style,
            )

        cache_key = self._paint_result_key(request, visual_style=visual_style)
        if (
            self._paint_result_cache_key == cache_key
            and self._paint_result_cache is not None
        ):
            self._increment_counter("paint_cache_hit_count")
            return self._paint_result_cache
        self._increment_counter("paint_cache_miss_count")
        result = self._build_landing_preview_paint_state(
            request,
            visual_style=visual_style,
        )
        self._paint_result_cache_key = cache_key
        self._paint_result_cache = result
        return result

    def _build_landing_preview_paint_state(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        visual_style: PromptReorderVisualStyle,
    ) -> PromptReorderLandingShadowPaintResult:
        """Build landing-preview paint state without consulting the frame cache."""

        geometry_result = self.landing_preview_for_active_target(request)
        if geometry_result.geometry is not None:
            return PromptReorderLandingShadowPaintResult(
                paint_state=self._drag_landing_preview_paint_state(
                    request,
                    geometry_result.geometry,
                    visual_style=visual_style,
                ),
                active_placement=geometry_result.active_placement,
            )
        pending_visual = self.pending_shadow_preview_visual(
            request,
            reason=self.last_landing_preview_skip_reason,
        )
        if pending_visual is None:
            return PromptReorderLandingShadowPaintResult(
                paint_state=None,
                active_placement=geometry_result.active_placement,
            )
        return PromptReorderLandingShadowPaintResult(
            paint_state=self._pending_landing_shadow_paint_state(
                request,
                pending_visual,
                visual_style=visual_style,
                reason=self.last_landing_preview_skip_reason,
            ),
            active_placement=geometry_result.active_placement,
        )

    def _paint_result_key(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        visual_style: PromptReorderVisualStyle,
    ) -> tuple[object, ...]:
        """Return a strict identity for one landing preview paint query."""

        return (
            id(visual_style),
            request.gesture_id,
            request.event_id,
            request.dragged_segment_index,
            request.active_target,
            _placement_key(request.active_placement),
            id(request.dragged_segment),
            _rect_key(request.content_rect),
            _rect_key(request.overlay_rect),
            request.preview_layout_active,
            request.preview_snapshot_available,
            request.preview_visual_count,
            _chip_geometry_key(request.landing_geometry),
            id(request.target_visual),
            request.preview_geometry_target_identity,
            request.expected_preview_target_identity,
            request.preview_target_identity_matches,
            _held_shadow_key(self.held_shadow_geometry),
            self._initial_landing_shadow_ready,
            self._initial_landing_shadow_sync_used,
        )

    def _clear_paint_cache(self) -> None:
        """Clear cached landing preview paint state."""

        self._paint_result_cache_key = None
        self._paint_result_cache = None

    def placement_owned_landing_geometry(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        reason: str,
    ) -> PromptReorderLandingShadowGeometryResult:
        """Return current-target landing geometry derived from placement state."""

        held = self.held_shadow_geometry
        if (
            request.dragged_segment_index is None
            or request.active_target is None
            or request.active_placement is None
            or held is None
            or held.chip_index != request.dragged_segment_index
            or request.dragged_segment is None
        ):
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )

        anchor_rect = request.active_placement.insertion_anchor_rect
        top_left = QPointF(
            anchor_rect.center().x(),
            anchor_rect.center().y() - (held.chrome_bounds.height() / 2.0),
        )
        visual = self.clamp_pending_shadow_visual(
            self.translated_held_shadow_visual(held, top_left),
            content_rect=request.content_rect,
            overlay_rect=request.overlay_rect,
        )
        content_rects = visual.bubble_rects
        if not content_rects:
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )

        visual_lines = tuple(
            PromptReorderChipLineGeometry(
                visual_line_index=(
                    request.active_placement.placement_id.visual_line_index
                    + line_offset
                ),
                line_rect=QRectF(request.active_placement.visual_line_rect),
                content_rect=QRectF(content_rect),
                leading_anchor=QPointF(content_rect.left(), content_rect.center().y()),
                trailing_anchor=QPointF(
                    content_rect.right(),
                    content_rect.center().y(),
                ),
            )
            for line_offset, content_rect in enumerate(content_rects)
        )
        geometry = PromptReorderChipGeometry(
            geometry_id=PromptReorderChipGeometryId(
                chip_index=request.dragged_segment_index,
                visual_revision=-(request.event_id or 0),
            ),
            chip_index=request.dragged_segment_index,
            source_start=request.dragged_segment.selection_start,
            source_end=request.dragged_segment.selection_end,
            rendered_start=request.dragged_segment.selection_start,
            rendered_end=request.dragged_segment.selection_end,
            visual_lines=visual_lines,
            hotspot_rect=QRect(visual.hotspot_rect),
            chrome_path=chrome_path_from_rects(
                tuple(QRectF(rect) for rect in content_rects)
            ),
            outline_bounds=reorder_visual_bubble_union_rect(content_rects),
            slot_before=QPointF(visual.slot_before),
            slot_after=QPointF(visual.slot_after),
            marker_height=visual.marker_height,
        )
        active_placement = self.attach_expected_landing_to_active_placement(
            request,
            landing_geometry=geometry,
        )
        self.log_event(
            "landing_preview.placement_owned_geometry",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            **self.telemetry.held_shadow_context(self.held_shadow_geometry),
            **placement_geometry_context(
                active_placement,
                prefix="active_placement",
            ),
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )
        return PromptReorderLandingShadowGeometryResult(
            geometry=geometry,
            active_placement=active_placement,
        )

    def pending_landing_shadow_rect(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        reason: str,
    ) -> QRectF | None:
        """Return provisional visible chrome bounds for diagnostics and tests."""

        visual = self.pending_shadow_preview_visual(request, reason=reason)
        if visual is None:
            return None
        return reorder_visual_bubble_union_rect(visual.bubble_rects)

    def pending_shadow_preview_visual(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        reason: str,
    ) -> PromptChipVisual | None:
        """Return a provisional landing visual built from held chrome metrics."""

        held = self.held_shadow_geometry
        if (
            request.dragged_segment_index is None
            or request.active_target is None
            or request.active_placement is None
            or held is None
            or held.chip_index != request.dragged_segment_index
        ):
            self.log_event(
                "preview_shadow.pending_fallback_skipped",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                reason=reason,
                has_dragged_segment=request.dragged_segment_index is not None,
                has_active_target=request.active_target is not None,
                has_active_placement=request.active_placement is not None,
                held_shadow_matches_drag=(
                    held is not None
                    and held.chip_index == request.dragged_segment_index
                ),
                **self.telemetry.held_shadow_context(self.held_shadow_geometry),
            )
            return None
        anchor_rect = request.active_placement.insertion_anchor_rect
        left = anchor_rect.center().x()
        top = anchor_rect.center().y() - (held.chrome_bounds.height() / 2.0)
        fallback_visual = self.translated_held_shadow_visual(held, QPointF(left, top))
        fallback_visual = self.clamp_pending_shadow_visual(
            fallback_visual,
            content_rect=request.content_rect,
            overlay_rect=request.overlay_rect,
        )
        pending_chrome_bounds = reorder_visual_bubble_union_rect(
            fallback_visual.bubble_rects
        )
        self.log_pending_shadow_shape_diagnostics(
            request,
            fallback_visual,
            reason=reason,
        )
        self.log_event(
            "preview_shadow.pending_fallback_replaced_marker",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            **self.telemetry.held_shadow_context(self.held_shadow_geometry),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
            pending_shadow_footprint_height=f"{pending_chrome_bounds.height():.2f}",
            pending_shadow_anchor_x=f"{anchor_rect.center().x():.2f}",
            pending_shadow_anchor_y=f"{anchor_rect.center().y():.2f}",
            **self._preview_target_identity_context(
                request.preview_geometry_target_identity,
                prefix="preview_geometry_target",
            ),
            **self._preview_target_identity_context(
                request.expected_preview_target_identity,
                prefix="expected_preview_target",
            ),
            **self.telemetry.visual_context(fallback_visual, prefix="pending_shadow"),
        )
        return fallback_visual

    def translated_held_shadow_visual(
        self,
        held: PromptReorderHeldShadowGeometry,
        top_left: QPointF,
    ) -> PromptChipVisual:
        """Return held chrome metrics translated into overlay coordinates."""

        bubble_rects = tuple(
            QRectF(rect).translated(top_left) for rect in held.normalized_bubble_rects
        )
        chrome_bounds = reorder_visual_bubble_union_rect(bubble_rects)
        hotspot_rect = QRectF(held.hotspot_bounds).translated(top_left)
        first_rect = bubble_rects[0]
        last_rect = bubble_rects[-1]
        return PromptChipVisual(
            bubble_rects=bubble_rects,
            fragment_union_rect=chrome_bounds,
            hotspot_rect=hotspot_rect.toAlignedRect(),
            slot_before=QPointF(first_rect.left(), first_rect.center().y()),
            slot_after=QPointF(last_rect.right(), last_rect.center().y()),
            marker_height=max(rect.height() for rect in bubble_rects),
        )

    def clamp_pending_shadow_visual(
        self,
        visual: PromptChipVisual,
        *,
        content_rect: QRectF,
        overlay_rect: QRectF,
    ) -> PromptChipVisual:
        """Keep a provisional visual visible by translating, never resizing it."""

        chrome_bounds = reorder_visual_bubble_union_rect(visual.bubble_rects)
        clamped_bounds = self.clamp_pending_shadow_rect(
            chrome_bounds,
            content_rect=content_rect,
            overlay_rect=overlay_rect,
        )
        delta = clamped_bounds.topLeft() - chrome_bounds.topLeft()
        if delta.isNull():
            return visual
        translated_bubbles = tuple(
            QRectF(rect).translated(delta) for rect in visual.bubble_rects
        )
        translated_hotspot = QRectF(visual.hotspot_rect).translated(delta)
        translated_union = QRectF(visual.fragment_union_rect).translated(delta)
        return PromptChipVisual(
            bubble_rects=translated_bubbles,
            fragment_union_rect=translated_union,
            hotspot_rect=translated_hotspot.toAlignedRect(),
            slot_before=visual.slot_before + delta,
            slot_after=visual.slot_after + delta,
            marker_height=visual.marker_height,
        )

    def clamp_pending_shadow_rect(
        self,
        rect: QRectF,
        *,
        content_rect: QRectF,
        overlay_rect: QRectF,
    ) -> QRectF:
        """Keep a provisional shadow visible without changing its cached size."""

        bounds = QRectF(content_rect)
        if not bounds.isValid() or bounds.isEmpty():
            bounds = QRectF(overlay_rect)
        if not bounds.isValid() or bounds.isEmpty():
            return rect
        left = rect.left()
        if rect.width() <= bounds.width():
            left = min(max(left, bounds.left()), bounds.right() - rect.width())
        top = rect.top()
        if rect.height() <= bounds.height():
            top = min(max(top, bounds.top()), bounds.bottom() - rect.height())
        return QRectF(left, top, rect.width(), rect.height())

    def should_suppress_marker_for_landing_feedback(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> bool:
        """Return whether landing or pending feedback should replace the marker."""

        held = self.held_shadow_geometry
        if (
            held is not None
            and request.active_placement is not None
            and held.chip_index == request.dragged_segment_index
        ):
            self.log_event(
                "target_visual.marker_skipped_pending_fallback",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
                reason=self.last_landing_preview_skip_reason,
                **self.telemetry.held_shadow_context(held),
            )
            return True
        landing_geometry = request.landing_geometry
        if landing_geometry is not None and self.landing_shadow_matches_active_target(
            request,
            landing_geometry,
            emit_rejection=False,
        ):
            self.log_event(
                "target_visual.marker_skipped_landing_geometry",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
                **self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                ),
            )
            return True
        return False

    def is_chip_shaped_landing_shadow(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry | None,
    ) -> bool:
        """Return whether geometry is a real chip shadow rather than an anchor."""

        if geometry is None or request.dragged_segment_index is None:
            return False
        return (
            geometry.chip_index == request.dragged_segment_index
            and not geometry.chrome_path.isEmpty()
            and geometry.outline_bounds.width() >= _INITIAL_LANDING_SHADOW_MIN_WIDTH
            and geometry.hotspot_rect.width() >= _INITIAL_LANDING_SHADOW_MIN_WIDTH
        )

    def mark_initial_landing_shadow_ready(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry | None = None,
    ) -> None:
        """Record the first valid chip-shaped landing shadow for this gesture."""

        if self._initial_landing_shadow_ready:
            return
        if geometry is None:
            geometry = request.landing_geometry
        if not self.is_chip_shaped_landing_shadow(request, geometry):
            return
        self._initial_landing_shadow_ready = True
        self._increment_counter("initial_shadow_ready_count")
        self.log_event(
            "preview_sync.initial_shadow_ready",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            has_preview_snapshot=request.preview_snapshot_available,
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )

    def landing_shadow_matches_active_target(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        *,
        emit_rejection: bool,
    ) -> bool:
        """Return whether one chip shadow agrees with the active placement target."""

        if request.dragged_segment_index is None:
            return False
        if geometry.chip_index != request.dragged_segment_index:
            if emit_rejection:
                self.log_landing_shadow_rejection(
                    request,
                    geometry,
                    reason="wrong_chip",
                    anchor_dx=None,
                    anchor_dy=None,
                )
            return False
        if request.active_target is None or request.active_placement is None:
            return False
        if request.active_placement.target != request.active_target:
            if emit_rejection:
                self.log_landing_shadow_rejection(
                    request,
                    geometry,
                    reason="placement_target_mismatch",
                    anchor_dx=None,
                    anchor_dy=None,
                )
            return False
        if (
            request.active_placement.expected_landing_chip_index is not None
            and request.active_placement.expected_landing_chip_index
            != request.dragged_segment_index
        ):
            if emit_rejection:
                self.log_landing_shadow_rejection(
                    request,
                    geometry,
                    reason="expected_chip_mismatch",
                    anchor_dx=None,
                    anchor_dy=None,
                )
            return False

        if (
            request.preview_geometry_target_identity is not None
            and request.expected_preview_target_identity is not None
            and request.preview_geometry_target_identity
            != request.expected_preview_target_identity
        ):
            if emit_rejection:
                self.log_landing_shadow_rejection(
                    request,
                    geometry,
                    reason="preview_target_mismatch",
                    anchor_dx=None,
                    anchor_dy=None,
                )
            return False

        anchor_rect = request.active_placement.insertion_anchor_rect
        landing_anchor = geometry.slot_before
        anchor_dx = abs(landing_anchor.x() - anchor_rect.center().x())
        anchor_dy = abs(landing_anchor.y() - anchor_rect.center().y())
        threshold_y = max(1.0, anchor_rect.height())
        if emit_rejection and (
            anchor_dx > _TARGET_LANDING_MISMATCH_X or anchor_dy > threshold_y
        ):
            self.log_landing_anchor_wrap_delta(
                request,
                geometry,
                anchor_dx=anchor_dx,
                anchor_dy=anchor_dy,
                threshold_y=threshold_y,
            )
        return True

    def log_pending_shadow_shape_diagnostics(
        self,
        request: PromptReorderLandingShadowRequest,
        visual: PromptChipVisual,
        *,
        reason: str,
    ) -> None:
        """Log pending-vs-held and pending-vs-authoritative shape diagnostics."""

        held = self.held_shadow_geometry
        if held is None:
            return
        pending_chrome_bounds = reorder_visual_bubble_union_rect(visual.bubble_rects)
        pending_max_bubble_height = max(rect.height() for rect in visual.bubble_rects)
        held_max_bubble_height = max(
            rect.height() for rect in held.normalized_bubble_rects
        )
        if len(visual.bubble_rects) == 1 and len(held.normalized_bubble_rects) > 1:
            self._log_reorder_anomaly(
                request,
                "anomaly.pending_shadow_collapsed_wrapped_chip",
                reason=reason,
                dragged_segment_index=request.dragged_segment_index,
                pending_shadow_bubble_count=len(visual.bubble_rects),
                **self.telemetry.held_shadow_context(held),
                **self.telemetry.visual_context(visual, prefix="pending_shadow"),
            )
        if (
            abs(pending_max_bubble_height - held_max_bubble_height)
            > _SHADOW_SHAPE_MISMATCH
        ):
            self._log_reorder_anomaly(
                request,
                "anomaly.pending_shadow_chrome_height_mismatch",
                reason=reason,
                dragged_segment_index=request.dragged_segment_index,
                pending_shadow_max_bubble_height=f"{pending_max_bubble_height:.2f}",
                held_shadow_max_bubble_height=f"{held_max_bubble_height:.2f}",
                **self.telemetry.held_shadow_context(held),
                **self.telemetry.visual_context(visual, prefix="pending_shadow"),
            )
        if (
            len(visual.bubble_rects) == 1
            and abs(pending_max_bubble_height - held.hotspot_bounds.height())
            <= _SHADOW_SHAPE_MISMATCH
            and abs(held.hotspot_bounds.height() - held_max_bubble_height)
            > _SHADOW_SHAPE_MISMATCH
        ):
            self._log_reorder_anomaly(
                request,
                "anomaly.pending_shadow_used_hotspot_height",
                reason=reason,
                dragged_segment_index=request.dragged_segment_index,
                pending_shadow_max_bubble_height=f"{pending_max_bubble_height:.2f}",
                held_shadow_hotspot_height=f"{held.hotspot_bounds.height():.2f}",
                held_shadow_max_bubble_height=f"{held_max_bubble_height:.2f}",
                **self.telemetry.held_shadow_context(held),
            )
        authoritative_geometry = request.landing_geometry
        if authoritative_geometry is None:
            return
        authoritative_visual = prompt_reorder_visual_for_chip_geometry(
            authoritative_geometry
        )
        authoritative_chrome_bounds = reorder_visual_bubble_union_rect(
            authoritative_visual.bubble_rects
        )
        height_delta = (
            pending_chrome_bounds.height() - authoritative_chrome_bounds.height()
        )
        width_delta = (
            pending_chrome_bounds.width() - authoritative_chrome_bounds.width()
        )
        center_delta_x = (
            pending_chrome_bounds.center().x()
            - authoritative_chrome_bounds.center().x()
        )
        center_delta_y = (
            pending_chrome_bounds.center().y()
            - authoritative_chrome_bounds.center().y()
        )
        self.log_event(
            "preview_shadow.pending_authoritative_delta",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            pending_to_authoritative_height_delta=f"{height_delta:.2f}",
            pending_to_authoritative_width_delta=f"{width_delta:.2f}",
            pending_to_authoritative_center_delta_x=f"{center_delta_x:.2f}",
            pending_to_authoritative_center_delta_y=f"{center_delta_y:.2f}",
            authoritative_shadow_chrome_width=(
                f"{authoritative_chrome_bounds.width():.2f}"
            ),
            authoritative_shadow_chrome_height=(
                f"{authoritative_chrome_bounds.height():.2f}"
            ),
            pending_shadow_bubble_count=len(visual.bubble_rects),
            authoritative_shadow_bubble_count=len(authoritative_visual.bubble_rects),
            **self.telemetry.held_shadow_context(held),
        )
        if abs(height_delta) > _SHADOW_SHAPE_MISMATCH:
            self._log_reorder_anomaly(
                request,
                "anomaly.pending_authoritative_shadow_height_delta",
                reason=reason,
                dragged_segment_index=request.dragged_segment_index,
                pending_to_authoritative_height_delta=f"{height_delta:.2f}",
                pending_shadow_chrome_height=f"{pending_chrome_bounds.height():.2f}",
                authoritative_shadow_chrome_height=(
                    f"{authoritative_chrome_bounds.height():.2f}"
                ),
                **self.telemetry.held_shadow_context(held),
            )
        if len(visual.bubble_rects) != len(authoritative_visual.bubble_rects):
            self._log_expected_geometry_diagnostic(
                request,
                "diagnostic.pending_authoritative_shadow_bubble_count_delta",
                reason=reason,
                dragged_segment_index=request.dragged_segment_index,
                pending_shadow_bubble_count=len(visual.bubble_rects),
                authoritative_shadow_bubble_count=len(
                    authoritative_visual.bubble_rects
                ),
                **self.telemetry.held_shadow_context(held),
            )

    def log_landing_anchor_wrap_delta(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        *,
        anchor_dx: float,
        anchor_dy: float,
        threshold_y: float,
    ) -> None:
        """Log legitimate projection wrap movement away from the insertion anchor."""

        if request.active_placement is None:
            return
        anchor_rect = request.active_placement.insertion_anchor_rect
        landing_visual_line = (
            geometry.visual_lines[0].visual_line_index
            if geometry.visual_lines
            else None
        )
        placement_visual_line = request.active_placement.placement_id.visual_line_index
        self._log_expected_geometry_diagnostic(
            request,
            "diagnostic.landing_anchor_wrap_delta",
            dragged_segment_index=request.dragged_segment_index,
            landing_anchor_dx=f"{anchor_dx:.2f}",
            landing_anchor_dy=f"{anchor_dy:.2f}",
            landing_anchor_threshold_x=f"{_TARGET_LANDING_MISMATCH_X:.2f}",
            landing_anchor_threshold_y=f"{threshold_y:.2f}",
            landing_anchor_same_visual_line=(
                landing_visual_line == placement_visual_line
            ),
            landing_visual_line_index=landing_visual_line,
            placement_visual_line_index=placement_visual_line,
            preview_target_identity_matches=request.preview_target_identity_matches,
            **self._preview_target_identity_context(
                request.preview_geometry_target_identity,
                prefix="preview_geometry_target",
            ),
            **self.telemetry.target_context(
                request.active_target,
                prefix="active_target",
            ),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
            **reorder_drag_rect_context(anchor_rect, prefix="semantic_anchor"),
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )

    def log_landing_shadow_rejection(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        *,
        reason: str,
        anchor_dx: float | None,
        anchor_dy: float | None,
    ) -> None:
        """Log one stale-shadow rejection and make marker fallback observable."""

        self._increment_counter("stale_shadow_rejected_count")
        self.last_rejected_landing_shadow_target = request.active_target
        self.log_event(
            "preview_shadow.rejected_stale_target",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            last_landing_target_kind=reorder_drag_target_kind(
                self.last_landing_preview_target
            ),
            anchor_landing_slot_dx=(
                "none" if anchor_dx is None else f"{anchor_dx:.2f}"
            ),
            anchor_landing_slot_dy=(
                "none" if anchor_dy is None else f"{anchor_dy:.2f}"
            ),
            preview_fresh_for_target=(
                self.last_landing_preview_target == request.active_target
            ),
            preview_target_identity_matches=request.preview_target_identity_matches,
            **self._preview_target_identity_context(
                request.preview_geometry_target_identity,
                prefix="preview_geometry_target",
            ),
            **self._preview_target_identity_context(
                request.expected_preview_target_identity,
                prefix="expected_preview_target",
            ),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )
        self.log_event(
            "preview_geometry.lightweight_marker_used",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason="stale_shadow_rejected",
            active_target_kind=reorder_drag_target_kind(request.active_target),
            has_last_valid_shadow=self.last_landing_preview_geometry is not None,
            pending_fallback_available=self.held_shadow_geometry is not None,
            **self.telemetry.held_shadow_context(self.held_shadow_geometry),
        )

    def attach_expected_landing_to_active_placement(
        self,
        request: PromptReorderLandingShadowRequest,
        landing_geometry: PromptReorderChipGeometry | None = None,
    ) -> PromptReorderPlacementGeometry | None:
        """Attach preview-derived landing geometry to the active placement."""

        if request.active_placement is None:
            return None
        if landing_geometry is None:
            landing_geometry = request.landing_geometry
        if landing_geometry is None:
            missing_landing_is_anomaly = (
                request.dragged_segment_index is not None
                and request.active_placement.expected_landing_chip_index is None
            )
            log_method = (
                self._log_reorder_anomaly
                if missing_landing_is_anomaly
                else self._log_expected_geometry_diagnostic
            )
            log_method(
                request,
                "anomaly.placement_expected_landing_missing"
                if missing_landing_is_anomaly
                else "diagnostic.preview_landing_stale_or_missing",
                dragged_segment_index=request.dragged_segment_index,
                preview_visual_count=request.preview_visual_count,
                **placement_geometry_context(
                    request.active_placement,
                    prefix="active_placement",
                ),
            )
            return request.active_placement
        active_placement = request.active_placement.with_expected_landing_geometry(
            chip_index=landing_geometry.chip_index,
            expected_landing_bounds=QRectF(landing_geometry.hotspot_rect),
        )
        self.log_event(
            "placement_geometry.expected_landing",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
            **placement_geometry_context(
                active_placement,
                prefix="active_placement",
            ),
        )
        return active_placement

    def landing_preview_for_active_target(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> PromptReorderLandingShadowGeometryResult:
        """Return dragged-chip landing geometry for the active target."""

        self.last_landing_preview_skip_reason = "none"
        self.log_event(
            "landing_preview.request",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            has_preview_layout=request.preview_layout_active,
            **self.telemetry.target_context(
                request.active_target,
                prefix="active_target",
            ),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
        )
        if request.dragged_segment_index is None:
            self.last_landing_preview_skip_reason = "no_dragged_segment"
            self.log_event(
                "landing_preview.skipped_no_dragged_segment",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
            )
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )
        if request.active_target is None:
            self.last_landing_preview_skip_reason = "no_active_target"
            self.log_event(
                "landing_preview.skipped_no_active_target",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
            )
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )
        if not request.preview_layout_active:
            self.last_landing_preview_skip_reason = "no_preview_layout"
            self.log_event(
                "landing_preview.skipped_no_preview_layout",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
                **self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                ),
            )
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )

        landing_geometry = request.landing_geometry
        if landing_geometry is None:
            placement_owned = self.placement_owned_landing_geometry(
                request,
                reason="missing_authoritative_geometry",
            )
            if placement_owned.geometry is not None:
                self.last_landing_preview_skip_reason = "none"
                self.mark_initial_landing_shadow_ready(
                    request,
                    placement_owned.geometry,
                )
                return placement_owned

            self.last_landing_preview_skip_reason = "missing_authoritative_geometry"
            log_method = (
                self._log_expected_geometry_diagnostic
                if self.held_shadow_geometry is not None
                else self._log_reorder_anomaly
            )
            log_method(
                request,
                "diagnostic.chip_landing_geometry_missing_pending_fallback"
                if self.held_shadow_geometry is not None
                else "anomaly.chip_landing_geometry_missing",
                dragged_segment_index=request.dragged_segment_index,
                preview_visual_count=request.preview_visual_count,
                **self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                ),
            )
            self.log_event(
                "landing_preview.skipped_no_geometry",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
                preview_visual_count=request.preview_visual_count,
            )
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )

        if not self.landing_shadow_matches_active_target(
            request,
            landing_geometry,
            emit_rejection=True,
        ):
            self.last_landing_preview_skip_reason = "rejected_stale_target"
            self.log_event(
                "landing_preview.rejected_before_paint",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
                active_target_kind=reorder_drag_target_kind(request.active_target),
                **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
            )
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )

        active_placement = self.attach_expected_landing_to_active_placement(
            request,
            landing_geometry,
        )
        aligned_request = replace(request, active_placement=active_placement)
        self.mark_initial_landing_shadow_ready(aligned_request, landing_geometry)
        self._log_target_alignment(aligned_request, landing_geometry)
        return PromptReorderLandingShadowGeometryResult(
            geometry=landing_geometry,
            active_placement=active_placement,
        )

    def _drag_landing_preview_paint_state(
        self,
        request: PromptReorderLandingShadowRequest,
        landing_geometry: PromptReorderChipGeometry,
        *,
        visual_style: PromptReorderVisualStyle,
    ) -> PromptReorderLandingPreviewPaintState:
        """Return prepared landing geometry state and record diagnostics."""

        started_at = reorder_drag_started_at()
        style = visual_style.outline_style(
            outline_width=_LANDING_PREVIEW_OUTLINE_WIDTH,
            opacity=_LANDING_PREVIEW_OUTLINE_OPACITY,
        )
        if style.border_color.alpha() == 0 or style.opacity <= 0.0:
            self._log_reorder_anomaly(
                request,
                "anomaly.border_alpha_zero",
                dragged_segment_index=request.dragged_segment_index,
                **self.telemetry.style_context(style, prefix="landing_style"),
            )
        self.last_landing_preview_visual = prompt_reorder_visual_for_chip_geometry(
            landing_geometry
        )
        self.last_landing_preview_geometry = landing_geometry
        self.last_landing_preview_target = request.active_target
        self.last_landing_preview_event_id = request.event_id
        self.log_timing(
            "landing_preview.paint",
            started_at=started_at,
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            **self.telemetry.target_context(
                request.active_target,
                prefix="active_target",
            ),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
            **self.telemetry.style_context(style, prefix="landing_style"),
            **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
        )
        return PromptReorderLandingPreviewPaintState(
            style=style,
            geometry=landing_geometry,
        )

    def _pending_landing_shadow_paint_state(
        self,
        request: PromptReorderLandingShadowRequest,
        visual: PromptChipVisual,
        *,
        visual_style: PromptReorderVisualStyle,
        reason: str,
    ) -> PromptReorderLandingPreviewPaintState:
        """Return prepared pending-shadow state and record diagnostics."""

        started_at = reorder_drag_started_at()
        style = visual_style.outline_style(
            outline_width=_LANDING_PREVIEW_OUTLINE_WIDTH,
            opacity=_PENDING_LANDING_PREVIEW_OUTLINE_OPACITY,
        )
        pending_chrome_bounds = reorder_visual_bubble_union_rect(visual.bubble_rects)
        self._increment_counter("pending_shadow_fallback_count")
        self._increment_counter("pending_shadow_replaced_marker_count")
        self.log_timing(
            "preview_shadow.pending_fallback_used",
            started_at=started_at,
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            **self.telemetry.held_shadow_context(self.held_shadow_geometry),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
            **self.telemetry.style_context(style, prefix="pending_shadow_style"),
            pending_shadow_footprint_height=f"{pending_chrome_bounds.height():.2f}",
            **self._preview_target_identity_context(
                request.preview_geometry_target_identity,
                prefix="preview_geometry_target",
            ),
            **self._preview_target_identity_context(
                request.expected_preview_target_identity,
                prefix="expected_preview_target",
            ),
            **self.telemetry.visual_context(visual, prefix="pending_shadow"),
        )
        return PromptReorderLandingPreviewPaintState(style=style, visual=visual)

    def _store_held_shadow_geometry(
        self,
        *,
        chip_index: int,
        bubble_rects: tuple[QRectF, ...],
        hotspot_bounds: QRectF,
        source: str,
        gesture_id: int | None,
        event_id: int | None,
        low_confidence: bool = False,
    ) -> None:
        """Store valid held-chip chrome metrics and log their source."""

        chrome_bounds = reorder_visual_bubble_union_rect(bubble_rects)
        if not bubble_rects or not chrome_bounds.isValid() or chrome_bounds.isEmpty():
            self._increment_counter("held_shadow_missing_count")
            self.log_event(
                "preview_shadow.held_size_missing",
                gesture_id=gesture_id,
                event_id=event_id,
                dragged_segment_index=chip_index,
                shadow_origin=source,
                held_bubble_count=len(bubble_rects),
                held_chrome_width=f"{chrome_bounds.width():.2f}",
                held_chrome_height=f"{chrome_bounds.height():.2f}",
                held_hotspot_width=f"{hotspot_bounds.width():.2f}",
                held_hotspot_height=f"{hotspot_bounds.height():.2f}",
            )
            return
        normalized_bubble_rects = tuple(
            QRectF(rect).translated(-chrome_bounds.left(), -chrome_bounds.top())
            for rect in bubble_rects
        )
        normalized_hotspot_bounds = QRectF(hotspot_bounds).translated(
            -chrome_bounds.left(),
            -chrome_bounds.top(),
        )
        normalized_chrome_bounds = QRectF(chrome_bounds).translated(
            -chrome_bounds.left(),
            -chrome_bounds.top(),
        )
        self.held_shadow_geometry = PromptReorderHeldShadowGeometry(
            chip_index=chip_index,
            normalized_bubble_rects=normalized_bubble_rects,
            chrome_bounds=normalized_chrome_bounds,
            hotspot_bounds=normalized_hotspot_bounds,
            source=source,
            low_confidence=low_confidence,
        )
        self._increment_counter("held_shadow_capture_count")
        self.log_event(
            "preview_shadow.held_size_captured",
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=chip_index,
            **self.telemetry.held_shadow_context(self.held_shadow_geometry),
        )
        self.log_event(
            "preview_shadow.held_chrome_captured",
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=chip_index,
            **self.telemetry.held_shadow_context(self.held_shadow_geometry),
        )
        if low_confidence:
            self._log_expected_geometry_diagnostic(
                None,
                "diagnostic.low_confidence_shadow_metrics",
                dragged_segment_index=chip_index,
                **self.telemetry.held_shadow_context(self.held_shadow_geometry),
            )

    def _log_target_alignment(
        self,
        request: PromptReorderLandingShadowRequest,
        landing_geometry: PromptReorderChipGeometry,
    ) -> None:
        """Log alignment between landing geometry and target/placement anchors."""

        target_visual = request.target_visual
        if target_visual is None:
            self._log_reorder_anomaly(
                request,
                "anomaly.active_target_without_visual",
                dragged_segment_index=request.dragged_segment_index,
                **self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                ),
            )
            return
        landing_rect = QRectF(landing_geometry.hotspot_rect)
        target_rect = target_visual.hit_rect
        anchor_rect = (
            target_rect
            if request.active_placement is None
            else request.active_placement.insertion_anchor_rect
        )
        landing_to_anchor_dx = abs(
            landing_geometry.hotspot_rect.center().x() - anchor_rect.center().x()
        )
        landing_to_anchor_dy = abs(
            landing_geometry.hotspot_rect.center().y() - anchor_rect.center().y()
        )
        landing_to_hit_dx = abs(
            landing_geometry.hotspot_rect.center().x() - target_rect.center().x()
        )
        landing_to_hit_dy = abs(
            landing_geometry.hotspot_rect.center().y() - target_rect.center().y()
        )
        self.log_event(
            "landing_preview.target_alignment",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            landing_left_to_target_left_dx=(
                f"{landing_rect.left() - target_rect.left():.2f}"
            ),
            landing_center_to_target_center_dx=(
                f"{landing_rect.center().x() - target_rect.center().x():.2f}"
            ),
            landing_right_to_target_right_dx=(
                f"{landing_rect.right() - target_rect.right():.2f}"
            ),
            landing_center_to_target_center_dy=(
                f"{landing_rect.center().y() - target_rect.center().y():.2f}"
            ),
            landing_center_to_anchor_center_dx=(
                f"{landing_rect.center().x() - anchor_rect.center().x():.2f}"
            ),
            landing_center_to_anchor_center_dy=(
                f"{landing_rect.center().y() - anchor_rect.center().y():.2f}"
            ),
            **self.telemetry.target_context(
                request.active_target,
                prefix="active_target",
            ),
            **self.telemetry.target_visual_context(target_visual, prefix="target"),
            **reorder_drag_rect_context(anchor_rect, prefix="semantic_anchor"),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
            **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
        )
        threshold_y = max(1.0, anchor_rect.height())
        if (
            landing_to_anchor_dx > _TARGET_LANDING_MISMATCH_X
            or landing_to_anchor_dy > threshold_y
        ):
            diagnostic_context = {
                "dragged_segment_index": request.dragged_segment_index,
                "target_landing_center_dx": f"{landing_to_hit_dx:.2f}",
                "target_landing_center_dy": f"{landing_to_hit_dy:.2f}",
                "anchor_landing_center_dx": f"{landing_to_anchor_dx:.2f}",
                "anchor_landing_center_dy": f"{landing_to_anchor_dy:.2f}",
                "threshold_x": f"{_TARGET_LANDING_MISMATCH_X:.2f}",
                "threshold_y": f"{threshold_y:.2f}",
                **self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                ),
                **reorder_drag_rect_context(
                    target_visual.hit_rect, prefix="target_hit"
                ),
                **reorder_drag_rect_context(anchor_rect, prefix="semantic_anchor"),
                **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
            }
            if isinstance(request.active_target, PromptGapBlankLineDropTarget):
                self._log_expected_geometry_diagnostic(
                    request,
                    "diagnostic.blank_line_landing_offset",
                    **diagnostic_context,
                )
            elif target_visual.hit_rect.width() >= max(
                1.0,
                request.content_rect.width() - 1.0,
            ):
                self._log_expected_geometry_diagnostic(
                    request,
                    "diagnostic.full_width_target_offset",
                    **diagnostic_context,
                )
            else:
                self._log_expected_geometry_diagnostic(
                    request,
                    "diagnostic.landing_anchor_wrap_delta",
                    preview_target_identity_matches=(
                        request.preview_target_identity_matches
                    ),
                    **self._preview_target_identity_context(
                        request.preview_geometry_target_identity,
                        prefix="preview_geometry_target",
                    ),
                    **diagnostic_context,
                )
        elif isinstance(request.active_target, PromptLineDropTarget) and (
            landing_to_hit_dx > _TARGET_LANDING_MISMATCH_X
            or landing_to_hit_dy > max(1.0, target_visual.hit_rect.height())
        ):
            self._log_expected_geometry_diagnostic(
                request,
                "diagnostic.line_hit_rect_offset",
                dragged_segment_index=request.dragged_segment_index,
                target_landing_center_dx=f"{landing_to_hit_dx:.2f}",
                target_landing_center_dy=f"{landing_to_hit_dy:.2f}",
                anchor_landing_center_dx=f"{landing_to_anchor_dx:.2f}",
                anchor_landing_center_dy=f"{landing_to_anchor_dy:.2f}",
                threshold_x=f"{_TARGET_LANDING_MISMATCH_X:.2f}",
                threshold_y=f"{threshold_y:.2f}",
                **self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                ),
                **reorder_drag_rect_context(
                    target_visual.hit_rect, prefix="target_hit"
                ),
                **reorder_drag_rect_context(anchor_rect, prefix="semantic_anchor"),
                **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
            )

        if (
            request.active_placement is not None
            and request.active_placement.expected_landing_rect is not None
        ):
            expected_rect = request.active_placement.expected_landing_rect
            expected_dx = abs(landing_rect.center().x() - expected_rect.center().x())
            expected_dy = abs(landing_rect.center().y() - expected_rect.center().y())
            self.log_event(
                "placement_geometry.landing_alignment",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                dragged_segment_index=request.dragged_segment_index,
                landing_expected_center_dx=f"{expected_dx:.2f}",
                landing_expected_center_dy=f"{expected_dy:.2f}",
                **placement_geometry_context(
                    request.active_placement,
                    prefix="active_placement",
                ),
                **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
            )
            if expected_dx > _TARGET_LANDING_MISMATCH_X or expected_dy > max(
                1.0,
                expected_rect.height(),
            ):
                self._log_reorder_anomaly(
                    request,
                    "anomaly.chip_geometry_commit_mismatch",
                    dragged_segment_index=request.dragged_segment_index,
                    landing_expected_center_dx=f"{expected_dx:.2f}",
                    landing_expected_center_dy=f"{expected_dy:.2f}",
                    **placement_geometry_context(
                        request.active_placement,
                        prefix="active_placement",
                    ),
                    **chip_geometry_context(
                        landing_geometry,
                        prefix="landing_geometry",
                    ),
                )

    def _preview_target_identity_context(
        self,
        identity: PromptReorderPreviewTargetIdentity | None,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return structured fields for one preview target identity."""

        if identity is None:
            return {
                f"{prefix}_dragged_segment_index": None,
                f"{prefix}_target_kind": "none",
                f"{prefix}_source_layout_key": "none",
            }
        return {
            f"{prefix}_dragged_segment_index": identity.dragged_segment_index,
            f"{prefix}_target_kind": reorder_drag_target_kind(identity.target),
            f"{prefix}_source_layout_key": repr(identity.source_fingerprint),
            f"{prefix}_preview_layout_key": repr(identity.preview_layout_key),
            f"{prefix}_base_drag_layout_key": repr(identity.base_drag_layout_key),
            f"{prefix}_viewport_identity": repr(identity.viewport_identity),
        }

    def _log_reorder_anomaly(
        self,
        request: PromptReorderLandingShadowRequest | None,
        event: str,
        **context: object,
    ) -> None:
        """Emit and count one landing-shadow anomaly."""

        self._increment_counter("anomaly_count")
        self.log_event(
            event,
            gesture_id=None if request is None else request.gesture_id,
            event_id=None if request is None else request.event_id,
            **context,
        )

    def _log_expected_geometry_diagnostic(
        self,
        request: PromptReorderLandingShadowRequest | None,
        event: str,
        **context: object,
    ) -> None:
        """Emit and count one expected landing-shadow geometry diagnostic."""

        self._increment_counter("expected_diagnostic_count")
        self.log_event(
            event,
            gesture_id=None if request is None else request.gesture_id,
            event_id=None if request is None else request.event_id,
            **context,
        )

    def _increment_counter(self, field_name: str) -> None:
        """Increment one immutable counter field by name."""

        self._counters = replace(
            self._counters,
            **{field_name: getattr(self._counters, field_name) + 1},
        )


def _chip_geometry_key(
    geometry: PromptReorderChipGeometry | None,
) -> tuple[object, ...] | None:
    """Return a value identity for landing outline geometry."""

    if geometry is None:
        return None
    return (
        geometry.geometry_id,
        geometry.chip_index,
        geometry.source_start,
        geometry.source_end,
        geometry.rendered_start,
        geometry.rendered_end,
        tuple(
            (
                line.visual_line_index,
                _rect_key(line.line_rect),
                _rect_key(line.content_rect),
                _point_key(line.leading_anchor),
                _point_key(line.trailing_anchor),
            )
            for line in geometry.visual_lines
        ),
        _rect_key(geometry.hotspot_rect),
        _rect_key(geometry.outline_bounds),
        _point_key(geometry.slot_before),
        _point_key(geometry.slot_after),
        geometry.marker_height,
    )


def _placement_key(
    placement: PromptReorderPlacementGeometry | None,
) -> tuple[object, ...] | None:
    """Return a value identity for placement geometry used by landing paint."""

    if placement is None:
        return None
    return (
        placement.placement_id,
        placement.target,
        _rect_key(placement.hit_rect),
        _rect_key(placement.insertion_anchor_rect),
        _rect_key(placement.visual_line_rect),
        _optional_rect_key(placement.expected_landing_rect),
        placement.source_before,
        placement.source_after,
        placement.adjacent_chip_indices,
        placement.expected_landing_chip_index,
        _optional_rect_key(placement.expected_landing_bounds),
    )


def _held_shadow_key(
    geometry: PromptReorderHeldShadowGeometry | None,
) -> tuple[object, ...] | None:
    """Return a value identity for held-shadow fallback inputs."""

    if geometry is None:
        return None
    return (
        geometry.chip_index,
        tuple(_rect_key(rect) for rect in geometry.normalized_bubble_rects),
        _rect_key(geometry.chrome_bounds),
        _rect_key(geometry.hotspot_bounds),
        geometry.source,
        geometry.low_confidence,
    )


def _optional_rect_key(rect: QRectF | None) -> tuple[float, float, float, float] | None:
    """Return a value identity for an optional Qt rectangle."""

    if rect is None:
        return None
    return _rect_key(rect)


def _rect_key(rect: QRectF | QRect) -> tuple[float, float, float, float]:
    """Return a value identity for a Qt rectangle."""

    return (rect.x(), rect.y(), rect.width(), rect.height())


def _point_key(point: QPointF) -> tuple[float, float]:
    """Return a value identity for a Qt point."""

    return (point.x(), point.y())


__all__ = [
    "PromptReorderHeldShadowCaptureInput",
    "PromptReorderHeldShadowGeometry",
    "PromptReorderInitialShadowSyncResult",
    "PromptReorderLandingShadowCounters",
    "PromptReorderLandingShadowGeometryResult",
    "PromptReorderLandingShadowPaintResult",
    "PromptReorderLandingShadowPresenter",
    "PromptReorderLandingShadowRequest",
]
