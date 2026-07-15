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

# mypy: disable-error-code="assignment,misc"
# Overlay shell mixins share state initialized by SegmentReorderOverlay.
# These suppressions keep the concrete QWidget shell typed without duplicating
# that state into each mixin.

from __future__ import annotations

from collections.abc import Callable
import time
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
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptReorderChipView,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)

from ..geometry import (
    autocomplete_panel_host,
    reorder_overlay_content_rect,
)
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometrySnapshot,
)
from ..projection.reorder_drop_targets import (
    PromptReorderBlankLineDropLane as _BlankLineDropLane,
    PromptReorderDropTargetTracker,
    PromptReorderDropTargetVisual as _DropTargetVisual,
    PromptReorderRowDropLane as _RowDropLane,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
    PromptReorderLayoutPolicy,
    layout_view_key,
    preview_snapshot_key,
)
from ..projection.observability import (
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from ..projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
)
from ..projection.reorder_animation import PromptReorderAnimationPlanner
from ..projection.reorder_state import (
    PromptReorderGeometryGenerationState,
    PromptReorderKeyboardState,
    PromptReorderOverlayPositionGeometryKey,
    PromptReorderOverlayRefreshGeometryKey,
    PromptReorderPointerState,
    PromptReorderPreviewTargetIdentity as _PreviewTargetIdentity,
    PromptReorderPreviewTargetState,
    ReorderChipWidgetGeometryKey as _ChipWidgetGeometryKey,
    ReorderLayoutViewKey as _ReorderLayoutViewKey,
    ReorderLiveVisualGeometryKey as _LiveVisualGeometryKey,
    ReorderPreviewSnapshotKey as _ReorderPreviewSnapshotKey,
    reorder_chip_widget_geometry_key,
    reorder_overlay_position_geometry_key,
    reorder_overlay_refresh_geometry_key,
)
from .chip_visuals import PromptChipVisual
from .reorder_drag_proxy import (
    PromptReorderDragProxyWidget,
)
from .reorder_autoscroll import PromptReorderAutoscrollInvalidation
from .reorder_gesture_controller import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderDragIntent,
    PromptReorderDragPhase,
    PromptReorderDragProxyPlacementController,
    PromptReorderGestureController,
)
from ..models import PromptReorderCommitSnapshot
from .reorder_view import PromptReorderVisualStyle
from .reorder_telemetry import PromptReorderTelemetry
from .reorder_landing_shadow import (
    PromptReorderLandingShadowPresenter,
)
from .reorder_animation_presenter import PromptReorderAnimationPresenter
from .reorder_displacement_session import ReorderDisplacementSession
from .reorder_held_chip_presenter import PromptReorderHeldChipPresenter
from .reorder_overlay_animation import PromptReorderOverlayAnimationMixin
from .reorder_overlay_geometry import PromptReorderOverlayGeometryMixin
from .reorder_overlay_interaction import PromptReorderOverlayInteractionMixin
from .reorder_overlay_ports import (
    PromptReorderAutoscrollFactory,
    PromptReorderDragProxyStateFactory,
    PromptReorderEditor,
    PromptReorderOverlay,
    PromptReorderOverlayRenderState,
    PromptReorderViewFactory,
    SegmentChipDragController,
)
from .reorder_raster_cache import PromptReorderRasterCache, ReorderRasterEntry
from .reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
    PromptReorderVisualSnapshotCache,
)

_INSERTION_WIDTH = 10.0
_SHADOW_ACTUAL_MISMATCH_X = 8.0
_SHADOW_ACTUAL_MISMATCH_Y = 8.0
_SLOW_DRAG_MOVE_MS = 16.0
_SLOW_LIVE_VISUALS_MS = 8.0


class _SegmentChip(QWidget):
    """Capture hover and drag input for one prompt segment without reflowing text."""

    def __init__(
        self,
        segment: PromptReorderChipView,
        *,
        controller: SegmentChipDragController,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize one transparent hotspot for the supplied prompt segment."""

        super().__init__(parent)
        self.segment_index = segment.index
        self._segment = segment
        self._controller = controller
        self._press_global_pos: QPoint | None = None
        self._drag_started = False
        self._last_mouse_event_at: float | None = None
        self.setObjectName("segmentChip")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setProperty("segmentIndex", segment.index)
        self.setProperty("segmentText", self.drag_proxy_text())
        self.setProperty("active", False)
        self.setProperty("dragging", False)
        self.setProperty("hovered", False)

    def drag_proxy_text(self) -> str:
        """Return the segment label used by the floating drag proxy."""

        if self._segment.has_separator_after:
            return f"{self._segment.display_text},"
        return self._segment.display_text

    def set_visual_state(self, *, active: bool, dragging: bool, hovered: bool) -> None:
        """Expose test-visible state on the transparent hotspot widget."""

        self.setProperty("active", active)
        self.setProperty("dragging", dragging)
        self.setProperty("hovered", hovered)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Report hover entry so the overlay can repaint the hovered segment."""

        self._controller.set_hovered_segment(self.segment_index)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover state when the pointer leaves this hotspot."""

        self._controller.set_hovered_segment(None)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Prime one drag gesture when the user presses the hotspot."""

        self._log_mouse_event("mouse.press", event)
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        self._controller.retain_editor_focus()
        self._controller.activate_chip(self)
        self._controller.set_pressed_segment(self.segment_index)
        self._press_global_pos = event.globalPosition().toPoint()
        self._drag_started = False
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Start or continue one drag gesture while the left button stays down."""

        self._log_mouse_event("mouse.move", event)
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return

        self._controller.retain_editor_focus()
        global_pos = event.globalPosition().toPoint()
        drag_distance = (
            0
            if self._press_global_pos is None
            else (global_pos - self._press_global_pos).manhattanLength()
        )
        if (
            not self._drag_started
            and self._press_global_pos is not None
            and drag_distance >= QApplication.startDragDistance()
        ):
            self._drag_started = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._log_interaction_event(
                "mouse.drag_threshold_crossed",
                segment_index=self.segment_index,
                global_x=global_pos.x(),
                global_y=global_pos.y(),
                drag_distance=drag_distance,
                threshold=QApplication.startDragDistance(),
            )
            self._controller.start_drag(
                self,
                global_pos=global_pos,
                press_global_pos=self._press_global_pos,
            )

        if self._drag_started:
            self._controller.drag_move(self, global_pos)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End one drag gesture or clear the primed click state."""

        self._log_mouse_event("mouse.release", event)
        self._press_global_pos = None

        if self._drag_started and event.button() == Qt.MouseButton.LeftButton:
            self._controller.retain_editor_focus()
            self._drag_started = False
            self._controller.end_drag(self)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._controller.retain_editor_focus()
            self._controller.set_pressed_segment(None)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _log_mouse_event(self, event_name: str, event: QMouseEvent) -> None:
        """Record raw mouse ingress for drag performance attribution."""

        now = time.perf_counter()
        elapsed_since_previous_ms = (
            None
            if self._last_mouse_event_at is None
            else (now - self._last_mouse_event_at) * 1000.0
        )
        self._last_mouse_event_at = now
        global_pos = event.globalPosition().toPoint()
        drag_distance = (
            None
            if self._press_global_pos is None
            else (global_pos - self._press_global_pos).manhattanLength()
        )
        self._log_interaction_event(
            event_name,
            segment_index=self.segment_index,
            button=str(event.button()),
            buttons=str(event.buttons()),
            global_x=global_pos.x(),
            global_y=global_pos.y(),
            drag_started=self._drag_started,
            drag_distance=drag_distance,
            elapsed_since_previous_ms=elapsed_since_previous_ms,
        )

    def _log_interaction_event(self, event: str, **context: object) -> None:
        """Delegate chip telemetry to the overlay interaction wrapper."""

        self._controller.log_interaction_event(event, **context)


class SegmentReorderOverlay(
    PromptReorderOverlayInteractionMixin,
    PromptReorderOverlayGeometryMixin,
    PromptReorderOverlayAnimationMixin,
    QWidget,
):
    """Show prompt segment reorder affordances over the existing text surface."""

    previewLayoutChanged = Signal()

    def __init__(
        self,
        editor: QWidget,
        *,
        geometry: PromptReorderInteractionGeometry,
        view_factory: PromptReorderViewFactory,
        gesture_controller: PromptReorderGestureController,
        drag_proxy_placement: PromptReorderDragProxyPlacementController,
        autoscroll_factory: PromptReorderAutoscrollFactory,
        drag_proxy: PromptReorderDragProxyWidget,
        drag_proxy_state_factory: PromptReorderDragProxyStateFactory,
    ) -> None:
        """Build one viewport-local reorder overlay for the supplied editor."""

        self._editor = cast(PromptReorderEditor, editor)
        super().__init__(self._editor.viewport())
        self._geometry = geometry
        self._telemetry = PromptReorderTelemetry()
        self._landing_shadow = PromptReorderLandingShadowPresenter(
            telemetry=self._telemetry,
            log_event=self._log_interaction_event,
            log_timing=self._log_interaction_timing,
        )
        self._animation_presenter = PromptReorderAnimationPresenter(
            parent=self,
            frame_callback=self._sync_reorder_animation_frame,
        )
        self._animation_planner = PromptReorderAnimationPlanner()
        self._displacement_session = ReorderDisplacementSession()
        self._held_chip_presenter = PromptReorderHeldChipPresenter(
            parent=self,
            frame_callback=self._sync_reorder_animation_frame,
        )
        self._raster_cache = PromptReorderRasterCache()
        self._live_raster_entries_render_key: tuple[object, ...] | None = None
        self._live_raster_entries_by_index: dict[int, ReorderRasterEntry] = {}
        self._preview_raster_entries_render_key: tuple[object, ...] | None = None
        self._preview_raster_entries_by_index: dict[int, ReorderRasterEntry] = {}
        self._drop_target_tracker = PromptReorderDropTargetTracker()
        self.setObjectName("segmentReorderOverlay")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._applying_theme_styles = False
        self._view = view_factory(self)
        self._view.setGeometry(self.rect())
        self._view.lower()
        self._view.show()
        self._visual_style = PromptReorderVisualStyle.from_current_theme()
        self._content_rect = QRect()
        self._document_view: PromptDocumentView | None = None
        self._source_revision: int | None = None
        self._original_layout_view: PromptReorderLayoutView | None = None
        self._current_layout_view: PromptReorderLayoutView | None = None
        self._base_drag_layout_view: PromptReorderLayoutView | None = None
        self._preview_layout_view: PromptReorderLayoutView | None = None
        self._original_reorder_state: PromptReorderStateView | None = None
        self._current_reorder_state: PromptReorderStateView | None = None
        self._base_drag_reorder_state: PromptReorderStateView | None = None
        self._preview_reorder_state: PromptReorderStateView | None = None
        self._preview_snapshot: PromptReorderPreviewSnapshot | None = None
        self._base_drag_snapshot: PromptReorderPreviewSnapshot | None = None
        self._preview_layout_target_identity: _PreviewTargetIdentity | None = None
        self._preview_geometry_target_identity: _PreviewTargetIdentity | None = None
        self._segments_by_index: dict[int, PromptReorderChipView] = {}
        self._visuals_by_index: dict[int, PromptChipVisual] = {}
        self._preview_visuals_by_index: dict[int, PromptChipVisual] = {}
        self._base_drag_visuals_by_index: dict[int, PromptChipVisual] = {}
        self._live_visual_snapshots_by_index: dict[
            int, PromptReorderChipVisualSnapshot
        ] = {}
        self._preview_visual_snapshots_by_index: dict[
            int, PromptReorderChipVisualSnapshot
        ] = {}
        self._visual_snapshot_cache = PromptReorderVisualSnapshotCache()
        self._chip_geometry_snapshot: PromptReorderChipGeometrySnapshot | None = None
        self._preview_chip_geometry_snapshot: (
            PromptReorderChipGeometrySnapshot | None
        ) = None
        self._base_drag_chip_geometry_snapshot: (
            PromptReorderChipGeometrySnapshot | None
        ) = None
        self._last_live_visual_geometry_key: _LiveVisualGeometryKey | None = None
        self._last_overlay_position_geometry_key: (
            PromptReorderOverlayPositionGeometryKey | None
        ) = None
        self._last_overlay_refresh_geometry_key: (
            PromptReorderOverlayRefreshGeometryKey | None
        ) = None
        self._last_chip_widget_geometry_key: _ChipWidgetGeometryKey | None = None
        self._pending_autoscroll_invalidation: (
            PromptReorderAutoscrollInvalidation | None
        ) = None
        self._chips_by_index: dict[int, _SegmentChip] = {}
        self._initial_ordered_indices: tuple[int, ...] = ()
        self._ordered_segment_indices: list[int] = []
        self._gesture = gesture_controller
        self._drag_handler: Callable[[PromptReorderDragIntent], None] | None = None
        self._commit_handler: Callable[[PromptReorderCommitIntent], None] | None = None
        self._cancel_handler: Callable[[PromptReorderCancelIntent], None] | None = None
        self._placement_snapshot: PromptReorderPlacementSnapshot | None = None
        self._active_placement: PromptReorderPlacementGeometry | None = None
        self._drop_target_visuals: tuple[_DropTargetVisual, ...] = ()
        self._drop_target_lanes: tuple[_RowDropLane | _BlankLineDropLane, ...] = ()
        self._last_drop_commit_visual: PromptChipVisual | None = None
        self._last_drop_commit_geometry: PromptReorderChipGeometry | None = None
        self._last_drop_commit_target: PromptReorderDropTarget | None = None
        self._last_drop_commit_placement: PromptReorderPlacementGeometry | None = None
        self._last_drop_commit_segment_index: int | None = None
        self._last_drop_commit_gesture_id: int | None = None
        self._last_drop_commit_event_id: int | None = None
        self._instrumentation_gesture_id: int | None = None
        self._instrumentation_event_id: int | None = None
        self._instrumentation_next_event_id = 0
        self._instrumentation_drag_move_count = 0
        self._instrumentation_target_change_count = 0
        self._instrumentation_drop_target_no_change_count = 0
        self._instrumentation_drop_target_changed_count = 0
        self._instrumentation_no_lane_count = 0
        self._instrumentation_anomaly_count = 0
        self._instrumentation_split_shadow_count = 0
        self._instrumentation_preview_sync_immediate_count = 0
        self._instrumentation_preview_sync_deferred_count = 0
        self._instrumentation_pointer_unexpected_work_count = 0
        self._instrumentation_pointer_preview_rebuild_count = 0
        self._instrumentation_pointer_full_refresh_count = 0
        self._instrumentation_pointer_base_cache_miss_count = 0
        self._instrumentation_pointer_paint_request_count = 0
        self._instrumentation_refresh_work_unit_count = 0
        self._instrumentation_skipped_refresh_count = 0
        self._instrumentation_expected_diagnostic_count = 0
        self._instrumentation_position_refresh_skip_count = 0
        self._instrumentation_position_refresh_run_count = 0
        self._instrumentation_preview_scheduler_request_count = 0
        self._instrumentation_preview_scheduler_run_count = 0
        self._instrumentation_preview_scheduler_stale_skip_count = 0
        self._instrumentation_autoscroll_schedule_count = 0
        self._instrumentation_autoscroll_coalesced_count = 0
        self._instrumentation_autoscroll_flush_count = 0
        self._instrumentation_autoscroll_target_refresh_count = 0
        self._instrumentation_preview_geometry_suppressed_count = 0
        self._instrumentation_preview_geometry_full_count = 0
        self._instrumentation_base_drag_geometry_reuse_count = 0
        self._instrumentation_base_drag_geometry_rebuild_count = 0
        self._instrumentation_preview_geometry_reused_chip_count = 0
        self._instrumentation_preview_geometry_rebuilt_chip_count = 0
        self._instrumentation_preview_geometry_reuse_rejected_count = 0
        self._instrumentation_marker_fallback_count = 0
        self._instrumentation_animation_plan_build_count = 0
        self._instrumentation_work_unit_id = 0
        self._animation_generation_id = 0
        self._animation_frame_batch_depth = 0
        self._animation_frame_sync_pending = False
        self._last_suppressed_chip_indices: frozenset[int] = frozenset()
        self._pointer_loop_depth = 0
        self._instrumentation_max_drag_move_ms = 0.0
        self._instrumentation_max_live_visuals_ms = 0.0
        self._instrumentation_max_preview_sync_ms = 0.0
        self._instrumentation_max_render_plan_ms = 0.0
        self._instrumentation_raster_entries_render_cache_hit_count = 0
        self._instrumentation_raster_entries_render_cache_miss_count = 0
        self._drag_proxy_host = autocomplete_panel_host(cast(QWidget, self._editor))
        self._drag_proxy = drag_proxy
        self._drag_proxy_state_factory = drag_proxy_state_factory
        self._drag_proxy_placement = drag_proxy_placement
        self._drag_proxy.setParent(self._drag_proxy_host)
        self._drag_proxy.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._drag_proxy.setFont(self._editor.viewport().font())
        self._drag_proxy.hide()
        self._autoscroll = autoscroll_factory(
            self,
            step_callback=self._handle_autoscroll_step,
            context_provider=self._autoscroll_context,
        )
        self._apply_theme_colors()

    def changeEvent(self, event: QEvent) -> None:
        """Refresh overlay colors after palette or theme changes."""

        if (
            event.type()
            in (
                QEvent.Type.PaletteChange,
                QEvent.Type.ApplicationPaletteChange,
                QEvent.Type.FontChange,
                QEvent.Type.ApplicationFontChange,
                QEvent.Type.StyleChange,
            )
            and not self._applying_theme_styles
        ):
            self._settle_chip_animations(reason="theme_or_font_change")
            self._clear_reorder_visual_snapshots(reason="theme_or_font_change")
            self._drag_proxy.setFont(self._editor.viewport().font())
            self._drag_proxy_state_factory.invalidate(reason="theme_or_font_change")
            self._apply_theme_colors()
            self._ensure_drag_proxy_render_state()
            self.refresh_geometry(reason="theme_change")
        super().changeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep drag proxy placement synchronized when the overlay resizes."""

        super().resizeEvent(event)
        self._view.setGeometry(self.rect())
        self._sync_reorder_view_state(reason="overlay_resize")
        if self._gesture.state.last_drag_global_position is not None:
            self._move_drag_proxy(self._gesture.state.last_drag_global_position)

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh chip geometry after the overlay becomes visible to Qt."""

        super().showEvent(event)
        self.refresh_geometry(reason="overlay_show")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Dispose the floating drag proxy when the overlay itself closes."""

        self._settle_chip_animations(reason="overlay_close")
        self._clear_reorder_visual_snapshots(reason="overlay_close")
        self._drag_proxy.hide()
        self._drag_proxy.deleteLater()
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Consume non-segment presses so text selection cannot start underneath."""

        self.retain_editor_focus()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Consume non-segment moves so the editor I-beam does not win."""

        self.retain_editor_focus()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Consume non-segment releases while reorder mode is active."""

        self.retain_editor_focus()
        event.accept()

    def set_chips(
        self,
        document_view: PromptDocumentView,
        reorder_layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        chips: tuple[PromptReorderChipView, ...],
        active_chip_index: int | None = None,
        source_revision: int | None = None,
    ) -> None:
        """Populate overlay hotspots from the current reorder-chip snapshot."""

        started_at = reorder_drag_started_at()
        self._cancel_chip_animations(reason="set_chips")
        self._clear_reorder_visual_snapshots(reason="set_chips")
        self.cancel_drag()
        self._delete_existing_chips()
        self._document_view = document_view
        self._source_revision = source_revision
        self._original_layout_view = reorder_layout_view
        self._current_layout_view = reorder_layout_view
        self._original_reorder_state = reorder_state
        self._current_reorder_state = reorder_state
        self._base_drag_reorder_state = None
        self._preview_reorder_state = None
        self._geometry.set_session(
            document_view,
            reorder_layout_view,
            reorder_state,
            ordered_indices=tuple(segment.index for segment in chips),
        )
        self._base_drag_layout_view = None
        self._preview_layout_view = None
        self._clear_preview_target_identity()
        self._last_live_visual_geometry_key = None
        self._last_overlay_position_geometry_key = None
        self._last_overlay_refresh_geometry_key = None
        self._last_chip_widget_geometry_key = None
        segments = chips
        self._segments_by_index = {segment.index: segment for segment in segments}
        self._initial_ordered_indices = tuple(segment.index for segment in segments)
        self._ordered_segment_indices = list(self._initial_ordered_indices)
        self._gesture.reset_all()
        active_segment_index = (
            active_chip_index if active_chip_index in self._segments_by_index else None
        )
        if active_segment_index is not None:
            self._gesture.activate_segment(active_segment_index)
        self._placement_snapshot = None
        self._active_placement = None
        self._drop_target_visuals = ()
        self._drop_target_lanes = ()
        self._preview_snapshot = None
        self._base_drag_snapshot = None
        self._landing_shadow.reset_session_state()
        self._chips_by_index = {
            segment.index: _SegmentChip(segment, controller=self, parent=self)
            for segment in segments
        }
        self._view.lower()
        self.refresh_geometry(reason="set_chips")
        self._log_interaction_timing(
            "overlay.set_chips",
            started_at=started_at,
            segment_count=len(segments),
            row_count=len(reorder_layout_view.rows),
            gap_count=len(reorder_layout_view.gaps),
            active_chip_index=active_chip_index,
        )

    def set_render_state(self, state: PromptReorderOverlayRenderState) -> None:
        """Accept externally prepared render state for the passive overlay port."""

        _ = state

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for drag intent publication."""

        self._drag_handler = handler

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for commit intent publication."""

        self._commit_handler = handler

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for cancel intent publication."""

        self._cancel_handler = handler

    def request_geometry_refresh(self, *, reason: str) -> None:
        """Request a bounded geometry refresh for the current overlay state."""

        self.refresh_geometry(reason=reason)

    def show_overlay(self) -> None:
        """Show the overlay without changing prompt source."""

        self.show()

    def hide_overlay(self) -> None:
        """Hide the overlay without changing prompt source."""

        self._settle_chip_animations(reason="overlay_hide")
        self._clear_reorder_visual_snapshots(reason="overlay_hide")
        self.hide()

    def _clear_reorder_visual_snapshots(self, *, reason: str) -> None:
        """Clear cached full-chip visual snapshots and document suppression."""

        self._live_visual_snapshots_by_index = {}
        self._preview_visual_snapshots_by_index = {}
        self._visual_snapshot_cache.clear()
        self._raster_cache.clear()
        self._clear_reorder_raster_entry_cache()
        self._last_live_visual_geometry_key = None
        self._last_overlay_refresh_geometry_key = None
        self._displacement_session.bump_raster_generation()
        self._set_reorder_overlay_suppression(frozenset())

    def _clear_reorder_raster_entry_cache(self) -> None:
        """Clear render-state memoization that wraps the raster cache."""

        self._live_raster_entries_render_key = None
        self._live_raster_entries_by_index = {}
        self._preview_raster_entries_render_key = None
        self._preview_raster_entries_by_index = {}

    def set_preview_snapshot(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None = None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Apply one controller-built preview snapshot for chrome geometry refresh."""

        started_at = reorder_drag_started_at()
        animation_start_rects = self._current_visible_chip_rects_for_animation()
        self._geometry.set_preview_snapshots(
            snapshot,
            base_drag_snapshot=base_drag_snapshot,
            ordered_chip_indices=ordered_chip_indices,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
            viewport_identity=self._overlay_position_geometry_key(),
        )
        self._preview_snapshot = self._geometry.preview_snapshot
        self._base_drag_snapshot = self._geometry.base_drag_snapshot
        self._ordered_segment_indices = list(self._geometry.ordered_segment_indices)
        self._preview_layout_target_identity = (
            self._geometry.preview_layout_target_identity
        )
        self._preview_geometry_target_identity = (
            self._geometry.preview_geometry_target_identity
        )
        self._refresh_preview_geometry()
        animation_plan = self._build_reorder_animation_plan_if_ready(
            current_visuals=animation_start_rects
        )
        self._update_chip_geometry()
        if animation_plan is not None:
            self.apply_animation_plan(animation_plan)
        else:
            self._sync_reorder_view_state(reason="set_preview_snapshot")
        if self._gesture.state.active_drop_target is None:
            self._log_interaction_event(
                "preview_state.fresh",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                reason="no_active_target",
            )
        elif self._active_placement is not None:
            self._log_interaction_event(
                "preview_state.caught_up",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                active_target_kind=reorder_drag_target_kind(
                    self._gesture.state.active_drop_target
                ),
                has_expected_landing=(
                    self._active_placement.expected_landing_chip_index is not None
                ),
            )
        if self._last_drop_commit_segment_index is not None:
            self._log_post_drop_geometry_checkpoint(
                checkpoint="set_preview_snapshot.after_surface_sync",
                segment_index=self._last_drop_commit_segment_index,
            )
            self._clear_last_drop_commit_context()
        self._log_interaction_timing(
            "overlay.set_preview_snapshot",
            started_at=started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            has_preview_snapshot=snapshot is not None,
            has_base_drag_snapshot=base_drag_snapshot is not None,
            ordered_count=len(self._ordered_segment_indices),
            preview_visual_count=len(self._preview_visuals_by_index),
            base_drag_visual_count=len(self._base_drag_visuals_by_index),
            lane_count=len(self._drop_target_lanes),
        )

    def refresh_geometry(self, *, reason: str = "unspecified") -> None:
        """Route one explicit invalidation reason to minimal overlay refresh work."""

        started_at = reorder_drag_started_at()
        work_unit_id = self.next_instrumentation_work_unit_id()
        self._instrumentation_refresh_work_unit_count += 1
        previous_key = self._last_overlay_refresh_geometry_key
        overlay_rect_changed = self._refresh_overlay_rect()
        next_key = self._overlay_refresh_geometry_key()
        self._last_overlay_position_geometry_key = self._overlay_position_geometry_key()
        drag_active = self._gesture.state.dragged_segment_index is not None
        key_changed = previous_key != next_key
        preview_snapshot_changed = (
            previous_key is None
            or previous_key.preview_snapshot_key != next_key.preview_snapshot_key
            or previous_key.preview_layout_key != next_key.preview_layout_key
            or previous_key.active_target != next_key.active_target
        )
        if key_changed and not preview_snapshot_changed:
            self._settle_chip_animations(reason=f"geometry_refresh:{reason}")
        self._log_interaction_event(
            "overlay.refresh_geometry.requested",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            has_preview_snapshot=self._preview_snapshot is not None,
            has_base_drag_snapshot=self._base_drag_snapshot is not None,
            geometry_key_changed=key_changed,
            preview_key_changed=preview_snapshot_changed,
            live_key_changed=(
                previous_key is None
                or previous_key.live_geometry_key != next_key.live_geometry_key
            ),
            viewport_width=next_key.viewport_width,
            viewport_height=next_key.viewport_height,
            scroll_offset=next_key.scroll_offset,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
        )
        if previous_key == next_key and self._visuals_by_index:
            self._instrumentation_skipped_refresh_count += 1
            proxy_changed = False
            if overlay_rect_changed:
                proxy_changed = self._sync_drag_proxy_geometry_if_needed(reason=reason)
            elapsed_ms = self._log_interaction_timing(
                "overlay.refresh_geometry.skip_unchanged",
                started_at=started_at,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                work_unit_id=work_unit_id,
                reason=reason,
                drag_active=drag_active,
                content_width=self._content_rect.width(),
                content_height=self._content_rect.height(),
                visual_count=len(self._visuals_by_index),
                preview_visual_count=len(self._preview_visuals_by_index),
                lane_count=len(self._drop_target_lanes),
                overlay_rect_changed=overlay_rect_changed,
                proxy_changed=proxy_changed,
            )
            if elapsed_ms >= _SLOW_LIVE_VISUALS_MS:
                self._log_interaction_event(
                    "budget.position_refresh_exceeded",
                    gesture_id=self._instrumentation_gesture_id,
                    event_id=self._instrumentation_event_id,
                    work_unit_id=work_unit_id,
                    elapsed_ms=f"{elapsed_ms:.3f}",
                    threshold_ms=f"{_SLOW_LIVE_VISUALS_MS:.3f}",
                    reason=reason,
                    skipped=True,
                )
            self._log_interaction_timing(
                "overlay.refresh_geometry",
                started_at=started_at,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                work_unit_id=work_unit_id,
                reason=reason,
                skipped=True,
                skipped_elapsed_ms=f"{elapsed_ms:.3f}",
            )
            return

        if self._pointer_loop_depth > 0:
            self.record_pointer_unexpected_work("full_refresh", reason=reason)

        live_changed = self._refresh_live_chip_geometry_if_needed(reason=reason)
        preview_changed = self._refresh_preview_geometry_if_needed(reason=reason)
        chip_geometry_changed = self._sync_chip_widget_geometry_if_needed(reason=reason)
        proxy_changed = self._sync_drag_proxy_geometry_if_needed(reason=reason)
        self._last_overlay_refresh_geometry_key = next_key
        if live_changed or preview_changed or chip_geometry_changed or proxy_changed:
            self._sync_reorder_view_state(reason=reason)
            if self._pointer_loop_depth > 0:
                self.record_pointer_unexpected_work("paint_request", reason=reason)
        event_name = self._refresh_geometry_event_name(
            live_changed=live_changed,
            preview_changed=preview_changed,
            proxy_changed=proxy_changed,
        )
        self._log_interaction_timing(
            event_name,
            started_at=started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            content_width=self._content_rect.width(),
            content_height=self._content_rect.height(),
            visual_count=len(self._visuals_by_index),
            preview_visual_count=len(self._preview_visuals_by_index),
            lane_count=len(self._drop_target_lanes),
            live_changed=live_changed,
            preview_changed=preview_changed,
            chip_geometry_changed=chip_geometry_changed,
            proxy_changed=proxy_changed,
        )
        self._log_interaction_timing(
            "overlay.refresh_geometry",
            started_at=started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            skipped=False,
            content_width=self._content_rect.width(),
            content_height=self._content_rect.height(),
            visual_count=len(self._visuals_by_index),
            preview_visual_count=len(self._preview_visuals_by_index),
            lane_count=len(self._drop_target_lanes),
        )

    def needs_position_refresh(
        self,
        *,
        reason: str = "unspecified",
    ) -> bool:
        """Return whether viewport positioning inputs changed since the last sync."""

        work_unit_id = self.next_instrumentation_work_unit_id()
        previous_key = self._last_overlay_position_geometry_key
        next_key = self._overlay_position_geometry_key()
        changed = previous_key != next_key
        drag_active = self._gesture.state.dragged_segment_index is not None
        self._log_interaction_event(
            "overlay.position_refresh.requested",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            position_key_changed=changed,
            viewport_width=next_key.viewport_width,
            viewport_height=next_key.viewport_height,
            scroll_offset=next_key.scroll_offset,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
        )
        if changed:
            self._instrumentation_position_refresh_run_count += 1
            self._log_interaction_event(
                "overlay.position_refresh.ran",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                work_unit_id=work_unit_id,
                reason=reason,
                drag_active=drag_active,
                position_key_changed=True,
            )
            return True
        self._instrumentation_position_refresh_skip_count += 1
        self._log_interaction_event(
            "overlay.position_refresh.skip_unchanged",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            position_key_changed=False,
        )
        return False

    def _refresh_overlay_rect(self) -> bool:
        """Sync overlay/content rect and return whether either rect changed."""

        previous_geometry = QRect(self.geometry())
        previous_content_rect = QRect(self._content_rect)
        self.setGeometry(self._editor.viewport().rect())
        self._content_rect = reorder_overlay_content_rect(self._editor)
        return (
            previous_geometry != self.geometry()
            or previous_content_rect != self._content_rect
        )

    def _overlay_position_geometry_key(self) -> PromptReorderOverlayPositionGeometryKey:
        """Return the cheap viewport identity used to gate overlay positioning."""

        viewport_rect = self._editor.viewport().rect()
        content_rect = reorder_overlay_content_rect(self._editor)
        scrollbar = self._editor.verticalScrollBar()
        return reorder_overlay_position_geometry_key(
            viewport_left=viewport_rect.left(),
            viewport_top=viewport_rect.top(),
            viewport_width=viewport_rect.width(),
            viewport_height=viewport_rect.height(),
            content_left=content_rect.left(),
            content_top=content_rect.top(),
            content_width=content_rect.width(),
            content_height=content_rect.height(),
            scroll_offset=scrollbar.value(),
        )

    def _refresh_live_chip_geometry_if_needed(self, *, reason: str) -> bool:
        """Refresh live chip geometry when live geometry identity changed."""

        previous_visuals = self._visuals_by_index
        previous_visual_snapshots = self._live_visual_snapshots_by_index
        self._visuals_by_index = self._build_visuals_if_needed(reason=reason)
        return (
            self._visuals_by_index != previous_visuals
            or self._live_visual_snapshots_by_index != previous_visual_snapshots
        )

    def _refresh_preview_geometry_if_needed(self, *, reason: str) -> bool:
        """Refresh preview and base geometry when preview identity changed."""

        previous_preview_visuals = self._preview_visuals_by_index
        previous_base_visuals = self._base_drag_visuals_by_index
        previous_lane_count = len(self._drop_target_lanes)
        self._update_preview_layout()
        self._refresh_preview_geometry()
        changed = (
            previous_preview_visuals != self._preview_visuals_by_index
            or previous_base_visuals != self._base_drag_visuals_by_index
            or previous_lane_count != len(self._drop_target_lanes)
        )
        if changed and self._pointer_loop_depth > 0:
            self.record_pointer_unexpected_work("preview_rebuild", reason=reason)
        return changed

    def _sync_chip_widget_geometry_if_needed(self, *, reason: str) -> bool:
        """Move chip widgets when visual geometry identity changed."""

        next_key = self._chip_widget_geometry_key()
        if next_key == self._last_chip_widget_geometry_key:
            self._log_interaction_event(
                "chip_geometry.update_skipped_unchanged",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                reason=reason,
                chip_count=len(self._chips_by_index),
            )
            return False
        self._last_chip_widget_geometry_key = next_key
        self._update_chip_geometry()
        return True

    def _sync_drag_proxy_geometry_if_needed(self, *, reason: str) -> bool:
        """Move drag proxy for the last pointer position without preview work."""

        if self._gesture.state.last_drag_global_position is None:
            return False
        previous_geometry = QRect(self._drag_proxy.geometry())
        self._move_drag_proxy(self._gesture.state.last_drag_global_position)
        changed = previous_geometry != self._drag_proxy.geometry()
        self._log_interaction_event(
            "overlay.refresh_geometry.proxy_only",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            reason=reason,
            proxy_changed=changed,
        )
        return changed

    @staticmethod
    def _refresh_geometry_event_name(
        *,
        live_changed: bool,
        preview_changed: bool,
        proxy_changed: bool,
    ) -> str:
        """Return the most specific refresh event name for completed work."""

        if live_changed and preview_changed:
            return "overlay.refresh_geometry.full"
        if preview_changed:
            return "overlay.refresh_geometry.preview_only"
        if live_changed:
            return "overlay.refresh_geometry.live_only"
        if proxy_changed:
            return "overlay.refresh_geometry.proxy_only"
        return "overlay.refresh_geometry.skip_unchanged"

    def _overlay_refresh_geometry_key(self) -> PromptReorderOverlayRefreshGeometryKey:
        """Return a conservative identity for broad overlay refresh work."""

        viewport_rect = self._editor.viewport().rect()
        scrollbar = self._editor.verticalScrollBar()
        source_text = (
            "" if self._document_view is None else self._document_view.source_text
        )
        position_key = reorder_overlay_position_geometry_key(
            viewport_left=viewport_rect.left(),
            viewport_top=viewport_rect.top(),
            viewport_width=viewport_rect.width(),
            viewport_height=viewport_rect.height(),
            content_left=self._content_rect.left(),
            content_top=self._content_rect.top(),
            content_width=self._content_rect.width(),
            content_height=self._content_rect.height(),
            scroll_offset=scrollbar.value(),
        )
        return reorder_overlay_refresh_geometry_key(
            position_key=position_key,
            source_text=source_text,
            live_geometry_key=self._live_visual_geometry_key(),
            current_layout_key=self._layout_view_key(self._current_layout_view),
            preview_layout_key=self._layout_view_key(self._preview_layout_view),
            base_drag_layout_key=self._layout_view_key(self._base_drag_layout_view),
            preview_snapshot_key=self._preview_snapshot_key(self._preview_snapshot),
            base_drag_snapshot_key=self._preview_snapshot_key(self._base_drag_snapshot),
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
        )

    def _chip_widget_geometry_key(self) -> _ChipWidgetGeometryKey:
        """Return the current visual identity used to place transparent chip widgets."""

        preview_rects = tuple(
            sorted(
                (
                    segment_index,
                    visual.hotspot_rect.left(),
                    visual.hotspot_rect.top(),
                    visual.hotspot_rect.width(),
                    visual.hotspot_rect.height(),
                )
                for segment_index, visual in self._preview_visuals_by_index.items()
            )
        )
        live_rects = tuple(
            sorted(
                (
                    segment_index,
                    visual.hotspot_rect.left(),
                    visual.hotspot_rect.top(),
                    visual.hotspot_rect.width(),
                    visual.hotspot_rect.height(),
                )
                for segment_index, visual in self._visuals_by_index.items()
            )
        )
        return reorder_chip_widget_geometry_key(
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            preview_mode_active=self._preview_mode_active(),
            preview_rects=preview_rects,
            live_rects=live_rects,
        )

    @staticmethod
    def _layout_view_key(
        layout_view: PromptReorderLayoutView | None,
    ) -> _ReorderLayoutViewKey | None:
        """Return a prompt-safe key for one reorder layout view."""

        return layout_view_key(layout_view)

    @staticmethod
    def _preview_snapshot_key(
        snapshot: PromptReorderPreviewSnapshot | None,
    ) -> _ReorderPreviewSnapshotKey | None:
        """Return a prompt-safe key for one preview snapshot."""

        return preview_snapshot_key(snapshot)

    def _preview_target_identity_for_active_target(
        self,
    ) -> _PreviewTargetIdentity | None:
        """Return the preview identity expected for the active semantic target."""

        return self._geometry.preview_target_identity_for_target(
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            target=self._gesture.state.active_drop_target,
            viewport_identity=self._overlay_position_geometry_key(),
        )

    def _preview_target_identity_matches_active_target(self) -> bool:
        """Return whether current preview geometry belongs to the active target."""

        return self._geometry.preview_geometry_matches_target(
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            target=self._gesture.state.active_drop_target,
            viewport_identity=self._overlay_position_geometry_key(),
        )

    def _clear_preview_target_identity(self) -> None:
        """Clear target identity for preview layout and geometry snapshots."""

        self._geometry.clear_preview_target_identity()
        self._preview_layout_target_identity = None
        self._preview_geometry_target_identity = None

    def _preview_target_identity_context(
        self,
        identity: _PreviewTargetIdentity | None,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return structured fields for one preview target identity."""

        context = self._geometry.preview_target_identity_context(
            identity,
            prefix=prefix,
        )
        if identity is not None:
            context.update(
                self._telemetry.target_context(
                    identity.target, prefix=f"{prefix}_target"
                )
            )
        return context

    def ordered_chip_indices(self) -> list[int]:
        """Return the current flattened chip order tracked by this reorder session."""

        return list(self._ordered_segment_indices)

    def retain_editor_focus(self) -> None:
        """Keep the host editor visually and keyboard-focused during reorder input."""

        self._editor.setFocus()

    def active_segment_index(self) -> int | None:
        """Return the segment that should remain selected after commit."""

        return self._gesture.state.active_segment_index

    def dragged_segment_index(self) -> int | None:
        """Return the segment currently being dragged, when one exists."""

        return self._gesture.state.dragged_segment_index

    def drop_target(self) -> PromptReorderDropTarget | None:
        """Return the typed destination that would be committed on Alt release."""

        if self._gesture.state.dragged_segment_index is not None:
            return self._gesture.state.active_drop_target
        if not self.has_reordered():
            return None
        return self._committable_keyboard_drop_target()

    def current_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the current in-session reorder layout represented by the overlay."""

        return self._current_layout_view

    def commit_snapshot(self) -> PromptReorderCommitSnapshot:
        """Return the prepared reorder state visible to interaction owners."""

        return PromptReorderCommitSnapshot(
            reorder_state=self._current_reorder_state,
            layout_view=self._current_layout_view,
            ordered_chip_indices=tuple(self._ordered_segment_indices),
            active_segment_index=self._gesture.state.active_segment_index,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            has_reordered=self.has_reordered(),
        )

    def pointer_reorder_state(self) -> PromptReorderPointerState:
        """Return read-only pointer state without exposing QWidget ownership."""

        return self._gesture.pointer_state()

    def keyboard_reorder_state(self) -> PromptReorderKeyboardState:
        """Return read-only keyboard state without exposing QWidget ownership."""

        return self._gesture.keyboard_state()

    def preview_reorder_state(self) -> PromptReorderStateView | None:
        """Return authoritative source state for the active painted preview."""

        if self._preview_mode_active():
            return self._preview_reorder_state
        if self.has_reordered():
            return self._current_reorder_state
        return None

    def base_drag_reorder_state(self) -> PromptReorderStateView | None:
        """Return authoritative source state for the base-drag preview."""

        return self._base_drag_reorder_state

    def preview_target_state(self) -> PromptReorderPreviewTargetState:
        """Return display-only preview target state for focused tests."""

        return self._geometry.preview_target_state(
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
        )

    def geometry_generation_state(self) -> PromptReorderGeometryGenerationState:
        """Return prepared geometry generation state without QWidget references."""

        return self._geometry.geometry_generation_state(
            generation_id=self._instrumentation_work_unit_id,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
            viewport_identity=self._overlay_position_geometry_key(),
        )

    def preview_chip_indices(self) -> list[int]:
        """Return previewed chip indices in the current visible reorder order."""

        if not self._preview_mode_active():
            return []
        return [
            segment_index
            for segment_index in self.ordered_chip_indices()
            if segment_index in self._preview_visuals_by_index
        ]

    def preview_rect_for_segment(self, segment_index: int) -> QRect | None:
        """Return one preview rect when the supplied segment is visibly previewed."""

        preview_visual = self._preview_visuals_by_index.get(segment_index)
        if preview_visual is None:
            return None
        return QRect(preview_visual.hotspot_rect)

    def preview_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the layout currently represented by the reorder preview."""

        return self._layout_for_painted_preview()

    def base_drag_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the stable drag-base layout used for hit testing during drags."""

        return self._base_drag_layout_view

    def has_base_drag_placement_geometry(self) -> bool:
        """Return whether drag hit testing has projection-owned placement geometry."""

        return self._placement_snapshot is not None and bool(
            self._placement_snapshot.placements
        )

    def has_valid_initial_landing_shadow(self) -> bool:
        """Return whether the active drag has a chip-shaped landing shadow."""

        result = self._landing_shadow.has_valid_initial_landing_shadow(
            self._landing_shadow_request()
        )
        self._active_placement = result.active_placement
        self._geometry.active_placement = self._active_placement
        return result.geometry is not None

    def should_flush_initial_landing_shadow_sync(self) -> bool:
        """Return and consume the one allowed immediate first-shadow sync request."""

        result = self._landing_shadow.should_flush_initial_landing_shadow_sync(
            self._landing_shadow_request(),
            base_drag_layout_available=self._base_drag_layout_view is not None,
        )
        self._active_placement = result.active_placement
        self._geometry.active_placement = self._active_placement
        return result.should_flush

    def drag_proxy_widget(self) -> QWidget:
        """Return the floating drag proxy widget used for segment dragging."""

        return self._drag_proxy

    def instrumentation_gesture_id(self) -> int | None:
        """Return the current drag gesture identifier."""

        return self._instrumentation_gesture_id

    def instrumentation_event_id(self) -> int | None:
        """Return the latest drag event identifier."""

        return self._instrumentation_event_id

    def has_reordered(self) -> bool:
        """Return whether the current prospective order differs from the original."""

        return self._current_reorder_state != self._original_reorder_state

    def set_hovered_segment(self, segment_index: int | None) -> None:
        """Track the segment currently under the pointer and repaint states."""

        changed = self._gesture.set_hovered_segment(segment_index)
        if not changed:
            return
        self._update_chip_states()
        self._sync_reorder_view_state(reason="hovered_segment_changed")

    def activate_chip(self, chip: _SegmentChip) -> None:
        """Track the segment that should retain selection if a commit happens."""

        self._gesture.activate_segment(chip.segment_index)
        self._update_chip_states()
        self._sync_reorder_view_state(reason="active_segment_changed")

    def set_pressed_segment(self, segment_index: int | None) -> None:
        """Track which segment pointer press is currently held down."""

        self._gesture.set_pressed_segment(segment_index)
        self._update_chip_states()

    def _delete_existing_chips(self) -> None:
        """Dispose any existing hotspots before repopulating the overlay."""

        self._cancel_chip_animations(reason="delete_existing_chips")
        for chip in self._chips_by_index.values():
            chip.deleteLater()
        self._chips_by_index = {}
        self._drop_target_visuals = ()
        self._drop_target_lanes = ()
        self._placement_snapshot = None
        self._active_placement = None
        self._preview_visuals_by_index = {}
        self._base_drag_visuals_by_index = {}
        self._landing_shadow.clear_held_shadow()
        self._last_live_visual_geometry_key = None
        self._preview_snapshot = None
        self._base_drag_snapshot = None
        self._preview_reorder_state = None
        self._base_drag_reorder_state = None
        self._visuals_by_index = {}
        self._clear_reorder_raster_entry_cache()
        self._clear_drag_intent_context()
        self._clear_last_drop_commit_context()

    def _apply_theme_colors(self) -> None:
        """Refresh the palette-derived colors used by the reorder overlay."""

        if self._applying_theme_styles:
            return

        self._applying_theme_styles = True
        try:
            self._visual_style = PromptReorderVisualStyle.from_current_theme()
        finally:
            self._applying_theme_styles = False

    def _emit_preview_layout_changed(self) -> None:
        """Notify listeners that the reorder preview layout contract changed."""

        self.previewLayoutChanged.emit()


__all__ = [
    "PromptReorderCancelIntent",
    "PromptReorderCommitIntent",
    "PromptReorderDragIntent",
    "PromptReorderDragPhase",
    "PromptReorderLayoutPolicy",
    "PromptReorderAutoscrollFactory",
    "PromptReorderDragProxyStateFactory",
    "PromptReorderOverlay",
    "PromptReorderOverlayRenderState",
    "PromptReorderViewFactory",
    "SegmentReorderOverlay",
]
