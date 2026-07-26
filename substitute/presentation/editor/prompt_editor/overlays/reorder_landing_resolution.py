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

"""Resolve authoritative reorder landing feedback independently of paint."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QRectF

from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from ..projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    placement_geometry_context,
)
from .chip_visuals import PromptChipVisual, prompt_chip_bubble_union_rect
from .reorder_landing_diagnostics import PromptReorderLandingDiagnostics
from .reorder_landing_events import PromptReorderLandingEventPublisher
from .reorder_landing_geometry import (
    prompt_reorder_is_chip_shaped_landing,
    prompt_reorder_landing_target_match,
    prompt_reorder_pending_shadow_visual,
    prompt_reorder_placement_landing_geometry,
)
from .reorder_landing_models import (
    PromptReorderInitialShadowSyncResult,
    PromptReorderLandingShadowGeometryResult,
    PromptReorderLandingShadowRequest,
)
from .reorder_landing_state import PromptReorderLandingStateOwner
from .reorder_telemetry import PromptReorderTelemetry
from .reorder_visual_geometry import prompt_reorder_visual_for_chip_geometry


@dataclass(frozen=True, slots=True)
class PromptReorderLandingResolvedFeedback:
    """Describe one resolved landing feedback state before paint preparation."""

    geometry: PromptReorderChipGeometry | None
    pending_visual: PromptChipVisual | None
    active_placement: PromptReorderPlacementGeometry | None
    skip_reason: str


@dataclass(slots=True)
class PromptReorderLandingResolutionOwner:
    """Own landing validity, geometry agreement, and semantic state transitions."""

    telemetry: PromptReorderTelemetry
    state: PromptReorderLandingStateOwner
    diagnostics: PromptReorderLandingDiagnostics
    events: PromptReorderLandingEventPublisher

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
        valid = prompt_reorder_is_chip_shaped_landing(request, geometry)
        if valid and placement_owned.geometry is None and geometry is not None:
            valid = self.landing_shadow_matches_active_target(
                request,
                geometry,
                emit_rejection=False,
            )
        self.events.initial_shadow_probe(
            request,
            geometry,
            self.state.publication,
            is_chip_shaped=(
                geometry is not None
                and prompt_reorder_is_chip_shaped_landing(request, geometry)
            ),
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
        """Consume the one permitted immediate first-shadow synchronization."""

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
        if self.state.publication.initial_shadow_sync_used:
            self.events.initial_shadow_already_used(request)
            return PromptReorderInitialShadowSyncResult(
                should_flush=False,
                active_placement=probe.active_placement,
            )
        self.state.consume_initial_shadow_sync()
        self.events.immediate_initial_shadow_missing(request)
        return PromptReorderInitialShadowSyncResult(
            should_flush=True,
            active_placement=probe.active_placement,
        )

    def initial_shadow_sync(
        self,
        request: PromptReorderLandingShadowRequest,
        base_drag_layout_available: bool,
    ) -> PromptReorderInitialShadowSyncResult:
        """Resolve initial-shadow synchronization through the callback boundary."""

        return self.should_flush_initial_landing_shadow_sync(
            request,
            base_drag_layout_available=base_drag_layout_available,
        )

    def placement_owned_landing_geometry(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        reason: str,
    ) -> PromptReorderLandingShadowGeometryResult:
        """Derive current-target landing geometry from placement state."""

        geometry = prompt_reorder_placement_landing_geometry(
            request,
            self.state.publication.held_shadow_geometry,
        )
        if geometry is None:
            return PromptReorderLandingShadowGeometryResult(
                geometry=None,
                active_placement=request.active_placement,
            )
        active_placement = self.attach_expected_landing_to_active_placement(
            request,
            landing_geometry=geometry,
        )
        self.events.placement_owned_geometry(
            request,
            reason=reason,
            held=self.state.publication.held_shadow_geometry,
            active_placement=active_placement,
            geometry=geometry,
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
        return prompt_chip_bubble_union_rect(visual.bubble_rects)

    def pending_shadow_preview_visual(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        reason: str,
    ) -> PromptChipVisual | None:
        """Build a provisional landing visual from held chrome metrics."""

        held = self.state.publication.held_shadow_geometry
        fallback_visual = prompt_reorder_pending_shadow_visual(request, held)
        if fallback_visual is None or request.active_placement is None:
            self.events.pending_fallback_skipped(request, held, reason=reason)
            return None
        self.diagnostics.pending_shadow_shape(
            request,
            fallback_visual,
            held,
            reason=reason,
        )
        self.events.pending_fallback_replaced_marker(
            request,
            fallback_visual,
            held,
            reason=reason,
        )
        return fallback_visual

    def should_suppress_marker_for_landing_feedback(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> bool:
        """Return whether landing or pending feedback replaces the marker."""

        publication = self.state.publication
        held = publication.held_shadow_geometry
        if (
            held is not None
            and request.active_placement is not None
            and held.chip_index == request.dragged_segment_index
        ):
            self.events.marker_skipped_for_pending(
                request,
                held,
                reason=publication.last_preview_skip_reason,
            )
            return True
        landing_geometry = request.landing_geometry
        if landing_geometry is not None and self.landing_shadow_matches_active_target(
            request,
            landing_geometry,
            emit_rejection=False,
        ):
            self.events.marker_skipped_for_geometry(request)
            return True
        return False

    def mark_initial_landing_shadow_ready(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry | None = None,
    ) -> None:
        """Record the first valid chip-shaped landing shadow for this gesture."""

        if self.state.publication.initial_shadow_ready:
            return
        if geometry is None:
            geometry = request.landing_geometry
        if not prompt_reorder_is_chip_shaped_landing(request, geometry):
            return
        self.state.mark_initial_shadow_ready()
        if geometry is not None:
            self.events.initial_shadow_ready(request, geometry)

    def landing_shadow_matches_active_target(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        *,
        emit_rejection: bool,
    ) -> bool:
        """Return whether one chip shadow agrees with the active target."""

        match = prompt_reorder_landing_target_match(request, geometry)
        if not match.accepted:
            if emit_rejection and match.rejection_reason is not None:
                publication = self.state.publication
                self.state.record_rejected_target(request.active_target)
                self.diagnostics.landing_shadow_rejection(
                    request,
                    geometry,
                    reason=match.rejection_reason,
                    anchor_dx=match.anchor_dx,
                    anchor_dy=match.anchor_dy,
                    last_landing_preview_target=publication.last_preview_target,
                    last_landing_preview_geometry=publication.last_preview_geometry,
                    held_shadow_geometry=publication.held_shadow_geometry,
                )
            return False
        if (
            emit_rejection
            and match.anchor_dx is not None
            and match.anchor_dy is not None
            and match.threshold_x is not None
            and match.threshold_y is not None
            and (
                match.anchor_dx > match.threshold_x
                or match.anchor_dy > match.threshold_y
            )
        ):
            self.diagnostics.landing_anchor_wrap_delta(
                request,
                geometry,
                anchor_dx=match.anchor_dx,
                anchor_dy=match.anchor_dy,
                threshold_x=match.threshold_x,
                threshold_y=match.threshold_y,
            )
        return True

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
                self.diagnostics.anomaly
                if missing_landing_is_anomaly
                else self.diagnostics.expected
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
        self.events.expected_landing(request, landing_geometry, active_placement)
        return active_placement

    def resolve_feedback(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> PromptReorderLandingResolvedFeedback:
        """Resolve and publish one semantic feedback result before it is painted."""

        geometry_result = self.landing_preview_for_active_target(request)
        if geometry_result.geometry is not None:
            geometry = geometry_result.geometry
            self.state.publish_preview(
                visual=prompt_reorder_visual_for_chip_geometry(geometry),
                geometry=geometry,
                target=request.active_target,
                event_id=request.event_id,
            )
            return PromptReorderLandingResolvedFeedback(
                geometry=geometry,
                pending_visual=None,
                active_placement=geometry_result.active_placement,
                skip_reason="none",
            )
        skip_reason = self.state.publication.last_preview_skip_reason
        pending_visual = self.pending_shadow_preview_visual(
            request,
            reason=skip_reason,
        )
        if pending_visual is not None:
            self.state.record_pending_fallback()
        return PromptReorderLandingResolvedFeedback(
            geometry=None,
            pending_visual=pending_visual,
            active_placement=geometry_result.active_placement,
            skip_reason=skip_reason,
        )

    def landing_preview_for_active_target(
        self,
        request: PromptReorderLandingShadowRequest,
    ) -> PromptReorderLandingShadowGeometryResult:
        """Return dragged-chip landing geometry for the active target."""

        self.state.set_skip_reason("none")
        self.events.preview_requested(request)
        if request.dragged_segment_index is None:
            self.state.set_skip_reason("no_dragged_segment")
            self.events.preview_skipped(request, "no_dragged_segment")
            return PromptReorderLandingShadowGeometryResult(
                None, request.active_placement
            )
        if request.active_target is None:
            self.state.set_skip_reason("no_active_target")
            self.events.preview_skipped(request, "no_active_target")
            return PromptReorderLandingShadowGeometryResult(
                None, request.active_placement
            )
        if not request.preview_layout_active:
            self.state.set_skip_reason("no_preview_layout")
            self.events.preview_skipped(request, "no_preview_layout")
            return PromptReorderLandingShadowGeometryResult(
                None, request.active_placement
            )

        landing_geometry = request.landing_geometry
        if landing_geometry is None:
            placement_owned = self.placement_owned_landing_geometry(
                request,
                reason="missing_authoritative_geometry",
            )
            if placement_owned.geometry is not None:
                self.state.set_skip_reason("none")
                self.mark_initial_landing_shadow_ready(
                    request, placement_owned.geometry
                )
                return placement_owned

            self.state.set_skip_reason("missing_authoritative_geometry")
            log_method = (
                self.diagnostics.expected
                if self.state.publication.held_shadow_geometry is not None
                else self.diagnostics.anomaly
            )
            log_method(
                request,
                "diagnostic.chip_landing_geometry_missing_pending_fallback"
                if self.state.publication.held_shadow_geometry is not None
                else "anomaly.chip_landing_geometry_missing",
                dragged_segment_index=request.dragged_segment_index,
                preview_visual_count=request.preview_visual_count,
                **self.telemetry.target_context(
                    request.active_target,
                    prefix="active_target",
                ),
            )
            self.events.preview_skipped(request, "missing_authoritative_geometry")
            return PromptReorderLandingShadowGeometryResult(
                None, request.active_placement
            )

        if not self.landing_shadow_matches_active_target(
            request,
            landing_geometry,
            emit_rejection=True,
        ):
            self.state.set_skip_reason("rejected_stale_target")
            self.events.preview_rejected(request, landing_geometry)
            return PromptReorderLandingShadowGeometryResult(
                None, request.active_placement
            )

        active_placement = self.attach_expected_landing_to_active_placement(
            request,
            landing_geometry,
        )
        aligned_request = replace(request, active_placement=active_placement)
        self.mark_initial_landing_shadow_ready(aligned_request, landing_geometry)
        self.diagnostics.target_alignment(aligned_request, landing_geometry)
        return PromptReorderLandingShadowGeometryResult(
            geometry=landing_geometry,
            active_placement=active_placement,
        )


__all__ = ["PromptReorderLandingResolutionOwner"]
