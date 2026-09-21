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

from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from ..projection.reorder_interaction_geometry_identity import (
    reorder_geometry_generation_state,
    reorder_preview_target_state,
)
from ..projection.reorder_animation import PromptReorderAnimationPlan
from ..projection.reorder_state import PromptReorderAnimationGenerationState
from ..projection.reorder_state import (
    PromptReorderGeometryGenerationState,
    PromptReorderKeyboardState,
    PromptReorderPointerState,
    PromptReorderPreviewTargetState,
)
from .reorder_gesture_controller import (
    PromptReorderDragIntent,
    PromptReorderGestureController,
)
from .reorder_theme_refresh import PromptReorderThemeRefreshRequest
from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from .reorder_keyboard_interaction import (
    PromptReorderKeyboardVisualContext,
)
from .reorder_pointer_regions import (
    PromptReorderPointerRegion,
)
from .reorder_overlay_ports import (
    PromptReorderEditor,
    PromptReorderViewFactory,
)
from .reorder_overlay_runtime import (
    PromptReorderOverlayRuntimeFactory,
    PromptReorderOverlayRuntimeMount,
)
from .reorder_commit_snapshot import prompt_reorder_commit_snapshot
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner


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
        runtime_factory: PromptReorderOverlayRuntimeFactory,
    ) -> None:
        """Build one viewport-local reorder overlay for the supplied editor."""

        self._editor = cast(PromptReorderEditor, editor)
        super().__init__(self._editor.viewport())
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
        self._runtime = runtime_factory(
            PromptReorderOverlayRuntimeMount(
                surface=self,
                editor=self._editor,
                view=self._view,
                geometry=geometry,
                preview_visuals=preview_visual_owner,
                interaction_metrics=interaction_metrics,
                gesture=gesture_controller,
                pointer_gesture_controller=self,
                pointer_surface=self,
                emit_preview_layout_changed=self.previewLayoutChanged.emit,
                handle_animation_frame=self._handle_reorder_animation_frame,
                publish_warmed_rasters=self._publish_warmed_reorder_rasters,
                refresh_geometry=lambda reason: self.refresh_geometry(reason=reason),
            )
        )
        self.preview_sync_context = self._runtime.preview_sync_context
        self.preview_build_facts = self._runtime.preview_build_facts

    def changeEvent(self, event: QEvent) -> None:
        """Refresh overlay colors after palette or theme changes."""

        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.FontChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.StyleChange,
        ):
            dragged_segment_index = self._runtime.gesture.state.dragged_segment_index
            self._runtime.visual_lifecycle.refresh_theme(
                PromptReorderThemeRefreshRequest(
                    has_document=self._runtime.geometry.state.document_view is not None,
                    dragged_segment=(
                        None
                        if dragged_segment_index is None
                        else self._runtime.visual_session.segments_by_index[
                            dragged_segment_index
                        ]
                    ),
                    source_revision=self._runtime.visual_session.source_revision,
                    gesture=self._runtime.gesture.state,
                    gesture_id=self._runtime.interaction_metrics.gesture_id,
                    event_id=self._runtime.interaction_metrics.event_id,
                )
            )
        super().changeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep drag proxy placement synchronized when the overlay resizes."""

        super().resizeEvent(event)
        view = getattr(self, "_view", None)
        if view is None:
            return
        view.setGeometry(self.rect())
        runtime = getattr(self, "_runtime", None)
        if runtime is None:
            return
        runtime.render.sync(reason="overlay_resize")
        if runtime.gesture.state.last_drag_global_position is not None:
            runtime.drag_proxy.move(
                runtime.gesture.state.last_drag_global_position,
                gesture_id=runtime.interaction_metrics.gesture_id,
                event_id=runtime.interaction_metrics.event_id,
            )

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh chip geometry after the overlay becomes visible to Qt."""

        super().showEvent(event)
        if self._runtime.geometry.state.document_view is None:
            self._runtime.viewport_refresh.sync_overlay_rect()
            self._view.setGeometry(self.rect())
            return
        self.refresh_geometry(reason="overlay_show")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Route a press through overlay-owned semantic chip hit testing."""

        self._runtime.pointer_input.press(
            event,
            ordered_indices=self._runtime.geometry.state.ordered_segment_indices,
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Route hover and drag motion through one bounded input surface."""

        self._runtime.pointer_input.move(
            event,
            ordered_indices=self._runtime.geometry.state.ordered_segment_indices,
        )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Release the semantic chip gesture owned by the overlay surface."""

        self._runtime.pointer_input.release(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Refresh hover immediately when the pointer enters reorder mode."""

        region = self._runtime.pointer_regions.hit_test(
            event.position(),
            ordered_indices=self._runtime.geometry.state.ordered_segment_indices,
        )
        self.set_hovered_segment(None if region is None else region.segment_index)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover when no pressed gesture retains overlay ownership."""

        self._runtime.pointer_input.leave()
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

        self._runtime.session_activation.activate(
            document_view,
            reorder_layout_view,
            reorder_state,
            chips=chips,
            active_chip_index=active_chip_index,
            source_identity=source_identity,
        )

    def animation_generation_state(self) -> PromptReorderAnimationGenerationState:
        """Return authoritative animation generation state for diagnostics."""

        return self._runtime.animation.generation_state(
            geometry_generation_id=self._runtime.interaction_metrics.work_unit_id,
            active_target=self._runtime.gesture.state.active_drop_target,
        )

    def apply_animation_plan(self, plan: PromptReorderAnimationPlan) -> None:
        """Publish one projection-owned animation plan."""

        self._runtime.animation.apply_plan(
            plan,
            preview_geometry=self._runtime.geometry.state.preview_chip_geometry_snapshot,
        )

    def _handle_reorder_animation_frame(self) -> None:
        """Adapt one prepared animation frame to pointer and paint surfaces."""

        self._runtime.animation.sync_pointer_regions(
            regions_by_index=self._runtime.pointer_regions.regions_by_index,
            preview_active=self._runtime.visual_mode.preview_active(),
            live_visuals_by_index=self._runtime.live_visuals.visuals_by_index,
            preview_visuals_by_index=self._runtime.preview_visuals.visuals_by_index,
        )
        self._runtime.render.sync(reason="animation_frame")

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for drag intent publication."""

        self._runtime.interaction_intents.set_drag_handler(handler)

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for commit intent publication."""

        self._runtime.interaction_intents.set_commit_handler(handler)

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Set the interaction callback used for cancel intent publication."""

        self._runtime.interaction_intents.set_cancel_handler(handler)

    def request_geometry_refresh(self, *, reason: str) -> None:
        """Request a bounded geometry refresh for the current overlay state."""

        self.refresh_geometry(reason=reason)

    def flush_pending_autoscroll_invalidation(self, *, reason: str) -> bool:
        """Expose the autoscroll owner's coalesced host-boundary flush."""

        return self._runtime.autoscroll.flush_pending_invalidation(reason=reason)

    def drag_move(self, segment_index: int, global_pos: QPoint) -> None:
        """Route one pointer move into the focused reorder transition owner."""

        self._runtime.pointer_move.move(segment_index, global_pos)

    def start_drag(
        self,
        segment_index: int,
        *,
        global_pos: QPoint,
        press_global_pos: QPoint,
    ) -> None:
        """Route one threshold crossing into the focused drag-start owner."""

        self._runtime.pointer_drag_start.start(
            segment_index,
            global_position=global_pos,
            press_global_position=press_global_pos,
        )

    def end_drag(self, segment_index: int) -> None:
        """Route one pointer release into the focused completion owner."""

        self._runtime.pointer_drag_completion.end(segment_index)

    def cancel_drag(self) -> None:
        """Route one cancellation into the focused completion owner."""

        self._runtime.pointer_drag_completion.cancel()

    def prepare_drag(self, segment_index: int) -> None:
        """Prepare immutable held-chip presentation before threshold crossing."""

        self._runtime.pointer_drag_start.prepare(segment_index)

    def move_active_chip(self, intent: PromptReorderKeyboardMoveIntent) -> bool:
        """Route one keyboard intent and publish its adapter-level visual events."""

        result = self._runtime.keyboard.move(
            direction=intent.direction,
            gesture_id=self._runtime.interaction_metrics.gesture_id,
            event_id=self._runtime.interaction_metrics.event_id,
            visuals=PromptReorderKeyboardVisualContext(
                segment_indices=tuple(self._runtime.pointer_regions.regions_by_index),
                preview_active=self._runtime.visual_mode.preview_active(),
                live_visuals_by_index=self._runtime.live_visuals.visuals_by_index,
                preview_visuals_by_index=(
                    self._runtime.preview_visuals.visuals_by_index
                ),
            ),
        )
        if result.context_prepared:
            self.emit_preview_layout_changed()
        if not result.moved:
            return False
        self._runtime.pointer_region_visuals.sync_interaction_state()
        self.emit_preview_layout_changed()
        return True

    def reorder_performance_counters(self) -> dict[str, object]:
        """Return deterministic reorder owner counters for diagnostics."""

        return self._runtime.performance.snapshot()

    def show_overlay(self) -> None:
        """Show the overlay without changing prompt source."""

        self.show()

    def hide_overlay(self) -> None:
        """Hide the overlay without changing prompt source."""

        self._runtime.visual_lifecycle.hide()
        self.hide()

    def _publish_warmed_reorder_rasters(self) -> None:
        """Publish one idle-built raster batch through the passive view owner."""

        self._runtime.visual_lifecycle.publish_warmed_rasters(
            overlay_visible=self.isVisible()
        )

    def set_preview_snapshot(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None = None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Route one preview projection into the frame-transition owner."""

        self._runtime.preview_frame.apply(
            snapshot,
            base_drag_snapshot=base_drag_snapshot,
            ordered_chip_indices=ordered_chip_indices,
        )

    def refresh_geometry(self, *, reason: str = "unspecified") -> None:
        """Route one explicit invalidation into the frame-transition owner."""

        self._runtime.viewport_refresh.refresh(reason=reason)

    def needs_position_refresh(
        self,
        *,
        reason: str = "unspecified",
    ) -> bool:
        """Return whether viewport positioning changed since publication."""

        return self._runtime.viewport_refresh.needs_position_refresh(reason=reason)

    def ordered_chip_indices(self) -> list[int]:
        """Return the current flattened chip order tracked by this reorder session."""

        return list(self._runtime.geometry.state.ordered_segment_indices)

    def retain_editor_focus(self) -> None:
        """Keep the host editor visually and keyboard-focused during reorder input."""

        self._editor.setFocus()

    def active_segment_index(self) -> int | None:
        """Return the segment that should remain selected after commit."""

        return self._runtime.gesture.state.active_segment_index

    def current_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the current in-session reorder layout represented by the overlay."""

        return self._runtime.geometry.state.current_layout_view

    def commit_snapshot(self) -> PromptReorderCommitSnapshot:
        """Return the prepared reorder state visible to interaction owners."""

        state = self._runtime.geometry.state
        gesture_state = self._runtime.gesture.state
        return prompt_reorder_commit_snapshot(
            state,
            active_segment_index=gesture_state.active_segment_index,
            dragged_segment_index=gesture_state.dragged_segment_index,
            has_reordered=self.has_reordered(),
        )

    def pointer_reorder_state(self) -> PromptReorderPointerState:
        """Return read-only pointer state without exposing QWidget ownership."""

        return self._runtime.gesture.pointer_state()

    def keyboard_reorder_state(self) -> PromptReorderKeyboardState:
        """Return read-only keyboard state without exposing QWidget ownership."""

        return self._runtime.gesture.keyboard_state()

    def preview_target_state(self) -> PromptReorderPreviewTargetState:
        """Return display-only preview target state for focused tests."""

        return reorder_preview_target_state(
            self._runtime.geometry.state,
            dragged_segment_index=self._runtime.gesture.state.dragged_segment_index,
            active_target=self._runtime.gesture.state.active_drop_target,
        )

    def geometry_generation_state(self) -> PromptReorderGeometryGenerationState:
        """Return prepared geometry generation state without QWidget references."""

        return reorder_geometry_generation_state(
            self._runtime.geometry.state,
            generation_id=self._runtime.interaction_metrics.work_unit_id,
            dragged_segment_index=self._runtime.gesture.state.dragged_segment_index,
            active_target=self._runtime.gesture.state.active_drop_target,
            viewport_identity=self._runtime.viewport_geometry.position_geometry_key(),
        )

    def preview_chip_indices(self) -> list[int]:
        """Return previewed chip indices in the current visible reorder order."""

        if not self._runtime.visual_mode.preview_active():
            return []
        return [
            segment_index
            for segment_index in self.ordered_chip_indices()
            if segment_index in self._runtime.preview_visuals.visuals_by_index
        ]

    def preview_rect_for_segment(self, segment_index: int) -> QRect | None:
        """Return one preview rect when the supplied segment is visibly previewed."""

        preview_visual = self._runtime.preview_visuals.visuals_by_index.get(
            segment_index
        )
        if preview_visual is None:
            return None
        return QRect(preview_visual.hotspot_rect)

    def has_valid_initial_landing_shadow(self) -> bool:
        """Return whether the active drag has a chip-shaped landing shadow."""

        result = self._runtime.landing_resolution.has_valid_initial_landing_shadow(
            self._runtime.landing_request.build()
        )
        self._runtime.geometry.set_active_placement(result.active_placement)
        return result.geometry is not None

    def drag_proxy_widget(self) -> QWidget:
        """Return the floating drag proxy widget used for segment dragging."""

        return self._runtime.drag_proxy.widget

    def has_reordered(self) -> bool:
        """Return whether the current prospective order differs from the original."""

        return self._runtime.visual_mode.has_reordered()

    def set_hovered_segment(self, segment_index: int | None) -> None:
        """Track the segment currently under the pointer and repaint states."""

        changed = self._runtime.gesture.set_hovered_segment(segment_index)
        if not changed:
            return
        self._runtime.pointer_region_visuals.sync_interaction_state()
        self._runtime.render.sync(reason="hovered_segment_changed")

    def activate_segment(self, segment_index: int) -> None:
        """Track the segment that should retain selection if a commit happens."""

        self._runtime.gesture.activate_segment(segment_index)
        self._runtime.pointer_region_visuals.sync_interaction_state()
        self._runtime.render.sync(reason="active_segment_changed")

    def set_pointer_cursor(self, cursor_shape: Qt.CursorShape) -> None:
        """Apply the cursor selected by the overlay's logical pointer owner."""

        if self.cursor().shape() != cursor_shape:
            self.setCursor(cursor_shape)

    def pointer_region_rects(self) -> dict[int, QRect]:
        """Return visible overlay-local chip regions for harness interaction."""

        return {
            segment_index: QRect(region.rect)
            for segment_index, region in self._runtime.pointer_regions.regions_by_index.items()
            if region.visible
        }

    def pointer_region(self, segment_index: int) -> PromptReorderPointerRegion:
        """Return one logical chip region for focused diagnostics."""

        region = self._runtime.pointer_regions.regions_by_index.get(segment_index)
        if region is None or not region.visible:
            raise KeyError(segment_index)
        return region

    def set_pressed_segment(self, segment_index: int | None) -> None:
        """Track which segment pointer press is currently held down."""

        self._runtime.gesture.set_pressed_segment(segment_index)
        self._runtime.pointer_region_visuals.sync_interaction_state()

    def emit_preview_layout_changed(self) -> None:
        """Notify listeners that the reorder preview layout contract changed."""

        self.previewLayoutChanged.emit()
