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

"""Own presentation-only activation of one reorder overlay visual session."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptReorderChipView,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import reorder_drag_started_at
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from .reorder_animation_presentation import PromptReorderAnimationPresentationOwner
from .reorder_autoscroll import PromptReorderAutoscrollOwner
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_drop_commit_diagnostics import PromptReorderDropCommitDiagnostics
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_held_drag_context import PromptReorderHeldDragContextOwner
from .reorder_interaction_diagnostics import PromptReorderInteractionDiagnosticsOwner
from .reorder_landing_paint import PromptReorderLandingPaintOwner
from .reorder_landing_session import PromptReorderLandingSessionOwner
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_overlay_visual_lifecycle import PromptReorderOverlayVisualLifecycleOwner
from .reorder_pointer_region_visual_owner import PromptReorderPointerRegionVisualOwner
from .reorder_pointer_regions import (
    PromptReorderPointerInput,
    PromptReorderPointerRegions,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_raster_publication import PromptReorderRasterPublicationOwner
from .reorder_refresh_identity import PromptReorderRefreshIdentityOwner
from .reorder_viewport_frame_refresh import PromptReorderViewportFrameRefreshOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner


class PromptReorderOverlaySessionActivationOwner:
    """Activate one display session without owning application reorder truth."""

    def __init__(
        self,
        *,
        interaction_metrics: PromptReorderInteractionMetricsOwner,
        animation: PromptReorderAnimationPresentationOwner,
        visual_lifecycle: PromptReorderOverlayVisualLifecycleOwner,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        autoscroll: PromptReorderAutoscrollOwner,
        pointer_input: PromptReorderPointerInput,
        pointer_regions: PromptReorderPointerRegions,
        preview_visuals: PromptReorderPreviewVisualOwner,
        landing_session: PromptReorderLandingSessionOwner,
        landing_preview: PromptReorderLandingPaintOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        raster: PromptReorderRasterPublicationOwner,
        held_drag_context: PromptReorderHeldDragContextOwner,
        drop_diagnostics: PromptReorderDropCommitDiagnostics,
        visual_session: PromptReorderVisualSessionOwner,
        geometry: PromptReorderInteractionGeometry,
        refresh_identity: PromptReorderRefreshIdentityOwner,
        gesture: PromptReorderGestureController,
        pointer_region_visuals: PromptReorderPointerRegionVisualOwner,
        viewport_refresh: PromptReorderViewportFrameRefreshOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        lower_view: Callable[[], None],
    ) -> None:
        """Store every presentation authority reset by one activation transaction."""

        self._interaction_metrics = interaction_metrics
        self._animation = animation
        self._visual_lifecycle = visual_lifecycle
        self._drag_proxy = drag_proxy
        self._autoscroll = autoscroll
        self._pointer_input = pointer_input
        self._pointer_regions = pointer_regions
        self._preview_visuals = preview_visuals
        self._landing_session = landing_session
        self._landing_preview = landing_preview
        self._live_visuals = live_visuals
        self._raster = raster
        self._held_drag_context = held_drag_context
        self._drop_diagnostics = drop_diagnostics
        self._visual_session = visual_session
        self._geometry = geometry
        self._refresh_identity = refresh_identity
        self._gesture = gesture
        self._pointer_region_visuals = pointer_region_visuals
        self._viewport_refresh = viewport_refresh
        self._diagnostics = diagnostics
        self._lower_view = lower_view

    def activate(
        self,
        document_view: PromptDocumentView,
        reorder_layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        chips: tuple[PromptReorderChipView, ...],
        active_chip_index: int | None,
        source_identity: PromptSourceIdentity | None,
    ) -> None:
        """Replace all transient presentation state from one immutable session view."""

        started_at = reorder_drag_started_at()
        self._interaction_metrics.begin_session()
        self._animation.cancel(reason="set_chips")
        self._visual_lifecycle.clear_snapshots(reason="set_chips")
        self._drag_proxy.hide()
        self._autoscroll.stop()
        self._autoscroll.clear_pending_invalidation()
        self._dispose_stale_regions()
        visual_session = self._visual_session.set_session(
            chips=chips,
            source_identity=source_identity,
        )
        self._geometry.set_session(
            document_view,
            reorder_layout_view,
            reorder_state,
            ordered_indices=tuple(segment.index for segment in chips),
        )
        self._refresh_identity.begin_session(document_view.source_text)
        self._geometry.clear_preview_target_identity()
        self._live_visuals.invalidate()
        self._gesture.reset_all()
        if (
            active_chip_index is not None
            and active_chip_index in visual_session.segments_by_index
        ):
            self._gesture.activate_segment(active_chip_index)
        self._landing_session.reset_session_state()
        self._landing_preview.reset_drag_state()
        self._pointer_region_visuals.invalidate_geometry()
        self._pointer_regions.set_segments(chips)
        self._pointer_input.reset()
        self._lower_view()
        self._viewport_refresh.refresh(reason="set_chips")
        self._diagnostics.log_timing(
            "overlay.set_chips",
            started_at=started_at,
            segment_count=len(chips),
            row_count=len(reorder_layout_view.rows),
            gap_count=len(reorder_layout_view.gaps),
            active_chip_index=active_chip_index,
        )

    def _dispose_stale_regions(self) -> None:
        """Release every presentation resource tied to a superseded chip session."""

        self._animation.cancel(reason="delete_existing_chips")
        self._pointer_input.reset()
        self._pointer_regions.clear()
        self._animation.clear_pointer_region_state()
        self._preview_visuals.clear()
        self._landing_session.clear_held_shadow()
        self._landing_preview.clear_held_shadow()
        self._live_visuals.clear()
        self._raster.invalidate_entries()
        self._held_drag_context.clear()
        self._drop_diagnostics.clear()


__all__ = ["PromptReorderOverlaySessionActivationOwner"]
