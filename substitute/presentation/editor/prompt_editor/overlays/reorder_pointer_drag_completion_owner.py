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

"""Own committed and cancelled pointer reorder completion transitions."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QRectF

from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCommitIntent,
)

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import (
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
from .reorder_commit_snapshot import prompt_reorder_commit_snapshot
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_drop_actual_observation import PromptReorderDropActualObservation
from .reorder_drop_commit_diagnostics import (
    PromptReorderDropCommitDiagnostics,
    PromptReorderDropReleaseObservation,
)
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
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_performance_counters import PromptReorderPerformanceCountersOwner
from .reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from .reorder_pointer_regions import PromptReorderPointerRegions
from .reorder_preview_layout_transition_owner import (
    PromptReorderPreviewLayoutTransitionOwner,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner


class PromptReorderPointerDragCompletionOwner:
    """Commit or cancel one drag and complete every visual lifecycle."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        visual_mode: PromptReorderVisualModeOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        intents: PromptReorderInteractionIntentOwner,
        metrics: PromptReorderInteractionMetricsOwner,
        autoscroll: PromptReorderAutoscrollOwner,
        animation: PromptReorderAnimationPresentationOwner,
        landing_preview: PromptReorderLandingPaintOwner,
        drop_diagnostics: PromptReorderDropCommitDiagnostics,
        held_context: PromptReorderHeldDragContextOwner,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        preview_layout: PromptReorderPreviewLayoutTransitionOwner,
        pointer_regions: PromptReorderPointerRegionVisualOwner,
        region_widgets: PromptReorderPointerRegions,
        render: PromptReorderRenderPublicationOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        performance: PromptReorderPerformanceCountersOwner,
        visual_session: PromptReorderVisualSessionOwner,
        preview_layout_changed: Callable[[], None],
    ) -> None:
        """Bind complete completion owners and the exact preview event adapter."""

        self._geometry = geometry
        self._gesture = gesture
        self._visual_mode = visual_mode
        self._live_visuals = live_visuals
        self._preview_visuals = preview_visuals
        self._intents = intents
        self._metrics = metrics
        self._autoscroll = autoscroll
        self._animation = animation
        self._landing_preview = landing_preview
        self._drop_diagnostics = drop_diagnostics
        self._held_context = held_context
        self._drag_proxy = drag_proxy
        self._preview_layout = preview_layout
        self._pointer_regions = pointer_regions
        self._region_widgets = region_widgets
        self._render = render
        self._diagnostics = diagnostics
        self._performance = performance
        self._visual_session = visual_session
        self._preview_layout_changed = preview_layout_changed

    def end(self, segment_index: int) -> None:
        """Commit the active drag and publish its actual visual observation."""

        if self._gesture.state.dragged_segment_index != segment_index:
            return
        last_position = self._gesture.state.last_drag_global_position
        self._intents.publish_drag(
            PromptReorderDragIntent(
                phase="end",
                segment_index=segment_index,
                global_position=last_position or QPoint(),
            )
        )
        total_started_at = reorder_drag_started_at()
        event_id = self._metrics.begin_event()
        self._autoscroll.flush_pending_invalidation(
            reason="autoscroll_pointer_drop_settle"
        )
        self._animation.settle(reason="pointer_drop")
        ending_target = self._gesture.state.active_drop_target
        landing_publication = self._landing_preview.state.publication
        self._drop_diagnostics.log_release(
            PromptReorderDropReleaseObservation.from_publications(
                dragged_segment_index=segment_index,
                ending_target=ending_target,
                landing=landing_publication,
                preview_visuals=self._preview_visuals.visuals_by_index,
                geometry=self._geometry.state,
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
            )
        )
        geometry_state = self._geometry.state
        if (
            geometry_state.preview_layout_view is not None
            and self._gesture.state.active_drop_target is not None
            and geometry_state.current_layout_view is not None
        ):
            self._geometry.commit_preview_layout()
            geometry_state = self._geometry.state
            self._gesture.set_committed_dragged_segment(segment_index)
            self._drop_diagnostics.capture(
                landing=landing_publication,
                target=ending_target,
                geometry=geometry_state,
                segment_index=segment_index,
                gesture_id=self._metrics.gesture_id,
                event_id=event_id,
            )
        else:
            self._gesture.set_active_drop_target(None)
            self._geometry.set_active_placement(None)
            self._geometry.clear_preview_target_identity()
            self._drop_diagnostics.clear()
        self._gesture.finish_pointer_drag(
            committed_segment_index=None,
            clear_target=False,
        )
        self._landing_preview.reset_drag_state()
        self._held_context.clear(preserve_preview=True)
        self._geometry.clear_preview_target_identity()
        self._drag_proxy.hide()
        self._autoscroll.stop()
        self._autoscroll.clear_pending_invalidation()
        self._preview_layout.update()
        self._pointer_regions.sync_geometry()
        chip = self._region_widgets.regions_by_index.get(segment_index)
        geometry_state = self._geometry.state
        self._drop_diagnostics.log_actual(
            PromptReorderDropActualObservation.from_publications(
                checkpoint="end_drag.after_geometry_update",
                segment_index=segment_index,
                live_visuals=self._live_visuals.visuals_by_index,
                preview_visuals=self._preview_visuals.visuals_by_index,
                live_chip_geometry=self._live_visuals.chip_geometry,
                chip_rect=None if chip is None else QRectF(chip.rect),
                preview_mode_active=self._visual_mode.preview_active(),
                geometry=geometry_state,
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
            )
        )
        self._render.sync(reason="drag_ended")
        self._preview_layout_changed()
        has_reordered = self._visual_mode.has_reordered()
        gesture_state = self._gesture.state
        self._intents.publish_commit(
            PromptReorderCommitIntent(
                reason="pointer_drop",
                snapshot=prompt_reorder_commit_snapshot(
                    self._geometry.state,
                    active_segment_index=gesture_state.active_segment_index,
                    dragged_segment_index=gesture_state.dragged_segment_index,
                    has_reordered=has_reordered,
                ),
            )
        )
        self._diagnostics.log_timing(
            "end.total",
            started_at=total_started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=event_id,
            dragged_segment_index=segment_index,
            committed_target_kind=reorder_drag_target_kind(ending_target),
            has_reordered=has_reordered,
            ordered_count=len(self._geometry.state.ordered_segment_indices),
            move_count=self._metrics.drag_move_count,
        )
        self._log_summary(outcome="end")
        self._metrics.finish_gesture()

    def cancel(self) -> None:
        """Restore the original layout and clear every drag visual."""

        total_started_at = reorder_drag_started_at()
        event_id = self._metrics.begin_event()
        self._animation.settle(reason="drag_cancelled")
        self._gesture.cancel_drag()
        self._geometry.set_active_placement(None)
        self._landing_preview.reset_drag_state()
        self._held_context.clear()
        self._geometry.clear_preview_target_identity()
        self._geometry.restore_original_layout()
        self._drag_proxy.hide()
        self._autoscroll.stop()
        self._autoscroll.clear_pending_invalidation()
        self._preview_layout.update()
        self._pointer_regions.sync_geometry()
        self._render.sync(reason="drag_cancelled")
        self._preview_layout_changed()
        self._diagnostics.log_timing(
            "cancel.total",
            started_at=total_started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=event_id,
            move_count=self._metrics.drag_move_count,
        )
        self._log_summary(outcome="cancel")
        self._metrics.finish_gesture()
        self._drop_diagnostics.clear()

    def _log_summary(self, *, outcome: str) -> None:
        """Publish one completion summary from authoritative owner counters."""

        self._diagnostics.log_gesture_summary_from_publications(
            outcome=outcome,
            chip_geometry=self._live_visuals.chip_geometry,
            geometry=self._geometry.state,
            expected_chip_count=len(self._visual_session.segments_by_index),
            landing_counters=self._landing_preview.counters,
            owner_counters=self._performance.owner_counters(),
        )
