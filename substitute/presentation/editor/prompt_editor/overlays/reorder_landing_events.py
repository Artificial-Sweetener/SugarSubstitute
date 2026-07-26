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

"""Publish prompt-safe operational events for reorder landing visuals."""

from __future__ import annotations

from dataclasses import dataclass

from ..projection.observability import reorder_drag_target_kind
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    chip_geometry_context,
)
from ..projection.reorder_interaction_geometry_identity import (
    reorder_preview_target_identity_context,
)
from ..projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    placement_geometry_context,
)
from .chip_painter import PromptChipPaintStyle
from .chip_visuals import PromptChipVisual, prompt_chip_bubble_union_rect
from .reorder_event_ports import PromptReorderEventLogger, PromptReorderTimingLogger
from .reorder_landing_capture import PromptReorderHeldShadowCaptureOutcome
from .reorder_landing_models import (
    PromptReorderHeldShadowCaptureInput,
    PromptReorderHeldShadowGeometry,
    PromptReorderLandingShadowRequest,
)
from .reorder_landing_state import PromptReorderLandingState
from .reorder_telemetry import PromptReorderTelemetry


@dataclass(slots=True)
class PromptReorderLandingEventPublisher:
    """Own operational landing event names and structured context assembly."""

    telemetry: PromptReorderTelemetry
    log_event: PromptReorderEventLogger
    log_timing: PromptReorderTimingLogger

    def held_shadow_missing(
        self,
        capture: PromptReorderHeldShadowCaptureInput,
        outcome: PromptReorderHeldShadowCaptureOutcome,
    ) -> None:
        """Publish a held-shadow capture miss."""

        self.log_event(
            "preview_shadow.held_size_missing",
            gesture_id=capture.gesture_id,
            event_id=capture.event_id,
            dragged_segment_index=capture.chip_index,
            shadow_origin=outcome.source,
            held_bubble_count=outcome.bubble_count,
            held_chrome_width=f"{outcome.chrome_bounds.width():.2f}",
            held_chrome_height=f"{outcome.chrome_bounds.height():.2f}",
            held_hotspot_width=f"{outcome.hotspot_bounds.width():.2f}",
            held_hotspot_height=f"{outcome.hotspot_bounds.height():.2f}",
        )

    def held_shadow_captured(
        self,
        capture: PromptReorderHeldShadowCaptureInput,
        geometry: PromptReorderHeldShadowGeometry,
    ) -> dict[str, object]:
        """Publish held-shadow capture events and return reusable context."""

        context = self.telemetry.held_shadow_context(geometry)
        common = {
            "gesture_id": capture.gesture_id,
            "event_id": capture.event_id,
            "dragged_segment_index": capture.chip_index,
            **context,
        }
        self.log_event("preview_shadow.held_size_captured", **common)
        self.log_event("preview_shadow.held_chrome_captured", **common)
        return context

    def initial_shadow_probe(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry | None,
        state: PromptReorderLandingState,
        *,
        is_chip_shaped: bool,
    ) -> None:
        """Publish one initial landing-shadow validity probe."""

        self.log_event(
            "preview_sync.initial_shadow_probe",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            has_preview_snapshot=request.preview_snapshot_available,
            has_landing_geometry=geometry is not None,
            is_chip_shaped=is_chip_shaped,
            initial_shadow_ready=state.initial_shadow_ready,
            initial_shadow_sync_used=state.initial_shadow_sync_used,
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )

    def initial_shadow_already_used(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> None:
        """Publish refusal to repeat immediate initial-shadow synchronization."""

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

    def immediate_initial_shadow_missing(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> None:
        """Publish the one immediate synchronization request."""

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

    def placement_owned_geometry(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        reason: str,
        held: PromptReorderHeldShadowGeometry | None,
        active_placement: PromptReorderPlacementGeometry | None,
        geometry: PromptReorderChipGeometry,
    ) -> None:
        """Publish placement-derived fallback geometry."""

        self.log_event(
            "landing_preview.placement_owned_geometry",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            **self.telemetry.held_shadow_context(held),
            **placement_geometry_context(
                active_placement,
                prefix="active_placement",
            ),
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )

    def pending_fallback_skipped(
        self,
        request: PromptReorderLandingShadowRequest,
        held: PromptReorderHeldShadowGeometry | None,
        *,
        reason: str,
    ) -> None:
        """Publish why pending held-shadow chrome could not be prepared."""

        self.log_event(
            "preview_shadow.pending_fallback_skipped",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            has_dragged_segment=request.dragged_segment_index is not None,
            has_active_target=request.active_target is not None,
            has_active_placement=request.active_placement is not None,
            held_shadow_matches_drag=(
                held is not None and held.chip_index == request.dragged_segment_index
            ),
            **self.telemetry.held_shadow_context(held),
        )

    def pending_fallback_replaced_marker(
        self,
        request: PromptReorderLandingShadowRequest,
        visual: PromptChipVisual,
        held: PromptReorderHeldShadowGeometry | None,
        *,
        reason: str,
    ) -> None:
        """Publish pending chrome that replaces the lightweight marker."""

        active_placement = request.active_placement
        if active_placement is None:
            return
        chrome_bounds = prompt_chip_bubble_union_rect(visual.bubble_rects)
        anchor_rect = active_placement.insertion_anchor_rect
        self.log_event(
            "preview_shadow.pending_fallback_replaced_marker",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            **self.telemetry.held_shadow_context(held),
            **placement_geometry_context(
                active_placement,
                prefix="active_placement",
            ),
            pending_shadow_footprint_height=f"{chrome_bounds.height():.2f}",
            pending_shadow_anchor_x=f"{anchor_rect.center().x():.2f}",
            pending_shadow_anchor_y=f"{anchor_rect.center().y():.2f}",
            **reorder_preview_target_identity_context(
                request.preview_geometry_target_identity,
                prefix="preview_geometry_target",
            ),
            **reorder_preview_target_identity_context(
                request.expected_preview_target_identity,
                prefix="expected_preview_target",
            ),
            **self.telemetry.visual_context(visual, prefix="pending_shadow"),
        )

    def marker_skipped_for_pending(
        self,
        request: PromptReorderLandingShadowRequest,
        held: PromptReorderHeldShadowGeometry,
        *,
        reason: str,
    ) -> None:
        """Publish marker suppression in favor of pending held chrome."""

        self.log_event(
            "target_visual.marker_skipped_pending_fallback",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            reason=reason,
            **self.telemetry.held_shadow_context(held),
        )

    def marker_skipped_for_geometry(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> None:
        """Publish marker suppression in favor of authoritative geometry."""

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

    def initial_shadow_ready(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
    ) -> None:
        """Publish first valid chip-shaped landing readiness."""

        self.log_event(
            "preview_sync.initial_shadow_ready",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            has_preview_snapshot=request.preview_snapshot_available,
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )

    def expected_landing(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        active_placement: PromptReorderPlacementGeometry,
    ) -> None:
        """Publish preview-derived expected landing placement."""

        self.log_event(
            "placement_geometry.expected_landing",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            **chip_geometry_context(geometry, prefix="landing_geometry"),
            **placement_geometry_context(
                active_placement,
                prefix="active_placement",
            ),
        )

    def preview_requested(self, request: PromptReorderLandingShadowRequest) -> None:
        """Publish one landing-preview request."""

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

    def preview_skipped(
        self,
        request: PromptReorderLandingShadowRequest,
        reason: str,
    ) -> None:
        """Publish one bounded landing-preview skip reason."""

        context: dict[str, object] = {
            "gesture_id": request.gesture_id,
            "event_id": request.event_id,
        }
        if reason != "no_dragged_segment":
            context["dragged_segment_index"] = request.dragged_segment_index
        if reason == "no_preview_layout":
            context.update(
                self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                )
            )
        if reason == "missing_authoritative_geometry":
            context["preview_visual_count"] = request.preview_visual_count
        self.log_event(
            {
                "no_dragged_segment": "landing_preview.skipped_no_dragged_segment",
                "no_active_target": "landing_preview.skipped_no_active_target",
                "no_preview_layout": "landing_preview.skipped_no_preview_layout",
                "missing_authoritative_geometry": (
                    "landing_preview.skipped_no_geometry"
                ),
            }[reason],
            **context,
        )

    def preview_rejected(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
    ) -> None:
        """Publish stale landing geometry rejected before paint."""

        self.log_event(
            "landing_preview.rejected_before_paint",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )

    def landing_painted(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        style: PromptChipPaintStyle,
        *,
        started_at: float,
    ) -> None:
        """Publish timing and context for authoritative landing paint."""

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
            **chip_geometry_context(geometry, prefix="landing_geometry"),
        )

    def pending_fallback_painted(
        self,
        request: PromptReorderLandingShadowRequest,
        visual: PromptChipVisual,
        held: PromptReorderHeldShadowGeometry | None,
        style: PromptChipPaintStyle,
        *,
        reason: str,
        started_at: float,
    ) -> None:
        """Publish timing and context for pending held-shadow paint."""

        chrome_bounds = prompt_chip_bubble_union_rect(visual.bubble_rects)
        self.log_timing(
            "preview_shadow.pending_fallback_used",
            started_at=started_at,
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            **self.telemetry.held_shadow_context(held),
            **placement_geometry_context(
                request.active_placement,
                prefix="active_placement",
            ),
            **self.telemetry.style_context(style, prefix="pending_shadow_style"),
            pending_shadow_footprint_height=f"{chrome_bounds.height():.2f}",
            **reorder_preview_target_identity_context(
                request.preview_geometry_target_identity,
                prefix="preview_geometry_target",
            ),
            **reorder_preview_target_identity_context(
                request.expected_preview_target_identity,
                prefix="expected_preview_target",
            ),
            **self.telemetry.visual_context(visual, prefix="pending_shadow"),
        )


__all__ = ["PromptReorderLandingEventPublisher"]
