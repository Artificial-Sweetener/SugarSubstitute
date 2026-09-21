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

"""Compose the collaborator graph behind one mounted reorder overlay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtWidgets import QWidget

from ..geometry.widget_mapping import autocomplete_panel_host
from ..overlays.reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from ..overlays.reorder_autoscroll import PromptReorderAutoscrollOwner
from ..overlays.reorder_drag_proxy import PromptReorderDragProxyWidget
from ..overlays.reorder_drag_proxy_visual_owner import (
    PromptReorderDragProxyVisualOwner,
)
from ..overlays.reorder_drop_commit_diagnostics import (
    PromptReorderDropCommitDiagnostics,
)
from ..overlays.reorder_gesture_controller import (
    PromptReorderDragProxyPlacementController,
)
from ..overlays.reorder_held_drag_context import PromptReorderHeldDragContextOwner
from ..overlays.reorder_insertion_marker_owner import PromptReorderInsertionMarkerOwner
from ..overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from ..overlays.reorder_interaction_intents import PromptReorderInteractionIntentOwner
from ..overlays.reorder_keyboard_interaction import (
    PromptReorderKeyboardInteractionOwner,
)
from ..overlays.reorder_landing_diagnostics import PromptReorderLandingDiagnostics
from ..overlays.reorder_landing_events import PromptReorderLandingEventPublisher
from ..overlays.reorder_landing_paint import PromptReorderLandingPaintOwner
from ..overlays.reorder_landing_request_owner import PromptReorderLandingRequestOwner
from ..overlays.reorder_landing_resolution import PromptReorderLandingResolutionOwner
from ..overlays.reorder_landing_session import PromptReorderLandingSessionOwner
from ..overlays.reorder_landing_state import PromptReorderLandingStateOwner
from ..overlays.reorder_live_visual_owner import PromptReorderLiveVisualOwner
from ..overlays.reorder_overlay_runtime import (
    PromptReorderOverlayRuntime,
    PromptReorderOverlayRuntimeMount,
)
from ..overlays.reorder_overlay_session_activation import (
    PromptReorderOverlaySessionActivationOwner,
)
from ..overlays.reorder_overlay_visual_lifecycle import (
    PromptReorderOverlayVisualLifecycleOwner,
)
from ..overlays.reorder_performance_counters import (
    PromptReorderPerformanceCountersOwner,
)
from ..overlays.reorder_pointer_drag_completion_owner import (
    PromptReorderPointerDragCompletionOwner,
)
from ..overlays.reorder_pointer_drag_start_owner import (
    PromptReorderPointerDragStartOwner,
)
from ..overlays.reorder_pointer_move_owner import PromptReorderPointerMoveOwner
from ..overlays.reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from ..overlays.reorder_pointer_regions import (
    PromptReorderPointerInput,
    PromptReorderPointerRegions,
)
from ..overlays.reorder_pointer_target_resolution import (
    PromptReorderPointerTargetResolutionOwner,
)
from ..overlays.reorder_pointer_target_transition import (
    PromptReorderPointerTargetTransitionOwner,
)
from ..overlays.reorder_preview_build_facts import PromptReorderPreviewBuildFactsOwner
from ..overlays.reorder_preview_frame_transition import (
    PromptReorderPreviewFrameTransitionOwner,
)
from ..overlays.reorder_preview_geometry_refresh_owner import (
    PromptReorderPreviewGeometryRefreshOwner,
)
from ..overlays.reorder_preview_layout_transition_owner import (
    PromptReorderPreviewLayoutTransitionOwner,
)
from ..overlays.reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from ..overlays.reorder_preview_sync_context import (
    PromptReorderPreviewSyncContextOwner,
    PromptReorderPreviewSyncIdentifiers,
)
from ..overlays.reorder_raster_publication import PromptReorderRasterPublicationOwner
from ..overlays.reorder_refresh_identity import PromptReorderRefreshIdentityOwner
from ..overlays.reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from ..overlays.reorder_telemetry import PromptReorderTelemetry
from ..overlays.reorder_viewport_frame_refresh import (
    PromptReorderViewportFrameRefreshOwner,
)
from ..overlays.reorder_viewport_geometry import PromptReorderViewportGeometryOwner
from ..overlays.reorder_visual_lifetime import PromptReorderVisualLifetime
from ..overlays.reorder_visual_mode import PromptReorderVisualModeOwner
from ..overlays.reorder_visual_session import PromptReorderVisualSessionOwner
from ..overlays.reorder_visual_style import PromptReorderVisualStyle
from ..reorder_drag_proxy_state import PromptReorderDragProxyRenderStateBuilder


@dataclass(frozen=True, slots=True)
class PromptReorderOverlayRuntimeComposer:
    """Build the complete runtime graph behind one reorder overlay surface."""

    drag_proxy_placement: PromptReorderDragProxyPlacementController
    drag_proxy: PromptReorderDragProxyWidget
    drag_proxy_state_builder: PromptReorderDragProxyRenderStateBuilder

    def __call__(
        self,
        mount: PromptReorderOverlayRuntimeMount,
    ) -> PromptReorderOverlayRuntime:
        """Compose all runtime owners against one initialized Qt mount."""

        surface = mount.surface
        editor = mount.editor
        geometry = mount.geometry
        preview_visuals = mount.preview_visuals
        interaction_metrics = mount.interaction_metrics
        gesture = mount.gesture
        viewport_geometry = PromptReorderViewportGeometryOwner(editor)
        refresh_identity = PromptReorderRefreshIdentityOwner()
        preview_paint_snapshots = PromptReorderPreviewPaintSnapshotOwner(
            build_projection_snapshots=(
                editor.reorder_preview_chip_projection_paint_snapshots
            ),
            geometry_state=lambda: geometry.state,
            preview_visuals=lambda: preview_visuals.visuals_by_index,
        )
        telemetry = PromptReorderTelemetry()
        diagnostics = PromptReorderInteractionDiagnosticsOwner(
            telemetry=telemetry,
            metrics=interaction_metrics,
        )
        live_visuals = PromptReorderLiveVisualOwner(
            geometry=geometry,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
        )
        drop_diagnostics = PromptReorderDropCommitDiagnostics(
            telemetry=telemetry,
            diagnostics=diagnostics,
        )
        interaction_intents = PromptReorderInteractionIntentOwner()
        landing_state = PromptReorderLandingStateOwner()
        landing_diagnostics = PromptReorderLandingDiagnostics(
            telemetry=telemetry,
            log_event=diagnostics.log_event,
        )
        landing_events = PromptReorderLandingEventPublisher(
            telemetry=telemetry,
            log_event=diagnostics.log_event,
            log_timing=diagnostics.log_timing,
        )
        landing_session = PromptReorderLandingSessionOwner(
            state=landing_state,
            diagnostics=landing_diagnostics,
            events=landing_events,
        )
        landing_resolution = PromptReorderLandingResolutionOwner(
            telemetry=telemetry,
            state=landing_state,
            diagnostics=landing_diagnostics,
            events=landing_events,
        )
        landing_paint = PromptReorderLandingPaintOwner(
            telemetry=telemetry,
            resolution=landing_resolution,
            state=landing_state,
            diagnostics=landing_diagnostics,
            events=landing_events,
        )
        animation = PromptReorderAnimationPresentationOwner(
            parent=surface,
            frame_callback=mount.handle_animation_frame,
        )
        raster = PromptReorderRasterPublicationOwner(
            parent=surface,
            entries_changed=mount.publish_warmed_rasters,
        )
        visual_session = PromptReorderVisualSessionOwner()
        pointer_regions = PromptReorderPointerRegions()
        pointer_input = PromptReorderPointerInput(
            regions=pointer_regions,
            gesture_controller=mount.pointer_gesture_controller,
            surface=mount.pointer_surface,
            log_event=diagnostics.log_event,
        )
        visual_mode = PromptReorderVisualModeOwner(
            geometry_state=lambda: geometry.state,
            gesture=gesture,
        )
        landing_request = PromptReorderLandingRequestOwner(
            geometry=geometry,
            gesture=gesture,
            metrics=interaction_metrics,
            preview_visuals=preview_visuals,
            viewport=viewport_geometry,
            visual_mode=visual_mode,
            visual_session=visual_session,
        )
        preview_sync_context = PromptReorderPreviewSyncContextOwner(
            geometry_state=lambda: geometry.state,
            set_active_placement=geometry.set_active_placement,
            dragged_segment_index=lambda: gesture.state.dragged_segment_index,
            identifiers=lambda: PromptReorderPreviewSyncIdentifiers(
                gesture_id=interaction_metrics.gesture_id,
                event_id=interaction_metrics.event_id,
                pointer_active=interaction_metrics.pointer_loop_active,
            ),
            build_landing_request=landing_request.build,
            initial_shadow_sync=landing_resolution.initial_shadow_sync,
        )
        insertion_marker = PromptReorderInsertionMarkerOwner(
            geometry=geometry,
            gesture=gesture,
            landing_preview=landing_resolution,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
            telemetry=telemetry,
        )
        visual_style = PromptReorderVisualStyle.from_current_theme()
        render = PromptReorderRenderPublicationOwner(
            geometry=geometry,
            gesture=gesture,
            visual_mode=visual_mode,
            landing_request=landing_request,
            landing_preview=landing_paint,
            live_visuals=live_visuals,
            preview_visuals=preview_visuals,
            preview_paint_snapshots=preview_paint_snapshots,
            animation=animation,
            raster=raster,
            insertion_marker=insertion_marker,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
            visual_style=visual_style,
            device_pixel_ratio=mount.view.devicePixelRatioF,
            publish_surface=editor.set_reorder_surface_visual_publication,
            publish_overlay=mount.view.set_render_state,
        )
        preview_geometry = PromptReorderPreviewGeometryRefreshOwner(
            geometry=geometry,
            gesture=gesture,
            viewport=viewport_geometry,
            preview_visuals=preview_visuals,
            preview_paint_snapshots=preview_paint_snapshots,
            landing_request=landing_request,
            landing_preview=landing_resolution,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
        )
        pointer_target_resolution = PromptReorderPointerTargetResolutionOwner(
            geometry=geometry,
            gesture=gesture,
            metrics=interaction_metrics,
            telemetry=telemetry,
            diagnostics=diagnostics,
        )
        keyboard = PromptReorderKeyboardInteractionOwner(
            geometry=geometry,
            gesture=gesture,
            animation=animation,
        )
        preview_build_facts = PromptReorderPreviewBuildFactsOwner(
            geometry_state=lambda: geometry.state,
            gesture_facts=gesture.preview_build_facts,
            keyboard_drop_target=keyboard.committable_drop_target,
        )
        drag_proxy = PromptReorderDragProxyVisualOwner(
            editor_viewport=editor.viewport(),
            host=autocomplete_panel_host(cast(QWidget, editor)),
            proxy=self.drag_proxy,
            render_state_builder=self.drag_proxy_state_builder,
            placement=self.drag_proxy_placement,
            log_timing=diagnostics.log_timing,
        )
        preview_layout = PromptReorderPreviewLayoutTransitionOwner(
            geometry=geometry,
            gesture=gesture,
            viewport=viewport_geometry,
            drag_proxy=drag_proxy,
            metrics=interaction_metrics,
        )
        held_context = PromptReorderHeldDragContextOwner(
            gesture=gesture,
            geometry_state=lambda: geometry.state,
            clear_geometry=lambda preserve_preview: geometry.clear_drag_context(
                preserve_preview=preserve_preview
            ),
            live_visual_facts=lambda: (
                live_visuals.visuals_by_index,
                live_visuals.chip_geometry,
            ),
            regions_by_index=lambda: pointer_regions.regions_by_index,
            proxy_sizes=lambda: (drag_proxy.size, drag_proxy.size_hint),
            capture_held_shadow=landing_session.capture_held_shadow,
            clear_held_shadow=landing_session.clear_held_shadow,
            clear_landing_paint=landing_paint.clear_held_shadow,
        )
        target_transition = PromptReorderPointerTargetTransitionOwner(
            resolver=pointer_target_resolution,
            geometry=geometry,
            gesture=gesture,
            animation=animation,
            live_visuals=live_visuals,
            preview_visuals=preview_visuals,
            regions=pointer_regions,
            drag_proxy=drag_proxy,
            landing=landing_session,
            viewport=viewport_geometry,
            visual_mode=visual_mode,
            preview_layout_changed=mount.emit_preview_layout_changed,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
            telemetry=telemetry,
        )
        pointer_region_visuals = PromptReorderPointerRegionVisualOwner(
            regions=pointer_regions,
            gesture=gesture,
            visual_mode=visual_mode,
            live_visuals=lambda: live_visuals.visuals_by_index,
            preview_visuals=lambda: preview_visuals.visuals_by_index,
            raise_drag_proxy=drag_proxy.raise_proxy,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
            visual_style=visual_style,
        )
        preview_frame = PromptReorderPreviewFrameTransitionOwner(
            geometry=geometry,
            gesture=gesture,
            visual_mode=visual_mode,
            visual_session=visual_session,
            viewport=viewport_geometry,
            refresh_identity=refresh_identity,
            live_visuals=live_visuals,
            preview_visuals=preview_visuals,
            preview_geometry=preview_geometry,
            preview_paint_snapshots=preview_paint_snapshots,
            pointer_region_visuals=pointer_region_visuals,
            pointer_regions=pointer_regions,
            animation=animation,
            render=render,
            drop_diagnostics=drop_diagnostics,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
        )
        viewport_refresh = PromptReorderViewportFrameRefreshOwner(
            geometry=geometry,
            gesture=gesture,
            visual_session=visual_session,
            viewport=viewport_geometry,
            refresh_identity=refresh_identity,
            live_visuals=live_visuals,
            preview_visuals=preview_visuals,
            preview_geometry=preview_geometry,
            preview_layout=preview_layout,
            pointer_region_visuals=pointer_region_visuals,
            drag_proxy=drag_proxy,
            animation=animation,
            render=render,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
            overlay_geometry=surface.geometry,
            set_overlay_geometry=surface.setGeometry,
        )
        autoscroll = PromptReorderAutoscrollOwner(
            parent=surface,
            scrollbar_provider=editor.verticalScrollBar,
            overlay_height_provider=surface.height,
            map_global_to_overlay=surface.mapFromGlobal,
            refresh_geometry=lambda reason: mount.refresh_geometry(reason),
            settle_animation=lambda reason: animation.settle(reason=reason),
            invalidate_refresh=refresh_identity.invalidate_refresh,
            gesture=gesture,
            update_target=lambda local_pointer, emit_preview_changed: (
                target_transition.update(
                    local_pointer,
                    emit_preview_changed=emit_preview_changed,
                )
            ),
            emit_preview_layout_changed=mount.emit_preview_layout_changed,
            metrics=interaction_metrics,
            diagnostics=diagnostics,
        )
        pointer_move = PromptReorderPointerMoveOwner(
            gesture=gesture,
            intents=interaction_intents,
            metrics=interaction_metrics,
            telemetry=telemetry,
            diagnostics=diagnostics,
            drag_proxy=drag_proxy,
            target_transition=target_transition,
            autoscroll=autoscroll,
            geometry=geometry,
            map_global_to_overlay=surface.mapFromGlobal,
        )
        performance = PromptReorderPerformanceCountersOwner(
            geometry=editor,
            interaction=interaction_metrics,
            drag_proxy=drag_proxy,
            autoscroll=autoscroll,
            animation=animation,
            raster=raster,
            landing_preview=landing_paint,
        )
        pointer_drag_start = PromptReorderPointerDragStartOwner(
            geometry=geometry,
            gesture=gesture,
            visual_mode=visual_mode,
            live_visuals=live_visuals,
            intents=interaction_intents,
            metrics=interaction_metrics,
            performance=performance,
            autoscroll=autoscroll,
            diagnostics=diagnostics,
            visual_session=visual_session,
            landing_preview=landing_paint,
            drop_diagnostics=drop_diagnostics,
            held_context=held_context,
            drag_proxy=drag_proxy,
            preview_layout=preview_layout,
            target_transition=target_transition,
            pointer_regions=pointer_region_visuals,
            render=render,
            animation=animation,
            map_global_to_overlay=surface.mapFromGlobal,
            preview_layout_changed=mount.emit_preview_layout_changed,
        )
        pointer_drag_completion = PromptReorderPointerDragCompletionOwner(
            geometry=geometry,
            gesture=gesture,
            visual_mode=visual_mode,
            live_visuals=live_visuals,
            preview_visuals=preview_visuals,
            intents=interaction_intents,
            metrics=interaction_metrics,
            autoscroll=autoscroll,
            animation=animation,
            landing_preview=landing_paint,
            drop_diagnostics=drop_diagnostics,
            held_context=held_context,
            drag_proxy=drag_proxy,
            preview_layout=preview_layout,
            pointer_regions=pointer_region_visuals,
            region_widgets=pointer_regions,
            render=render,
            diagnostics=diagnostics,
            performance=performance,
            visual_session=visual_session,
            preview_layout_changed=mount.emit_preview_layout_changed,
        )
        visual_lifecycle = PromptReorderOverlayVisualLifecycleOwner(
            visual_style=visual_style,
            animation=animation,
            preview_paint_snapshots=preview_paint_snapshots,
            preview_visuals=preview_visuals,
            raster=raster,
            live_visuals=live_visuals,
            refresh_identity=refresh_identity,
            render=render,
            pointer_regions=pointer_region_visuals,
            drag_proxy=drag_proxy,
            refresh_geometry=lambda reason: mount.refresh_geometry(reason),
        )
        visual_lifecycle.apply_current_theme_style()
        visual_lifetime = PromptReorderVisualLifetime(
            surface,
            visual_lifecycle,
            self.drag_proxy,
        )
        session_activation = PromptReorderOverlaySessionActivationOwner(
            interaction_metrics=interaction_metrics,
            animation=animation,
            visual_lifecycle=visual_lifecycle,
            drag_proxy=drag_proxy,
            autoscroll=autoscroll,
            pointer_input=pointer_input,
            pointer_regions=pointer_regions,
            preview_visuals=preview_visuals,
            landing_session=landing_session,
            landing_preview=landing_paint,
            live_visuals=live_visuals,
            raster=raster,
            held_drag_context=held_context,
            drop_diagnostics=drop_diagnostics,
            visual_session=visual_session,
            geometry=geometry,
            refresh_identity=refresh_identity,
            gesture=gesture,
            pointer_region_visuals=pointer_region_visuals,
            viewport_refresh=viewport_refresh,
            diagnostics=diagnostics,
            lower_view=mount.view.lower,
        )
        return PromptReorderOverlayRuntime(
            geometry=geometry,
            viewport_geometry=viewport_geometry,
            preview_visuals=preview_visuals,
            interaction_metrics=interaction_metrics,
            telemetry=telemetry,
            preview_paint_snapshots=preview_paint_snapshots,
            live_visuals=live_visuals,
            interaction_intents=interaction_intents,
            landing_request=landing_request,
            landing_resolution=landing_resolution,
            animation=animation,
            raster=raster,
            visual_session=visual_session,
            pointer_regions=pointer_regions,
            pointer_input=pointer_input,
            gesture=gesture,
            visual_mode=visual_mode,
            render=render,
            keyboard=keyboard,
            drag_proxy=drag_proxy,
            pointer_region_visuals=pointer_region_visuals,
            preview_frame=preview_frame,
            viewport_refresh=viewport_refresh,
            autoscroll=autoscroll,
            pointer_move=pointer_move,
            pointer_drag_start=pointer_drag_start,
            pointer_drag_completion=pointer_drag_completion,
            performance=performance,
            visual_lifecycle=visual_lifecycle,
            session_activation=session_activation,
            preview_sync_context=preview_sync_context,
            preview_build_facts=preview_build_facts,
            visual_lifetime=visual_lifetime,
        )


__all__ = ["PromptReorderOverlayRuntimeComposer"]
