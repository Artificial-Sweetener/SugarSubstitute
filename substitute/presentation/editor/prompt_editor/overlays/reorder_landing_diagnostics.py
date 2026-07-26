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

"""Own reorder landing diagnostic classification and structured context."""

from __future__ import annotations

from dataclasses import dataclass, replace
from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
)

from ..projection.observability import (
    reorder_drag_rect_context,
    reorder_drag_target_kind,
)
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    chip_geometry_context,
)
from ..projection.reorder_placement_geometry import placement_geometry_context
from ..projection.reorder_interaction_geometry_identity import (
    reorder_preview_target_identity_context,
)
from .chip_visuals import PromptChipVisual, prompt_chip_bubble_union_rect
from .reorder_event_ports import PromptReorderEventLogger
from .reorder_landing_models import (
    PromptReorderHeldShadowGeometry,
    PromptReorderLandingShadowRequest,
)
from .reorder_telemetry import PromptReorderTelemetry
from .reorder_visual_geometry import prompt_reorder_visual_for_chip_geometry

_TARGET_LANDING_MISMATCH_X = 24.0
_SHADOW_SHAPE_MISMATCH = 1.0


@dataclass(frozen=True, slots=True)
class PromptReorderLandingDiagnosticCounters:
    """Expose diagnostic classifications without owning interaction state."""

    anomaly_count: int = 0
    expected_diagnostic_count: int = 0


@dataclass(slots=True)
class PromptReorderLandingDiagnostics:
    """Classify landing geometry observations and publish bounded diagnostics."""

    telemetry: PromptReorderTelemetry
    log_event: PromptReorderEventLogger
    _counters: PromptReorderLandingDiagnosticCounters = (
        PromptReorderLandingDiagnosticCounters()
    )

    @property
    def counters(self) -> PromptReorderLandingDiagnosticCounters:
        """Return immutable diagnostic classification counters."""

        return self._counters

    def reset(self) -> None:
        """Reset per-drag diagnostic counters."""

        self._counters = PromptReorderLandingDiagnosticCounters()

    def pending_shadow_shape(
        self,
        request: PromptReorderLandingShadowRequest,
        visual: PromptChipVisual,
        held: PromptReorderHeldShadowGeometry | None,
        *,
        reason: str,
    ) -> None:
        """Compare pending chrome with held and authoritative geometry."""

        if held is None:
            return
        pending_chrome_bounds = prompt_chip_bubble_union_rect(visual.bubble_rects)
        pending_max_bubble_height = max(rect.height() for rect in visual.bubble_rects)
        held_max_bubble_height = max(
            rect.height() for rect in held.normalized_bubble_rects
        )
        if len(visual.bubble_rects) == 1 and len(held.normalized_bubble_rects) > 1:
            self.anomaly(
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
            self.anomaly(
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
            self.anomaly(
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
        authoritative_chrome_bounds = prompt_chip_bubble_union_rect(
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
            self.anomaly(
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
            self.expected(
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

    def landing_anchor_wrap_delta(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        *,
        anchor_dx: float,
        anchor_dy: float,
        threshold_x: float,
        threshold_y: float,
    ) -> None:
        """Record legitimate projection wrap movement from the insertion anchor."""

        if request.active_placement is None:
            return
        anchor_rect = request.active_placement.insertion_anchor_rect
        landing_visual_line = (
            geometry.visual_lines[0].visual_line_index
            if geometry.visual_lines
            else None
        )
        placement_visual_line = request.active_placement.placement_id.visual_line_index
        self.expected(
            request,
            "diagnostic.landing_anchor_wrap_delta",
            dragged_segment_index=request.dragged_segment_index,
            landing_anchor_dx=f"{anchor_dx:.2f}",
            landing_anchor_dy=f"{anchor_dy:.2f}",
            landing_anchor_threshold_x=f"{threshold_x:.2f}",
            landing_anchor_threshold_y=f"{threshold_y:.2f}",
            landing_anchor_same_visual_line=(
                landing_visual_line == placement_visual_line
            ),
            landing_visual_line_index=landing_visual_line,
            placement_visual_line_index=placement_visual_line,
            preview_target_identity_matches=request.preview_target_identity_matches,
            **reorder_preview_target_identity_context(
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

    def landing_shadow_rejection(
        self,
        request: PromptReorderLandingShadowRequest,
        geometry: PromptReorderChipGeometry,
        *,
        reason: str,
        anchor_dx: float | None,
        anchor_dy: float | None,
        last_landing_preview_target: PromptReorderDropTarget | None,
        last_landing_preview_geometry: PromptReorderChipGeometry | None,
        held_shadow_geometry: PromptReorderHeldShadowGeometry | None,
    ) -> None:
        """Publish one stale-shadow rejection and marker-fallback context."""

        self.log_event(
            "preview_shadow.rejected_stale_target",
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=reason,
            dragged_segment_index=request.dragged_segment_index,
            active_target_kind=reorder_drag_target_kind(request.active_target),
            last_landing_target_kind=reorder_drag_target_kind(
                last_landing_preview_target
            ),
            anchor_landing_slot_dx=(
                "none" if anchor_dx is None else f"{anchor_dx:.2f}"
            ),
            anchor_landing_slot_dy=(
                "none" if anchor_dy is None else f"{anchor_dy:.2f}"
            ),
            preview_fresh_for_target=(
                last_landing_preview_target == request.active_target
            ),
            preview_target_identity_matches=request.preview_target_identity_matches,
            **reorder_preview_target_identity_context(
                request.preview_geometry_target_identity,
                prefix="preview_geometry_target",
            ),
            **reorder_preview_target_identity_context(
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
            has_last_valid_shadow=last_landing_preview_geometry is not None,
            pending_fallback_available=held_shadow_geometry is not None,
            **self.telemetry.held_shadow_context(held_shadow_geometry),
        )

    def target_alignment(
        self,
        request: PromptReorderLandingShadowRequest,
        landing_geometry: PromptReorderChipGeometry,
    ) -> None:
        """Record alignment between landing geometry and target anchors."""

        target_visual = request.target_visual
        if target_visual is None:
            self.anomaly(
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
                    target_visual.hit_rect,
                    prefix="target_hit",
                ),
                **reorder_drag_rect_context(anchor_rect, prefix="semantic_anchor"),
                **chip_geometry_context(landing_geometry, prefix="landing_geometry"),
            }
            if isinstance(request.active_target, PromptGapBlankLineDropTarget):
                self.expected(
                    request,
                    "diagnostic.blank_line_landing_offset",
                    **diagnostic_context,
                )
            elif target_visual.hit_rect.width() >= max(
                1.0,
                request.content_rect.width() - 1.0,
            ):
                self.expected(
                    request,
                    "diagnostic.full_width_target_offset",
                    **diagnostic_context,
                )
            else:
                self.expected(
                    request,
                    "diagnostic.landing_anchor_wrap_delta",
                    preview_target_identity_matches=(
                        request.preview_target_identity_matches
                    ),
                    **reorder_preview_target_identity_context(
                        request.preview_geometry_target_identity,
                        prefix="preview_geometry_target",
                    ),
                    **diagnostic_context,
                )
        elif isinstance(request.active_target, PromptLineDropTarget) and (
            landing_to_hit_dx > _TARGET_LANDING_MISMATCH_X
            or landing_to_hit_dy > max(1.0, target_visual.hit_rect.height())
        ):
            self.expected(
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
                    target_visual.hit_rect,
                    prefix="target_hit",
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
                **chip_geometry_context(
                    landing_geometry,
                    prefix="landing_geometry",
                ),
            )
            if expected_dx > _TARGET_LANDING_MISMATCH_X or expected_dy > max(
                1.0,
                expected_rect.height(),
            ):
                self.anomaly(
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

    def anomaly(
        self,
        request: PromptReorderLandingShadowRequest | None,
        event: str,
        **context: object,
    ) -> None:
        """Publish and count one landing-shadow anomaly."""

        self._counters = replace(
            self._counters,
            anomaly_count=self._counters.anomaly_count + 1,
        )
        self.log_event(
            event,
            gesture_id=None if request is None else request.gesture_id,
            event_id=None if request is None else request.event_id,
            **context,
        )

    def expected(
        self,
        request: PromptReorderLandingShadowRequest | None,
        event: str,
        **context: object,
    ) -> None:
        """Publish and count one expected landing geometry diagnostic."""

        self._counters = replace(
            self._counters,
            expected_diagnostic_count=self._counters.expected_diagnostic_count + 1,
        )
        self.log_event(
            event,
            gesture_id=None if request is None else request.gesture_id,
            event_id=None if request is None else request.event_id,
            **context,
        )


__all__ = [
    "PromptReorderLandingDiagnosticCounters",
    "PromptReorderLandingDiagnostics",
]
