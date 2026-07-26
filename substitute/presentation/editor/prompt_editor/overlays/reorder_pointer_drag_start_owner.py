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

"""Own the complete transition into a pointer reorder drag."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QPointF

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import (
    next_reorder_drag_gesture_id,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from .reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from .reorder_autoscroll import PromptReorderAutoscrollOwner
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_drop_commit_diagnostics import PromptReorderDropCommitDiagnostics
from .reorder_gesture_controller import (
    PromptReorderDragIntent,
    PromptReorderGestureController,
)
from .reorder_held_drag_context import PromptReorderHeldDragContextOwner
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_interaction_intents import PromptReorderInteractionIntentOwner
from .reorder_landing_paint import PromptReorderLandingPaintOwner
from .reorder_live_placement import live_gap_ranges_for_layout
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_performance_counters import PromptReorderPerformanceCountersOwner
from .reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from .reorder_pointer_target_transition import (
    PromptReorderPointerTargetTransitionOwner,
)
from .reorder_preview_layout_transition_owner import (
    PromptReorderPreviewLayoutTransitionOwner,
)
from .reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner


class PromptReorderPointerDragStartOwner:
    """Establish one drag's geometry, visuals, counters, and target state."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        visual_mode: PromptReorderVisualModeOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        intents: PromptReorderInteractionIntentOwner,
        metrics: PromptReorderInteractionMetricsOwner,
        performance: PromptReorderPerformanceCountersOwner,
        animation: PromptReorderAnimationPresentationOwner,
        autoscroll: PromptReorderAutoscrollOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        visual_session: PromptReorderVisualSessionOwner,
        landing_preview: PromptReorderLandingPaintOwner,
        drop_diagnostics: PromptReorderDropCommitDiagnostics,
        held_context: PromptReorderHeldDragContextOwner,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        preview_layout: PromptReorderPreviewLayoutTransitionOwner,
        target_transition: PromptReorderPointerTargetTransitionOwner,
        pointer_regions: PromptReorderPointerRegionVisualOwner,
        render: PromptReorderRenderPublicationOwner,
        map_global_to_overlay: Callable[[QPoint], QPoint],
        preview_layout_changed: Callable[[], None],
    ) -> None:
        """Bind complete drag-start owners and two exact Qt adapters."""

        self._geometry = geometry
        self._gesture = gesture
        self._visual_mode = visual_mode
        self._live_visuals = live_visuals
        self._intents = intents
        self._metrics = metrics
        self._performance = performance
        self._animation = animation
        self._autoscroll = autoscroll
        self._diagnostics = diagnostics
        self._visual_session = visual_session
        self._landing_preview = landing_preview
        self._drop_diagnostics = drop_diagnostics
        self._held_context = held_context
        self._drag_proxy = drag_proxy
        self._preview_layout = preview_layout
        self._target_transition = target_transition
        self._pointer_regions = pointer_regions
        self._render = render
        self._map_global_to_overlay = map_global_to_overlay
        self._preview_layout_changed = preview_layout_changed

    def prepare(self, segment_index: int) -> None:
        """Prepare immutable held-chip presentation before drag threshold."""

        self._animation.settle(reason="pointer_press")
        self._drag_proxy.prepare_segment_render_state(
            segment=self._visual_session.segments_by_index[segment_index],
            source_revision=self._visual_session.source_revision,
            visual_style=self._render.visual_style,
            interaction=self._gesture.state,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )

    def start(
        self,
        segment_index: int,
        *,
        global_position: QPoint,
        press_global_position: QPoint,
    ) -> None:
        """Begin one drag when its coherent document and layout are available."""

        if self._gesture.state.dragged_segment_index is not None:
            return
        geometry_state = self._geometry.state
        current_layout = geometry_state.current_layout_view
        document = geometry_state.document_view
        if current_layout is None or document is None:
            return
        preview_chip_geometry = geometry_state.preview_chip_geometry_snapshot
        painted_chip_geometry = (
            preview_chip_geometry
            if self._visual_mode.preview_active() and preview_chip_geometry is not None
            else self._live_visuals.chip_geometry
        )
        self._intents.publish_drag(
            PromptReorderDragIntent(
                phase="start",
                segment_index=segment_index,
                global_position=global_position,
            )
        )

        gesture_id = next_reorder_drag_gesture_id()
        event_id = self._metrics.begin_gesture(gesture_id)
        self._performance.reset_for_gesture()
        self._autoscroll.clear_pending_invalidation()
        total_started_at = reorder_drag_started_at()
        self._diagnostics.log_event(
            "start",
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=segment_index,
            segment_count=len(self._visual_session.segments_by_index),
            row_count=len(current_layout.rows),
            gap_count=len(current_layout.gaps),
            ordered_count=len(geometry_state.ordered_segment_indices),
        )
        self._gesture.begin_pointer_drag(
            segment_index=segment_index,
            global_position=global_position,
        )
        phase_started_at = reorder_drag_started_at()
        base_drag_layout = self._geometry.begin_drag(
            dragged_segment_index=segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        if base_drag_layout is None:
            return
        self._diagnostics.log_timing(
            "start.base_drag_layout",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            row_count=len(base_drag_layout.rows),
            gap_count=len(base_drag_layout.gaps),
        )
        self._geometry.clear_preview_target_identity()
        self._gesture.set_active_drop_target(None)
        self._geometry.set_active_placement(None)
        self._landing_preview.reset_drag_state()
        self._drop_diagnostics.clear()
        phase_started_at = reorder_drag_started_at()
        self._held_context.capture(
            segment_index,
            local_pointer=QPointF(self._map_global_to_overlay(press_global_position)),
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )
        self._drag_proxy.begin_segment_render_state(
            segment=self._visual_session.segments_by_index[segment_index],
            source_revision=self._visual_session.source_revision,
            visual_style=self._render.visual_style,
            interaction=self._gesture.state,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )
        self._diagnostics.log_timing(
            "start.capture_intent",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            **_drag_intent_context(self._gesture),
        )
        live_gap_ranges = live_gap_ranges_for_layout(
            document.source_text,
            base_drag_layout,
            self._visual_session.segments_by_index,
        )
        if live_gap_ranges is not None and painted_chip_geometry is not None:
            self._geometry.prime_base_drag_placement_from_painted_projection(
                chip_geometry_snapshot=painted_chip_geometry,
                gap_ranges_by_index=live_gap_ranges,
                gesture_id=gesture_id,
                event_id=event_id,
            )
        self._preview_layout.update()
        self._preview_layout_changed()
        visual_revision = self._render.publication.revision
        self._target_transition.update(
            QPointF(self._map_global_to_overlay(global_position))
        )
        preview_sync_applied = self._render.publication.revision != visual_revision
        if not preview_sync_applied:
            self._pointer_regions.sync_geometry()
        self._drag_proxy.show()
        self._drag_proxy.move(
            global_position,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )
        self._autoscroll.update_for_pointer(global_position)
        if not preview_sync_applied:
            self._render.sync(reason="drag_started")
        self._diagnostics.log_timing(
            "start.total",
            started_at=total_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
            lane_count=len(self._geometry.state.drop_target_lanes),
            visual_target_count=len(self._geometry.state.drop_target_visuals),
        )


def _drag_intent_context(
    gesture: PromptReorderGestureController,
) -> dict[str, object]:
    """Return bounded drag-intent geometry for start diagnostics."""

    state = gesture.state
    return {
        "drag_grab_offset_x": (
            "none"
            if state.drag_grab_offset is None
            else f"{state.drag_grab_offset.x():.2f}"
        ),
        "drag_grab_offset_y": (
            "none"
            if state.drag_grab_offset is None
            else f"{state.drag_grab_offset.y():.2f}"
        ),
        "drag_intent_width": (
            "none"
            if state.drag_intent_size is None
            else f"{state.drag_intent_size.width():.2f}"
        ),
        "drag_intent_height": (
            "none"
            if state.drag_intent_size is None
            else f"{state.drag_intent_size.height():.2f}"
        ),
    }
