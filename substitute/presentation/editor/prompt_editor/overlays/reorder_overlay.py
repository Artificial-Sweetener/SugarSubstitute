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

"""Render the prompt-segment reorder affordance over the text editor."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QEnterEvent,
    QMouseEvent,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptReorderChipView,
)
from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitSnapshot,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..geometry.widget_mapping import (
    autocomplete_panel_host,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from ..projection.reorder_interaction_geometry_identity import (
    reorder_geometry_generation_state,
    reorder_preview_target_state,
)
from ..projection.reorder_animation import PromptReorderAnimationPlan
from ..projection.reorder_state import PromptReorderAnimationGenerationState
from ..reorder_drag_proxy_state import PromptReorderDragProxyRenderStateBuilder
from ..projection.reorder_state import (
    PromptReorderGeometryGenerationState,
    PromptReorderKeyboardState,
    PromptReorderPointerState,
    PromptReorderPreviewTargetState,
)
from .reorder_drag_proxy import (
    PromptReorderDragProxyWidget,
)
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_drop_commit_diagnostics import PromptReorderDropCommitDiagnostics
from .reorder_gesture_controller import (
    PromptReorderDragIntent,
    PromptReorderDragProxyPlacementController,
    PromptReorderGestureController,
)
from .reorder_held_drag_context import (
    PromptReorderHeldDragContextOwner,
)
from .reorder_visual_style import PromptReorderVisualStyle
from .reorder_overlay_visual_lifecycle import (
    PromptReorderOverlayVisualLifecycleOwner,
)
from .reorder_theme_refresh import PromptReorderThemeRefreshRequest
from .reorder_overlay_session_activation import (
    PromptReorderOverlaySessionActivationOwner,
)
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner
from .reorder_telemetry import PromptReorderTelemetry
from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_keyboard_interaction import (
    PromptReorderKeyboardInteractionOwner,
    PromptReorderKeyboardVisualContext,
)
from .reorder_interaction_intents import PromptReorderInteractionIntentOwner
from .reorder_insertion_marker_owner import PromptReorderInsertionMarkerOwner
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_landing_diagnostics import PromptReorderLandingDiagnostics
from .reorder_landing_events import PromptReorderLandingEventPublisher
from .reorder_landing_paint import PromptReorderLandingPaintOwner
from .reorder_landing_request_owner import PromptReorderLandingRequestOwner
from .reorder_landing_resolution import PromptReorderLandingResolutionOwner
from .reorder_landing_session import PromptReorderLandingSessionOwner
from .reorder_landing_state import PromptReorderLandingStateOwner
from .reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from .reorder_autoscroll import PromptReorderAutoscrollOwner
from .reorder_pointer_regions import (
    PromptReorderPointerInput,
    PromptReorderPointerRegion,
    PromptReorderPointerRegions,
)
from .reorder_refresh_identity import PromptReorderRefreshIdentityOwner
from .reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from .reorder_pointer_move_owner import PromptReorderPointerMoveOwner
from .reorder_pointer_target_resolution import (
    PromptReorderPointerTargetResolutionOwner,
)
from .reorder_pointer_target_transition import (
    PromptReorderPointerTargetTransitionOwner,
)
from .reorder_performance_counters import PromptReorderPerformanceCountersOwner
from .reorder_overlay_ports import (
    PromptReorderEditor,
    PromptReorderViewFactory,
)
from .reorder_commit_snapshot import prompt_reorder_commit_snapshot
from .reorder_preview_frame_transition import (
    PromptReorderPreviewFrameTransitionOwner,
)
from .reorder_preview_build_facts import PromptReorderPreviewBuildFactsOwner
from .reorder_preview_sync_context import (
    PromptReorderPreviewSyncContextOwner,
    PromptReorderPreviewSyncIdentifiers,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from .reorder_preview_geometry_refresh_owner import (
    PromptReorderPreviewGeometryRefreshOwner,
)
from .reorder_preview_layout_transition_owner import (
    PromptReorderPreviewLayoutTransitionOwner,
)
from .reorder_raster_publication import PromptReorderRasterPublicationOwner
from .reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from .reorder_pointer_drag_start_owner import PromptReorderPointerDragStartOwner
from .reorder_pointer_drag_completion_owner import (
    PromptReorderPointerDragCompletionOwner,
)
from .reorder_viewport_frame_refresh import PromptReorderViewportFrameRefreshOwner


class SegmentReorderOverlay(QWidget):
    """Show prompt segment reorder affordances over the existing text surface."""

    previewLayoutChanged = Signal()

    def __init__(
        self,
        editor: QWidget,
        *,
        geometry: PromptReorderInteractionGeometry,
        preview_visual_owner: PromptReorderPreviewVisualOwner,
        interaction_metrics: PromptReorderInteractionMetricsOwner,
        view_factory: PromptReorderViewFactory,
        gesture_controller: PromptReorderGestureController,
        drag_proxy_placement: PromptReorderDragProxyPlacementController,
        drag_proxy: PromptReorderDragProxyWidget,
        drag_proxy_state_factory: PromptReorderDragProxyRenderStateBuilder,
    ) -> None:
        """Build one viewport-local reorder overlay for the supplied editor."""

        self._editor = cast(PromptReorderEditor, editor)
        super().__init__(self._editor.viewport())
        self._geometry = geometry
        self._viewport_geometry = PromptReorderViewportGeometryOwner(self._editor)
        self._refresh_identity = PromptReorderRefreshIdentityOwner()
        self._preview_visual_owner = preview_visual_owner
        self._preview_paint_snapshots = PromptReorderPreviewPaintSnapshotOwner(
            build_projection_snapshots=(
                self._editor.reorder_preview_chip_projection_paint_snapshots
            ),
            geometry_state=lambda: self._geometry.state,
            preview_visuals=lambda: self._preview_visual_owner.visuals_by_index,
        )
        self._telemetry = PromptReorderTelemetry()
        self._interaction_metrics = interaction_metrics
        self._interaction_diagnostics = PromptReorderInteractionDiagnosticsOwner(
            telemetry=self._telemetry,
            metrics=self._interaction_metrics,
        )
        self._live_visual_owner = PromptReorderLiveVisualOwner(
            geometry=self._geometry,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
        )
        self._drop_commit_diagnostics = PromptReorderDropCommitDiagnostics(
            telemetry=self._telemetry,
            diagnostics=self._interaction_diagnostics,
        )
        self._interaction_intents = PromptReorderInteractionIntentOwner()
        self._landing_state = PromptReorderLandingStateOwner()
        self._landing_diagnostics = PromptReorderLandingDiagnostics(
            telemetry=self._telemetry,
            log_event=self._interaction_diagnostics.log_event,
        )
        self._landing_events = PromptReorderLandingEventPublisher(
            telemetry=self._telemetry,
            log_event=self._interaction_diagnostics.log_event,
            log_timing=self._interaction_diagnostics.log_timing,
        )
        self._landing_session = PromptReorderLandingSessionOwner(
            state=self._landing_state,
            diagnostics=self._landing_diagnostics,
            events=self._landing_events,
        )
        self._landing_resolution = PromptReorderLandingResolutionOwner(
            telemetry=self._telemetry,
            state=self._landing_state,
            diagnostics=self._landing_diagnostics,
            events=self._landing_events,
        )
        self._landing_paint = PromptReorderLandingPaintOwner(
            telemetry=self._telemetry,
            resolution=self._landing_resolution,
            state=self._landing_state,
            diagnostics=self._landing_diagnostics,
            events=self._landing_events,
        )
        self._animation_presentation = PromptReorderAnimationPresentationOwner(
            parent=self,
            frame_callback=self._handle_reorder_animation_frame,
        )
        self._raster_publication_owner = PromptReorderRasterPublicationOwner(
            parent=self,
            entries_changed=self._publish_warmed_reorder_rasters,
        )
        self.setObjectName("segmentReorderOverlay")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._view = view_factory(self)
        self._view.setGeometry(self.rect())
        self._view.lower()
        self._view.show()
        initial_visual_style = PromptReorderVisualStyle.from_current_theme()
        self._visual_session = PromptReorderVisualSessionOwner()
        self._pointer_regions = PromptReorderPointerRegions()
        self._pointer_input = PromptReorderPointerInput(
            regions=self._pointer_regions,
            gesture_controller=self,
            surface=self,
            log_event=self._interaction_diagnostics.log_event,
        )
        self._chips_by_index = self._pointer_regions.regions_by_index
        self._gesture = gesture_controller
        self._visual_mode = PromptReorderVisualModeOwner(
            geometry_state=lambda: self._geometry.state,
            gesture=self._gesture,
        )
        self._landing_request = PromptReorderLandingRequestOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            metrics=self._interaction_metrics,
            preview_visuals=self._preview_visual_owner,
            viewport=self._viewport_geometry,
            visual_mode=self._visual_mode,
            visual_session=self._visual_session,
        )
        self.preview_sync_context = PromptReorderPreviewSyncContextOwner(
            geometry_state=lambda: self._geometry.state,
            set_active_placement=self._geometry.set_active_placement,
            dragged_segment_index=lambda: self._gesture.state.dragged_segment_index,
            identifiers=lambda: PromptReorderPreviewSyncIdentifiers(
                gesture_id=self._interaction_metrics.gesture_id,
                event_id=self._interaction_metrics.event_id,
                pointer_active=self._interaction_metrics.pointer_loop_active,
            ),
            build_landing_request=self._landing_request.build,
            initial_shadow_sync=self._landing_resolution.initial_shadow_sync,
        )
        self._insertion_marker = PromptReorderInsertionMarkerOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            landing_preview=self._landing_resolution,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
            telemetry=self._telemetry,
        )
        self._render_publication = PromptReorderRenderPublicationOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            visual_mode=self._visual_mode,
            landing_request=self._landing_request,
            landing_preview=self._landing_paint,
            live_visuals=self._live_visual_owner,
            preview_visuals=self._preview_visual_owner,
            preview_paint_snapshots=self._preview_paint_snapshots,
            animation=self._animation_presentation,
            raster=self._raster_publication_owner,
            insertion_marker=self._insertion_marker,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
            visual_style=initial_visual_style,
            device_pixel_ratio=self._view.devicePixelRatioF,
            publish_surface=self._editor.set_reorder_surface_visual_publication,
            publish_overlay=self._view.set_render_state,
        )
        self._preview_geometry_refresh = PromptReorderPreviewGeometryRefreshOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            viewport=self._viewport_geometry,
            preview_visuals=self._preview_visual_owner,
            preview_paint_snapshots=self._preview_paint_snapshots,
            landing_request=self._landing_request,
            landing_preview=self._landing_resolution,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
        )
        self._pointer_target_resolution = PromptReorderPointerTargetResolutionOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            metrics=self._interaction_metrics,
            telemetry=self._telemetry,
            diagnostics=self._interaction_diagnostics,
        )
        self._keyboard_interaction = PromptReorderKeyboardInteractionOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            animation=self._animation_presentation,
        )
        self.preview_build_facts = PromptReorderPreviewBuildFactsOwner(
            geometry_state=lambda: self._geometry.state,
            gesture_facts=self._gesture.preview_build_facts,
            keyboard_drop_target=self._keyboard_interaction.committable_drop_target,
        )
        self._drag_proxy_visual = PromptReorderDragProxyVisualOwner(
            editor_viewport=self._editor.viewport(),
            host=autocomplete_panel_host(cast(QWidget, self._editor)),
            proxy=drag_proxy,
            render_state_builder=drag_proxy_state_factory,
            placement=drag_proxy_placement,
            log_timing=self._interaction_diagnostics.log_timing,
        )
        self._preview_layout_transition = PromptReorderPreviewLayoutTransitionOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            viewport=self._viewport_geometry,
            drag_proxy=self._drag_proxy_visual,
            metrics=self._interaction_metrics,
        )
        self._held_drag_context = PromptReorderHeldDragContextOwner(
            gesture=self._gesture,
            geometry_state=lambda: self._geometry.state,
            clear_geometry=lambda preserve_preview: self._geometry.clear_drag_context(
                preserve_preview=preserve_preview
            ),
            live_visual_facts=lambda: (
                self._live_visual_owner.visuals_by_index,
                self._live_visual_owner.chip_geometry,
            ),
            regions_by_index=lambda: self._pointer_regions.regions_by_index,
            proxy_sizes=lambda: (
                self._drag_proxy_visual.size,
                self._drag_proxy_visual.size_hint,
            ),
            capture_held_shadow=self._landing_session.capture_held_shadow,
            clear_held_shadow=self._landing_session.clear_held_shadow,
            clear_landing_paint=self._landing_paint.clear_held_shadow,
        )
        self._pointer_target_transition = PromptReorderPointerTargetTransitionOwner(
            resolver=self._pointer_target_resolution,
            geometry=self._geometry,
            gesture=self._gesture,
            animation=self._animation_presentation,
            live_visuals=self._live_visual_owner,
            preview_visuals=self._preview_visual_owner,
            regions=self._pointer_regions,
            drag_proxy=self._drag_proxy_visual,
            landing=self._landing_session,
            viewport=self._viewport_geometry,
            visual_mode=self._visual_mode,
            preview_layout_changed=self.previewLayoutChanged.emit,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
            telemetry=self._telemetry,
        )
        self._pointer_region_visual = PromptReorderPointerRegionVisualOwner(
            regions=self._pointer_regions,
            gesture=self._gesture,
            visual_mode=self._visual_mode,
            live_visuals=lambda: self._live_visual_owner.visuals_by_index,
            preview_visuals=lambda: self._preview_visual_owner.visuals_by_index,
            raise_drag_proxy=self._drag_proxy_visual.raise_proxy,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
            visual_style=initial_visual_style,
        )
        self._preview_frame_transition = PromptReorderPreviewFrameTransitionOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            visual_mode=self._visual_mode,
            visual_session=self._visual_session,
            viewport=self._viewport_geometry,
            refresh_identity=self._refresh_identity,
            live_visuals=self._live_visual_owner,
            preview_visuals=self._preview_visual_owner,
            preview_geometry=self._preview_geometry_refresh,
            preview_paint_snapshots=self._preview_paint_snapshots,
            pointer_region_visuals=self._pointer_region_visual,
            pointer_regions=self._pointer_regions,
            animation=self._animation_presentation,
            render=self._render_publication,
            drop_diagnostics=self._drop_commit_diagnostics,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
        )
        self._viewport_frame_refresh = PromptReorderViewportFrameRefreshOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            visual_session=self._visual_session,
            viewport=self._viewport_geometry,
            refresh_identity=self._refresh_identity,
            live_visuals=self._live_visual_owner,
            preview_visuals=self._preview_visual_owner,
            preview_geometry=self._preview_geometry_refresh,
            preview_layout=self._preview_layout_transition,
            pointer_region_visuals=self._pointer_region_visual,
            drag_proxy=self._drag_proxy_visual,
            animation=self._animation_presentation,
            render=self._render_publication,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
            overlay_geometry=self.geometry,
            set_overlay_geometry=self.setGeometry,
        )
        self._autoscroll = PromptReorderAutoscrollOwner(
            parent=self,
            scrollbar_provider=self._editor.verticalScrollBar,
            overlay_height_provider=self.height,
            map_global_to_overlay=self.mapFromGlobal,
            refresh_geometry=lambda reason: self.request_geometry_refresh(
                reason=reason
            ),
            settle_animation=lambda reason: self._animation_presentation.settle(
                reason=reason
            ),
            invalidate_refresh=self._refresh_identity.invalidate_refresh,
            gesture=self._gesture,
            update_target=lambda local_pointer, emit_preview_changed: (
                self._pointer_target_transition.update(
                    local_pointer,
                    emit_preview_changed=emit_preview_changed,
                )
            ),
            emit_preview_layout_changed=self.emit_preview_layout_changed,
            metrics=self._interaction_metrics,
            diagnostics=self._interaction_diagnostics,
        )
        self._pointer_move = PromptReorderPointerMoveOwner(
            gesture=self._gesture,
            intents=self._interaction_intents,
            metrics=self._interaction_metrics,
            telemetry=self._telemetry,
            diagnostics=self._interaction_diagnostics,
            drag_proxy=self._drag_proxy_visual,
            target_transition=self._pointer_target_transition,
            autoscroll=self._autoscroll,
            geometry=self._geometry,
            map_global_to_overlay=self.mapFromGlobal,
        )
        self._performance_counters = PromptReorderPerformanceCountersOwner(
            geometry=self._editor,
            interaction=self._interaction_metrics,
            drag_proxy=self._drag_proxy_visual,
            autoscroll=self._autoscroll,
            animation=self._animation_presentation,
            raster=self._raster_publication_owner,
            landing_preview=self._landing_paint,
        )
        self._pointer_drag_start = PromptReorderPointerDragStartOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            visual_mode=self._visual_mode,
            live_visuals=self._live_visual_owner,
            intents=self._interaction_intents,
            metrics=self._interaction_metrics,
            performance=self._performance_counters,
            autoscroll=self._autoscroll,
            diagnostics=self._interaction_diagnostics,
            visual_session=self._visual_session,
            landing_preview=self._landing_paint,
            drop_diagnostics=self._drop_commit_diagnostics,
            held_context=self._held_drag_context,
            drag_proxy=self._drag_proxy_visual,
            preview_layout=self._preview_layout_transition,
            target_transition=self._pointer_target_transition,
            pointer_regions=self._pointer_region_visual,
            render=self._render_publication,
            animation=self._animation_presentation,
            map_global_to_overlay=self.mapFromGlobal,
            preview_layout_changed=self.previewLayoutChanged.emit,
        )
        self._pointer_drag_completion = PromptReorderPointerDragCompletionOwner(
            geometry=self._geometry,
            gesture=self._gesture,
            visual_mode=self._visual_mode,
            live_visuals=self._live_visual_owner,
            preview_visuals=self._preview_visual_owner,
            intents=self._interaction_intents,
            metrics=self._interaction_metrics,
            autoscroll=self._autoscroll,
            animation=self._animation_presentation,
            landing_preview=self._landing_paint,
            drop_diagnostics=self._drop_commit_diagnostics,
            held_context=self._held_drag_context,
            drag_proxy=self._drag_proxy_visual,
            preview_layout=self._preview_layout_transition,
            pointer_regions=self._pointer_region_visual,
            region_widgets=self._pointer_regions,
            render=self._render_publication,
            diagnostics=self._interaction_diagnostics,
            performance=self._performance_counters,
            visual_session=self._visual_session,
            preview_layout_changed=self.previewLayoutChanged.emit,
        )
        self._visual_lifecycle = PromptReorderOverlayVisualLifecycleOwner(
            visual_style=initial_visual_style,
            animation=self._animation_presentation,
            preview_paint_snapshots=self._preview_paint_snapshots,
            preview_visuals=self._preview_visual_owner,
            raster=self._raster_publication_owner,
            live_visuals=self._live_visual_owner,
            refresh_identity=self._refresh_identity,
            render=self._render_publication,
            pointer_regions=self._pointer_region_visual,
            drag_proxy=self._drag_proxy_visual,
            refresh_geometry=lambda reason: self.refresh_geometry(reason=reason),
        )
        self._visual_lifecycle.apply_current_theme_style()
        self._session_activation = PromptReorderOverlaySessionActivationOwner(
            interaction_metrics=self._interaction_metrics,
            animation=self._animation_presentation,
            visual_lifecycle=self._visual_lifecycle,
            drag_proxy=self._drag_proxy_visual,
            autoscroll=self._autoscroll,
            pointer_input=self._pointer_input,
            pointer_regions=self._pointer_regions,
            preview_visuals=self._preview_visual_owner,
            landing_session=self._landing_session,
            landing_preview=self._landing_paint,
            live_visuals=self._live_visual_owner,
            raster=self._raster_publication_owner,
            held_drag_context=self._held_drag_context,
            drop_diagnostics=self._drop_commit_diagnostics,
            visual_session=self._visual_session,
            geometry=self._geometry,
            refresh_identity=self._refresh_identity,
            gesture=self._gesture,
            pointer_region_visuals=self._pointer_region_visual,
            viewport_refresh=self._viewport_frame_refresh,
            diagnostics=self._interaction_diagnostics,
            lower_view=self._view.lower,
        )

    def changeEvent(self, event: QEvent) -> None:
        """Refresh overlay colors after palette or theme changes."""

        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.FontChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.StyleChange,
        ):
            dragged_segment_index = self._gesture.state.dragged_segment_index
            self._visual_lifecycle.refresh_theme(
                PromptReorderThemeRefreshRequest(
                    has_document=self._geometry.state.document_view is not None,
                    dragged_segment=(
                        None
                        if dragged_segment_index is None
                        else self._visual_session.segments_by_index[
                            dragged_segment_index
                        ]
                    ),
                    source_revision=self._visual_session.source_revision,
                    gesture=self._gesture.state,
                    gesture_id=self._interaction_metrics.gesture_id,
                    event_id=self._interaction_metrics.event_id,
                )
            )
        super().changeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep drag proxy placement synchronized when the overlay resizes."""

        super().resizeEvent(event)
        view = getattr(self, "_view", None)
        render = getattr(self, "_render_publication", None)
        if view is None or render is None:
            return
        view.setGeometry(self.rect())
        render.sync(reason="overlay_resize")
        if self._gesture.state.last_drag_global_position is not None:
            self._drag_proxy_visual.move(
                self._gesture.state.last_drag_global_position,
                gesture_id=self._interaction_metrics.gesture_id,
                event_id=self._interaction_metrics.event_id,
            )

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh chip geometry after the overlay becomes visible to Qt."""

        super().showEvent(event)
        if self._geometry.state.document_view is None:
            self._viewport_frame_refresh.sync_overlay_rect()
            self._view.setGeometry(self.rect())
            return
        self.refresh_geometry(reason="overlay_show")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Dispose the floating drag proxy when the overlay itself closes."""

        self._visual_lifecycle.close()
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Route a press through overlay-owned semantic chip hit testing."""

        self._pointer_input.press(
            event,
            ordered_indices=self._geometry.state.ordered_segment_indices,
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Route hover and drag motion through one bounded input surface."""

        self._pointer_input.move(
            event,
            ordered_indices=self._geometry.state.ordered_segment_indices,
        )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Release the semantic chip gesture owned by the overlay surface."""

        self._pointer_input.release(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Refresh hover immediately when the pointer enters reorder mode."""

        region = self._pointer_regions.hit_test(
            event.position(),
            ordered_indices=self._geometry.state.ordered_segment_indices,
        )
        self.set_hovered_segment(None if region is None else region.segment_index)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover when no pressed gesture retains overlay ownership."""

        self._pointer_input.leave()
        super().leaveEvent(event)

    def set_chips(
        self,
        document_view: PromptDocumentView,
        reorder_layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        chips: tuple[PromptReorderChipView, ...],
        active_chip_index: int | None = None,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Populate overlay hotspots from the current reorder-chip snapshot."""

        self._session_activation.activate(
            document_view,
            reorder_layout_view,
            reorder_state,
            chips=chips,
            active_chip_index=active_chip_index,
            source_identity=source_identity,
        )

    def animation_generation_state(self) -> PromptReorderAnimationGenerationState:
        """Return authoritative animation generation state for diagnostics."""

        return self._animation_presentation.generation_state(
            geometry_generation_id=self._interaction_metrics.work_unit_id,
            active_target=self._gesture.state.active_drop_target,
        )

    def apply_animation_plan(self, plan: PromptReorderAnimationPlan) -> None:
        """Publish one projection-owned animation plan."""

        self._animation_presentation.apply_plan(
            plan,
            preview_geometry=self._geometry.state.preview_chip_geometry_snapshot,
        )

    def _handle_reorder_animation_frame(self) -> None:
        """Adapt one prepared animation frame to pointer and paint surfaces."""

        self._animation_presentation.sync_pointer_regions(
            regions_by_index=self._chips_by_index,
            preview_active=self._visual_mode.preview_active(),
            live_visuals_by_index=self._live_visual_owner.visuals_by_index,
            preview_visuals_by_index=self._preview_visual_owner.visuals_by_index,
        )
        self._render_publication.sync(reason="animation_frame")

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for drag intent publication."""

        self._interaction_intents.set_drag_handler(handler)

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for commit intent publication."""

        self._interaction_intents.set_commit_handler(handler)

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for cancel intent publication."""

        self._interaction_intents.set_cancel_handler(handler)

    def request_geometry_refresh(self, *, reason: str) -> None:
        """Request a bounded geometry refresh for the current overlay state."""

        self.refresh_geometry(reason=reason)

    def flush_pending_autoscroll_invalidation(self, *, reason: str) -> bool:
        """Expose the autoscroll owner's coalesced host-boundary flush."""

        return self._autoscroll.flush_pending_invalidation(reason=reason)

    def drag_move(self, segment_index: int, global_pos: QPoint) -> None:
        """Route one pointer move into the focused reorder transition owner."""

        self._pointer_move.move(segment_index, global_pos)

    def start_drag(
        self,
        segment_index: int,
        *,
        global_pos: QPoint,
        press_global_pos: QPoint,
    ) -> None:
        """Route one threshold crossing into the focused drag-start owner."""

        self._pointer_drag_start.start(
            segment_index,
            global_position=global_pos,
            press_global_position=press_global_pos,
        )

    def end_drag(self, segment_index: int) -> None:
        """Route one pointer release into the focused completion owner."""

        self._pointer_drag_completion.end(segment_index)

    def cancel_drag(self) -> None:
        """Route one cancellation into the focused completion owner."""

        self._pointer_drag_completion.cancel()

    def prepare_drag(self, segment_index: int) -> None:
        """Prepare immutable held-chip presentation before threshold crossing."""

        self._pointer_drag_start.prepare(segment_index)

    def move_active_chip(self, intent: PromptReorderKeyboardMoveIntent) -> bool:
        """Route one keyboard intent and publish its adapter-level visual events."""

        result = self._keyboard_interaction.move(
            direction=intent.direction,
            gesture_id=self._interaction_metrics.gesture_id,
            event_id=self._interaction_metrics.event_id,
            visuals=PromptReorderKeyboardVisualContext(
                segment_indices=tuple(self._chips_by_index),
                preview_active=self._visual_mode.preview_active(),
                live_visuals_by_index=self._live_visual_owner.visuals_by_index,
                preview_visuals_by_index=(self._preview_visual_owner.visuals_by_index),
            ),
        )
        if result.context_prepared:
            self.emit_preview_layout_changed()
        if not result.moved:
            return False
        self._pointer_region_visual.sync_interaction_state()
        self.emit_preview_layout_changed()
        return True

    def reorder_performance_counters(self) -> dict[str, object]:
        """Return deterministic reorder owner counters for diagnostics."""

        return self._performance_counters.snapshot()

    def show_overlay(self) -> None:
        """Show the overlay without changing prompt source."""

        self.show()

    def hide_overlay(self) -> None:
        """Hide the overlay without changing prompt source."""

        self._visual_lifecycle.hide()
        self.hide()

    def _publish_warmed_reorder_rasters(self) -> None:
        """Publish one idle-built raster batch through the passive view owner."""

        self._visual_lifecycle.publish_warmed_rasters(overlay_visible=self.isVisible())

    def set_preview_snapshot(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None = None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Route one preview projection into the frame-transition owner."""

        self._preview_frame_transition.apply(
            snapshot,
            base_drag_snapshot=base_drag_snapshot,
            ordered_chip_indices=ordered_chip_indices,
        )

    def refresh_geometry(self, *, reason: str = "unspecified") -> None:
        """Route one explicit invalidation into the frame-transition owner."""

        self._viewport_frame_refresh.refresh(reason=reason)

    def needs_position_refresh(
        self,
        *,
        reason: str = "unspecified",
    ) -> bool:
        """Return whether viewport positioning changed since publication."""

        return self._viewport_frame_refresh.needs_position_refresh(reason=reason)

    def ordered_chip_indices(self) -> list[int]:
        """Return the current flattened chip order tracked by this reorder session."""

        return list(self._geometry.state.ordered_segment_indices)

    def retain_editor_focus(self) -> None:
        """Keep the host editor visually and keyboard-focused during reorder input."""

        self._editor.setFocus()

    def active_segment_index(self) -> int | None:
        """Return the segment that should remain selected after commit."""

        return self._gesture.state.active_segment_index

    def current_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the current in-session reorder layout represented by the overlay."""

        return self._geometry.state.current_layout_view

    def commit_snapshot(self) -> PromptReorderCommitSnapshot:
        """Return the prepared reorder state visible to interaction owners."""

        state = self._geometry.state
        gesture_state = self._gesture.state
        return prompt_reorder_commit_snapshot(
            state,
            active_segment_index=gesture_state.active_segment_index,
            dragged_segment_index=gesture_state.dragged_segment_index,
            has_reordered=self.has_reordered(),
        )

    def pointer_reorder_state(self) -> PromptReorderPointerState:
        """Return read-only pointer state without exposing QWidget ownership."""

        return self._gesture.pointer_state()

    def keyboard_reorder_state(self) -> PromptReorderKeyboardState:
        """Return read-only keyboard state without exposing QWidget ownership."""

        return self._gesture.keyboard_state()

    def preview_target_state(self) -> PromptReorderPreviewTargetState:
        """Return display-only preview target state for focused tests."""

        return reorder_preview_target_state(
            self._geometry.state,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
        )

    def geometry_generation_state(self) -> PromptReorderGeometryGenerationState:
        """Return prepared geometry generation state without QWidget references."""

        return reorder_geometry_generation_state(
            self._geometry.state,
            generation_id=self._interaction_metrics.work_unit_id,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
            viewport_identity=self._viewport_geometry.position_geometry_key(),
        )

    def preview_chip_indices(self) -> list[int]:
        """Return previewed chip indices in the current visible reorder order."""

        if not self._visual_mode.preview_active():
            return []
        return [
            segment_index
            for segment_index in self.ordered_chip_indices()
            if segment_index in self._preview_visual_owner.visuals_by_index
        ]

    def preview_rect_for_segment(self, segment_index: int) -> QRect | None:
        """Return one preview rect when the supplied segment is visibly previewed."""

        preview_visual = self._preview_visual_owner.visuals_by_index.get(segment_index)
        if preview_visual is None:
            return None
        return QRect(preview_visual.hotspot_rect)

    def has_valid_initial_landing_shadow(self) -> bool:
        """Return whether the active drag has a chip-shaped landing shadow."""

        result = self._landing_resolution.has_valid_initial_landing_shadow(
            self._landing_request.build()
        )
        self._geometry.set_active_placement(result.active_placement)
        return result.geometry is not None

    def drag_proxy_widget(self) -> QWidget:
        """Return the floating drag proxy widget used for segment dragging."""

        return self._drag_proxy_visual.widget

    def has_reordered(self) -> bool:
        """Return whether the current prospective order differs from the original."""

        return self._visual_mode.has_reordered()

    def set_hovered_segment(self, segment_index: int | None) -> None:
        """Track the segment currently under the pointer and repaint states."""

        changed = self._gesture.set_hovered_segment(segment_index)
        if not changed:
            return
        self._pointer_region_visual.sync_interaction_state()
        self._render_publication.sync(reason="hovered_segment_changed")

    def activate_segment(self, segment_index: int) -> None:
        """Track the segment that should retain selection if a commit happens."""

        self._gesture.activate_segment(segment_index)
        self._pointer_region_visual.sync_interaction_state()
        self._render_publication.sync(reason="active_segment_changed")

    def set_pointer_cursor(self, cursor_shape: Qt.CursorShape) -> None:
        """Apply the cursor selected by the overlay's logical pointer owner."""

        if self.cursor().shape() != cursor_shape:
            self.setCursor(cursor_shape)

    def pointer_region_rects(self) -> dict[int, QRect]:
        """Return visible overlay-local chip regions for harness interaction."""

        return {
            segment_index: QRect(region.rect)
            for segment_index, region in self._chips_by_index.items()
            if region.visible
        }

    def pointer_region(self, segment_index: int) -> PromptReorderPointerRegion:
        """Return one logical chip region for focused diagnostics."""

        region = self._chips_by_index.get(segment_index)
        if region is None or not region.visible:
            raise KeyError(segment_index)
        return region

    def set_pressed_segment(self, segment_index: int | None) -> None:
        """Track which segment pointer press is currently held down."""

        self._gesture.set_pressed_segment(segment_index)
        self._pointer_region_visual.sync_interaction_state()

    def emit_preview_layout_changed(self) -> None:
        """Notify listeners that the reorder preview layout contract changed."""

        self.previewLayoutChanged.emit()
