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

"""Own controller-preview adoption into one prepared reorder frame."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderPreviewSnapshot,
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
from .reorder_animation_paint_policy import (
    animation_plan_with_complete_paint_ownership,
)
from .reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from .reorder_drop_actual_observation import PromptReorderDropActualObservation
from .reorder_drop_commit_diagnostics import PromptReorderDropCommitDiagnostics
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from .reorder_pointer_regions import PromptReorderPointerRegions
from .reorder_preview_geometry_refresh_owner import (
    PromptReorderPreviewGeometryRefreshOwner,
)
from .reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_refresh_identity import PromptReorderRefreshIdentityOwner
from .reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner


class PromptReorderPreviewFrameTransitionOwner:
    """Adopt one projection preview and publish its complete visual frame."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        visual_mode: PromptReorderVisualModeOwner,
        visual_session: PromptReorderVisualSessionOwner,
        viewport: PromptReorderViewportGeometryOwner,
        refresh_identity: PromptReorderRefreshIdentityOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        preview_geometry: PromptReorderPreviewGeometryRefreshOwner,
        preview_paint_snapshots: PromptReorderPreviewPaintSnapshotOwner,
        pointer_region_visuals: PromptReorderPointerRegionVisualOwner,
        pointer_regions: PromptReorderPointerRegions,
        animation: PromptReorderAnimationPresentationOwner,
        render: PromptReorderRenderPublicationOwner,
        drop_diagnostics: PromptReorderDropCommitDiagnostics,
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
    ) -> None:
        """Bind exact publications participating in preview adoption."""

        self._geometry = geometry
        self._gesture = gesture
        self._visual_mode = visual_mode
        self._visual_session = visual_session
        self._viewport = viewport
        self._refresh_identity = refresh_identity
        self._live_visuals = live_visuals
        self._preview_visuals = preview_visuals
        self._preview_geometry = preview_geometry
        self._preview_paint_snapshots = preview_paint_snapshots
        self._pointer_region_visuals = pointer_region_visuals
        self._pointer_regions = pointer_regions
        self._animation = animation
        self._render = render
        self._drop_diagnostics = drop_diagnostics
        self._metrics = metrics
        self._diagnostics = diagnostics

    def apply(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Adopt one preview projection and publish its prepared visual frame."""

        started_at = reorder_drag_started_at()
        animation_start_rects = self._animation.current_visible_chip_rects(
            segment_indices=tuple(self._pointer_regions.regions_by_index),
            preview_active=self._visual_mode.preview_active(),
            live_visuals_by_index=self._live_visuals.visuals_by_index,
            preview_visuals_by_index=self._preview_visuals.visuals_by_index,
        )
        self._animation.cancel(reason="preview_snapshot_refresh")
        self._geometry.set_preview_snapshots(
            snapshot,
            base_drag_snapshot=base_drag_snapshot,
            ordered_chip_indices=ordered_chip_indices,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
            viewport_identity=self._viewport.position_geometry_key(),
        )
        self._preview_geometry.refresh()
        geometry_state = self._geometry.state
        animation_plan = self._animation.build_plan_if_ready(
            current_visuals=animation_start_rects,
            proposed_layout_view=self._visual_mode.painted_preview_layout(),
            preview_geometry=geometry_state.preview_chip_geometry_snapshot,
            ordered_segment_indices=geometry_state.ordered_segment_indices,
        )
        snapshot_indices = (
            frozenset()
            if animation_plan is None
            else frozenset(
                target.segment_index for target in animation_plan.changed_targets
            )
        )
        dragged_segment_index = self._gesture.state.dragged_segment_index
        if dragged_segment_index is not None:
            snapshot_indices = snapshot_indices | {dragged_segment_index}
        self._preview_paint_snapshots.prepare(snapshot_indices)
        if animation_plan is not None:
            animation_plan = animation_plan_with_complete_paint_ownership(
                animation_plan,
                snapshot_indices=frozenset(
                    self._preview_paint_snapshots.snapshots_by_index
                ),
            )
        self._pointer_region_visuals.sync_geometry_if_needed(
            reason="set_preview_snapshot"
        )
        if animation_plan is None:
            self._render.sync(reason="set_preview_snapshot")
        else:
            self._animation.apply_plan(
                animation_plan,
                preview_geometry=geometry_state.preview_chip_geometry_snapshot,
            )
        position_key = self._viewport.position_geometry_key()
        self._refresh_identity.record_publication(
            position_key=position_key,
            refresh_key=self._refresh_identity.build_refresh_key(
                position_key=position_key,
                segments_by_index=self._visual_session.segments_by_index,
                content_rect=self._viewport.published_content_rect,
                geometry_state=self._geometry.state,
                dragged_segment_index=self._gesture.state.dragged_segment_index,
                active_target=self._gesture.state.active_drop_target,
            ),
        )
        self._record_preview_freshness()
        self._record_committed_drop_actual()
        self._diagnostics.log_timing(
            "overlay.set_preview_snapshot",
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            has_preview_snapshot=snapshot is not None,
            has_base_drag_snapshot=base_drag_snapshot is not None,
            ordered_count=len(self._geometry.state.ordered_segment_indices),
            preview_visual_count=len(self._preview_visuals.visuals_by_index),
            lane_count=len(self._geometry.state.drop_target_lanes),
        )

    def _record_preview_freshness(self) -> None:
        """Record whether preview placement caught the active target."""

        if self._gesture.state.active_drop_target is None:
            self._diagnostics.log_event(
                "preview_state.fresh",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                reason="no_active_target",
            )
            return
        state = self._geometry.state
        if state.active_placement is not None:
            self._diagnostics.log_event(
                "preview_state.caught_up",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                active_target_kind=reorder_drag_target_kind(
                    self._gesture.state.active_drop_target
                ),
                has_expected_landing=(
                    state.active_placement.expected_landing_chip_index is not None
                ),
            )

    def _record_committed_drop_actual(self) -> None:
        """Publish one deferred actual-drop observation after preview adoption."""

        segment_index = self._drop_diagnostics.state.segment_index
        if segment_index is None:
            return
        region = self._pointer_regions.regions_by_index.get(segment_index)
        self._drop_diagnostics.log_actual(
            PromptReorderDropActualObservation.from_publications(
                checkpoint="set_preview_snapshot.after_surface_sync",
                segment_index=segment_index,
                live_visuals=self._live_visuals.visuals_by_index,
                preview_visuals=self._preview_visuals.visuals_by_index,
                live_chip_geometry=self._live_visuals.chip_geometry,
                chip_rect=None if region is None else QRectF(region.rect),
                preview_mode_active=self._visual_mode.preview_active(),
                geometry=self._geometry.state,
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
            )
        )
        self._drop_diagnostics.clear()
