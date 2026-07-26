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

"""Prepare cached reorder landing paint from already resolved feedback."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..projection.observability import reorder_drag_started_at
from .reorder_landing_diagnostics import PromptReorderLandingDiagnostics
from .reorder_landing_events import PromptReorderLandingEventPublisher
from .reorder_landing_models import (
    PromptReorderLandingShadowCounters,
    PromptReorderLandingShadowRequest,
)
from .reorder_landing_paint_cache import (
    PromptReorderLandingPaintCache,
    PromptReorderLandingShadowPaintResult,
    prompt_reorder_landing_paint_key,
)
from .reorder_landing_paint_policy import (
    prompt_reorder_landing_geometry_paint_state,
    prompt_reorder_pending_landing_paint_state,
)
from .reorder_landing_resolution import PromptReorderLandingResolutionOwner
from .reorder_landing_state import PromptReorderLandingStateOwner
from .reorder_telemetry import PromptReorderTelemetry
from .reorder_visual_style import PromptReorderVisualStyle


@dataclass(slots=True)
class PromptReorderLandingPaintOwner:
    """Own bounded landing-paint cache reuse and paint-state conversion."""

    telemetry: PromptReorderTelemetry
    resolution: PromptReorderLandingResolutionOwner
    state: PromptReorderLandingStateOwner
    diagnostics: PromptReorderLandingDiagnostics
    events: PromptReorderLandingEventPublisher
    _paint_cache: PromptReorderLandingPaintCache = field(
        default_factory=PromptReorderLandingPaintCache
    )

    @property
    def counters(self) -> PromptReorderLandingShadowCounters:
        """Return landing diagnostics and paint-cache counters in one snapshot."""

        cache_metrics = self._paint_cache.metrics
        diagnostic_counters = self.diagnostics.counters
        operational = self.state.counters
        return PromptReorderLandingShadowCounters(
            initial_shadow_sync_count=operational.initial_shadow_sync_count,
            initial_shadow_ready_count=operational.initial_shadow_ready_count,
            stale_shadow_rejected_count=operational.stale_shadow_rejected_count,
            held_shadow_capture_count=operational.held_shadow_capture_count,
            held_shadow_missing_count=operational.held_shadow_missing_count,
            pending_shadow_fallback_count=operational.pending_shadow_fallback_count,
            pending_shadow_replaced_marker_count=(
                operational.pending_shadow_replaced_marker_count
            ),
            anomaly_count=diagnostic_counters.anomaly_count,
            expected_diagnostic_count=diagnostic_counters.expected_diagnostic_count,
            paint_cache_hit_count=cache_metrics.hit_count,
            paint_cache_miss_count=cache_metrics.miss_count,
        )

    def reset_drag_state(self) -> None:
        """Clear all drag-scoped landing state before preparing a new drag."""

        self.state.reset()
        self.diagnostics.reset()
        self._paint_cache.clear()
        self._paint_cache.reset_metrics()

    def clear_preview_state(self) -> None:
        """Discard cached preview paint after the preview state changes."""

        self._paint_cache.clear()

    def clear_held_shadow(self) -> None:
        """Discard cached paint that depends on held-shadow geometry."""

        self._paint_cache.clear()

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
        publication = self.state.publication
        cache_key = prompt_reorder_landing_paint_key(
            request,
            visual_style=visual_style,
            held_shadow_geometry=publication.held_shadow_geometry,
            initial_landing_shadow_ready=publication.initial_shadow_ready,
            initial_landing_shadow_sync_used=publication.initial_shadow_sync_used,
        )
        cached = self._paint_cache.lookup(cache_key)
        if cached is not None:
            return cached
        result = self._build_landing_preview_paint_state(
            request,
            visual_style=visual_style,
        )
        self._paint_cache.store(cache_key, result)
        return result

    def _build_landing_preview_paint_state(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        visual_style: PromptReorderVisualStyle,
    ) -> PromptReorderLandingShadowPaintResult:
        """Convert one resolved landing state to a passive paint publication."""

        feedback = self.resolution.resolve_feedback(request)
        if feedback.geometry is not None:
            paint_state = prompt_reorder_landing_geometry_paint_state(
                visual_style,
                feedback.geometry,
            )
            if (
                paint_state.style.border_color.alpha() == 0
                or paint_state.style.opacity <= 0.0
            ):
                self.diagnostics.anomaly(
                    request,
                    "anomaly.border_alpha_zero",
                    dragged_segment_index=request.dragged_segment_index,
                    **self.telemetry.style_context(
                        paint_state.style,
                        prefix="landing_style",
                    ),
                )
            self.events.landing_painted(
                request,
                feedback.geometry,
                paint_state.style,
                started_at=reorder_drag_started_at(),
            )
            return PromptReorderLandingShadowPaintResult(
                paint_state=paint_state,
                active_placement=feedback.active_placement,
            )
        if feedback.pending_visual is None:
            return PromptReorderLandingShadowPaintResult(
                paint_state=None,
                active_placement=feedback.active_placement,
            )
        paint_state = prompt_reorder_pending_landing_paint_state(
            visual_style,
            feedback.pending_visual,
        )
        self.events.pending_fallback_painted(
            request,
            feedback.pending_visual,
            self.state.publication.held_shadow_geometry,
            paint_state.style,
            started_at=reorder_drag_started_at(),
            reason=feedback.skip_reason,
        )
        return PromptReorderLandingShadowPaintResult(
            paint_state=paint_state,
            active_placement=feedback.active_placement,
        )


__all__ = ["PromptReorderLandingPaintOwner"]
