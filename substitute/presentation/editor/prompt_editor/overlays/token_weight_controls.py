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

"""Render prompt token weight controls and relay their gesture intent."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal, Protocol, cast

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QCursor,
    QEnterEvent,
    QMouseEvent,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from ..core.state.semantic_state import PromptEditorSemanticSnapshot
from .token_weight_geometry import (
    PromptTokenWeightControlGeometry,
    PromptTokenWeightGeometry,
    PromptTokenWeightGeometrySnapshot,
)
from .token_weight_exact_edit import PromptTokenWeightExactEditController
from .token_weight_actions import PromptTokenWeightActionCoordinator
from .token_weight_gestures import (
    PromptTokenWeightGestureController,
    PromptTokenWeightStepIntent,
    PromptTokenWeightWheelStepIntent,
)
from .token_weight_input_router import PromptTokenWeightInputRouter
from .token_weight_view import (
    PromptTokenWeightControlPaintState,
    PromptTokenWeightPreviewPaintState,
    PromptTokenWeightView,
    PromptTokenWeightViewRenderState,
)
from .token_weight_preview import PromptTokenWeightPreviewController
from .token_weight_wheel_intent import PromptTokenWeightWheelIntentRouter


type _TokenControlGeometry = PromptTokenWeightControlGeometry


class _ProjectionSnapshotLike(Protocol):
    """Describe the prepared projection snapshot consumed by token controls."""

    @property
    def display_mode(self) -> PromptProjectionDisplayMode:
        """Return whether the current projection is raw or projected."""
        ...

    @property
    def tokens(self) -> Sequence[PromptProjectionToken]:
        """Return the prepared projection tokens available to overlays."""
        ...


class PromptTokenWeightControlsSurface(Protocol):
    """Describe the projection-surface API required by the controls overlay."""

    def viewport(self) -> QWidget:
        """Return the visible viewport used for pointer ownership."""

    def parentWidget(self) -> QWidget | None:
        """Return the immediate editor parent when no window host exists."""

    def window(self) -> QWidget:
        """Return the top-level host window used for non-clipping controls."""

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the projected token painted under one viewport-local point."""

    def enclosing_emphasis_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return emphasis containing visible text without a token-specific run."""

    def projection_document(self) -> _ProjectionSnapshotLike:
        """Return the current token-aware projection document."""

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local anchor rect for one token."""

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local painted weight rect for one weighted token."""


class PromptTokenWeightViewFactory(Protocol):
    """Create the passive token-weight view for one overlay instance."""

    def __call__(
        self,
        parent: QWidget,
        *,
        surface_widget: QWidget,
    ) -> PromptTokenWeightView:
        """Return the view parented to the supplied overlay widget."""


class PromptTokenWeightGestureControllerFactory(Protocol):
    """Create the token-weight gesture owner for one overlay instance."""

    def __call__(self, parent: QObject) -> PromptTokenWeightGestureController:
        """Return the gesture controller parented to the supplied overlay widget."""


class PromptTokenWeightExactEditControllerFactory(Protocol):
    """Create exact-edit coordination around one overlay gesture owner."""

    def __call__(
        self,
        gestures: PromptTokenWeightGestureController,
    ) -> PromptTokenWeightExactEditController:
        """Return the exact-edit controller bound to the supplied gestures."""


class PromptTokenWeightActionCoordinatorFactory(Protocol):
    """Create command-to-feedback coordination for one mounted overlay."""

    def __call__(
        self,
        host: PromptTokenWeightControls,
        *,
        gestures: PromptTokenWeightGestureController,
        emit_control_step: Callable[[PromptTokenWeightStepIntent], None],
        emit_wheel_step: Callable[[PromptTokenWeightWheelStepIntent], None],
    ) -> PromptTokenWeightActionCoordinator:
        """Return the action coordinator bound to the supplied owners."""


class PromptTokenWeightInputRouterFactory(Protocol):
    """Create Qt input routing around one mounted control overlay."""

    def __call__(
        self,
        host: PromptTokenWeightControls,
        *,
        overlay: QWidget,
        surface_widget: QWidget,
        viewport: QWidget,
        gestures: PromptTokenWeightGestureController,
        exact_edit: PromptTokenWeightExactEditController,
        actions: PromptTokenWeightActionCoordinator,
        wheel_intent: PromptTokenWeightWheelIntentRouter,
    ) -> PromptTokenWeightInputRouter:
        """Return the input router bound to the supplied mounted owners."""


class PromptTokenWeightControls(QWidget):
    """Render token weight controls above the custom prompt projection surface."""

    tokenWeightStepTriggered = Signal(object)
    tokenWeightWheelStepTriggered = Signal(object)
    visibleTokenRangeChanged = Signal(object)
    visibleTokenContentRangeChanged = Signal(object)

    CONTROL_WIDTH = 13.0
    CONTROL_HEIGHT = 10.0
    CONTROL_GAP = 0.5
    CONTROL_MARGIN = 4.0
    OVERLAY_PADDING = 2.0
    HIDE_DELAY_MS = 140

    def __init__(
        self,
        surface: PromptTokenWeightControlsSurface,
        *,
        host: QWidget,
        geometry: PromptTokenWeightGeometry,
        view_factory: PromptTokenWeightViewFactory,
        gesture_controller_factory: PromptTokenWeightGestureControllerFactory,
        exact_edit_controller_factory: PromptTokenWeightExactEditControllerFactory,
        action_coordinator_factory: PromptTokenWeightActionCoordinatorFactory,
        input_router_factory: PromptTokenWeightInputRouterFactory,
        preview_controller: PromptTokenWeightPreviewController,
        wheel_intent_router: PromptTokenWeightWheelIntentRouter,
    ) -> None:
        """Create the non-clipping overlay used for token-adjacent controls."""

        self._surface = surface
        self._surface_widget = cast(QWidget, surface)
        self._host = host
        super().__init__(self._host)
        self._geometry = geometry
        self._geometry_snapshot = PromptTokenWeightGeometrySnapshot()
        self._view = view_factory(self, surface_widget=self._surface_widget)
        self._gestures = gesture_controller_factory(self)
        self._exact_edit = exact_edit_controller_factory(self._gestures)
        self._preview_controller = preview_controller
        self._gestures.hide_timeout.timeout.connect(self._handle_hide_timeout)
        self._gestures.preview_timeout.timeout.connect(self.clear_weight_preview)
        self._wheel_intent = wheel_intent_router
        self._actions = action_coordinator_factory(
            self,
            gestures=self._gestures,
            emit_control_step=self.tokenWeightStepTriggered.emit,
            emit_wheel_step=self.tokenWeightWheelStepTriggered.emit,
        )
        self._visible_token: PromptProjectionToken | None = None
        self._increase_rect: QRectF | None = None
        self._decrease_rect: QRectF | None = None
        self._weight_hit_rect: QRectF | None = None

        viewport = self._surface.viewport()
        self._input_router = input_router_factory(
            self,
            overlay=self,
            surface_widget=self._surface_widget,
            viewport=viewport,
            gestures=self._gestures,
            exact_edit=self._exact_edit,
            actions=self._actions,
            wheel_intent=self._wheel_intent,
        )
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)
        self._surface_widget.installEventFilter(self)
        if host is not self._surface_widget:
            host.installEventFilter(self)
        focus_owner = self._surface.parentWidget()
        if focus_owner is not None and focus_owner is not self._surface_widget:
            focus_owner.installEventFilter(self)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._view.setGeometry(self.rect())
        self._sync_view_render_state()
        self.hide()

    def refresh_geometry(self) -> None:
        """Recompute control visibility from the current hover activation zone."""

        if not self._runtime_widgets_are_valid():
            return
        if self._surface.projection_document().display_mode.value == "raw":
            self._geometry_snapshot = PromptTokenWeightGeometrySnapshot()
            self._gestures.stop_hide_linger()
            self._hide_controls()
            return
        if self._controls_are_dormant():
            self._geometry_snapshot = PromptTokenWeightGeometrySnapshot()
            self._hide_controls()
            return
        self._refresh_geometry_snapshot()
        if self._exact_edit.active:
            self._gestures.stop_hide_linger()
            self.clear_weight_preview()
            token = self._exact_edit.token
            if token is None:
                self._cancel_exact_weight_edit()
                return
            self._set_visible_token(token)
            self._increase_rect = None
            self._decrease_rect = None
            self._weight_hit_rect = None
            self._refresh_overlay_bounds()
            return

        keep_hide_linger = False
        self._refresh_pointer_from_action_position_if_needed()
        geometry = self.interaction_geometry_at_pointer()
        if geometry is None and self._gestures.pressed_control is not None:
            geometry = self.geometry_for_visible_token()
        if geometry is None and self._gestures.hide_timeout.isActive():
            geometry = self.geometry_for_visible_token()
            keep_hide_linger = True

        if geometry is None and self._gestures.action_in_progress:
            return

        if geometry is None:
            if (
                self._visible_token is not None
                and self._gestures.pointer_host_position is not None
            ):
                self.start_hide_linger()
                geometry = self.geometry_for_visible_token()
                keep_hide_linger = True
            else:
                self._hide_controls()
                return

        if geometry is None:
            self._hide_controls()
            return

        if not keep_hide_linger:
            self._gestures.stop_hide_linger()
        self.apply_geometry(geometry)

    def _controls_are_dormant(self) -> bool:
        """Return whether no interaction state can consume prepared geometry."""

        return (
            not self._exact_edit.active
            and self._gestures.pointer_host_position is None
            and self._visible_token is None
            and self._gestures.pressed_control is None
            and not self._gestures.action_in_progress
            and not self._gestures.hide_timeout.isActive()
        )

    def _refresh_geometry_snapshot(self) -> None:
        """Publish the latest prepared token-control geometry snapshot."""

        self._geometry_snapshot = self._geometry.build_snapshot()

    def apply_geometry(self, geometry: _TokenControlGeometry) -> None:
        """Apply one host-local geometry snapshot to the visible control overlay."""

        self._set_visible_token(geometry.token)
        self._increase_rect = geometry.increase_rect
        self._decrease_rect = geometry.decrease_rect
        self._weight_hit_rect = geometry.weight_text_rect
        pointer_position = self._gestures.pointer_host_position
        self._wheel_intent.refresh_candidate(
            geometry.token,
            None
            if pointer_position is None
            else self._global_position_from_host_position(pointer_position),
        )
        self._refresh_overlay_bounds()

    def _hide_controls(self) -> None:
        """Hide the overlay and clear any non-pressed visibility state."""

        self._set_visible_token(None)
        if self._weighted_token_at_current_pointer() is None:
            self._exact_edit.clear_overlay_emphasis_session()
            self._wheel_intent.clear()
        self._increase_rect = None
        self._decrease_rect = None
        self._weight_hit_rect = None
        if self._gestures.pressed_control is None:
            self._gestures.hovered_control = None
            self.unsetCursor()
        self._refresh_overlay_bounds()

    def _set_visible_token(self, token: PromptProjectionToken | None) -> None:
        """Persist the visible token and publish range changes for paren accenting."""

        previous_range = self._outer_range_for_token(self._visible_token)
        previous_content_range = self._content_range_for_token(self._visible_token)
        next_range = self._outer_range_for_token(token)
        next_content_range = self._content_range_for_token(token)
        self._visible_token = token
        if previous_range != next_range:
            self.visibleTokenRangeChanged.emit(next_range)
        if previous_content_range != next_content_range:
            self.visibleTokenContentRangeChanged.emit(next_content_range)

    @staticmethod
    def _outer_range_for_token(
        token: PromptProjectionToken | None,
    ) -> tuple[int, int] | None:
        """Return one token outer range or ``None`` when no token is visible."""

        if token is None:
            return None
        return (token.source_start, token.source_end)

    @staticmethod
    def _content_range_for_token(
        token: PromptProjectionToken | None,
    ) -> tuple[int, int] | None:
        """Return one token content range or ``None`` when the token has none."""

        if token is None:
            return None
        return token.content_range

    @property
    def visible_token(self) -> PromptProjectionToken | None:
        """Return the weighted token currently owning visible controls."""

        token = self._visible_token
        if token is None:
            return None
        resolved_token = self._current_projection_token_for(token)
        if resolved_token is not None:
            self._visible_token = resolved_token
            return resolved_token
        return token

    @property
    def increase_rect(self) -> QRectF | None:
        """Return the host-local rect for the visible increase control."""

        return self._increase_rect

    @property
    def decrease_rect(self) -> QRectF | None:
        """Return the host-local rect for the visible decrease control."""

        return self._decrease_rect

    def set_prompt_state(
        self,
        snapshot: PromptEditorSemanticSnapshot,
    ) -> None:
        """Refresh controls after the prompt snapshot changes."""

        _ = snapshot
        self.refresh_geometry()

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Refresh controls after the active syntax span changes."""

        _ = (active_span, cursor_position)
        self.refresh_geometry()

    def hit_test_action(self, position: object) -> Any | None:
        """Return no viewport-local syntax action because controls live off-viewport."""

        _ = position
        return None

    def clear_transient_state(self) -> None:
        """Clear transient hover ownership and let controls hide normally."""

        if not self._runtime_widgets_are_valid():
            return
        self._cancel_exact_weight_edit()
        self._input_router.cancel_hold()
        self._gestures.clear_transient_state()
        self._wheel_intent.clear()
        self.unsetCursor()
        self.refresh_geometry()

    def begin_exact_weight_edit_at_position(self, position: QPointF) -> bool:
        """Start exact weight editing when one viewport-local point hits a painted number."""

        return self._input_router.begin_exact_edit_at_position(position)

    def handle_exact_weight_click(self, position: QPointF) -> bool:
        """Advance the number-only click recognizer for one surface or overlay click."""

        return self._input_router.handle_exact_weight_click(position)

    def handle_host_wheel_event(self, event: QWheelEvent) -> bool:
        """Handle one wheel event delivered through the prompt host viewport."""

        if not self._runtime_widgets_are_valid():
            return False
        return self._input_router.handle_host_wheel_event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Track pointer ownership from the surface viewport."""

        if not self._runtime_widgets_are_valid():
            return False
        handled = self._input_router.filter_event(watched, event)
        if handled is not None:
            return handled
        return super().eventFilter(watched, event)

    def _runtime_widgets_are_valid(self) -> bool:
        """Return whether overlay mapping targets are still backed by Qt objects."""

        try:
            viewport = self._surface.viewport()
        except RuntimeError:
            return False
        return (
            _qt_object_is_valid(self)
            and _qt_object_is_valid(self._surface_widget)
            and _qt_object_is_valid(self._host)
            and _qt_object_is_valid(viewport)
        )

    def host_point_from_global(self, global_position: QPointF) -> QPointF | None:
        """Map one global point to the host when the host is still alive."""

        if not _qt_object_is_valid(self._host):
            return None
        return self._geometry.host_point_from_global(global_position)

    def _host_rect(self) -> QRectF:
        """Return the host rect, or an empty rect if the host is tearing down."""

        if not _qt_object_is_valid(self._host):
            return QRectF()
        return self._geometry.host_rect()

    def enterEvent(self, event: QEnterEvent) -> None:
        """Track hover ownership once the pointer enters the overlay itself."""

        self._input_router.enter(event)
        super().enterEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Refresh hovered control ownership while the pointer moves."""

        self._input_router.move(event)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Release overlay hover ownership once the pointer leaves the control host."""

        self._input_router.leave()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Capture one pressed control without interfering with text selection."""

        self._input_router.press(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Start exact edit only from an unambiguous weight double click."""

        self._input_router.double_click(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit one typed emphasis action when the same control is released."""

        self._input_router.release(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Adjust emphasis when the wheel is used over visible controls."""

        self._input_router.wheel(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the passive child view aligned with overlay bounds."""

        self._view.setGeometry(self.rect())
        self._sync_view_render_state()
        super().resizeEvent(event)

    def weighted_token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the weighted token painted under one viewport-local point."""

        return self._geometry.weighted_token_at_viewport_position(position)

    def _weighted_token_at_current_pointer(self) -> PromptProjectionToken | None:
        """Return the weighted token under the stored pointer position, if any."""

        pointer_position = self._gestures.pointer_host_position
        if pointer_position is None:
            return None
        global_position = self._global_position_from_host_position(pointer_position)
        viewport_position = QPointF(
            self._surface.viewport().mapFromGlobal(global_position.toPoint())
        )
        return self.weighted_token_at_viewport_position(viewport_position)

    def _weight_token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the weighted token whose painted number contains one viewport point."""

        self._refresh_geometry_snapshot()
        return self._geometry_snapshot.token_at_weight_viewport_position(position)

    def token_at_weight_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the weighted token whose painted number owns one surface or viewport point."""

        token = self._weight_token_at_viewport_position(position)
        if token is not None:
            return token
        return self._weight_token_at_viewport_position(
            QPointF(
                self._surface.viewport().mapFrom(
                    self._surface_widget,
                    position.toPoint(),
                )
            )
        )

    def _weight_rect_for_token_host_local(
        self,
        token: PromptProjectionToken,
    ) -> QRectF | None:
        """Return the host-local painted number rect for one weighted token."""

        if not self._runtime_widgets_are_valid():
            return None
        geometry = self._geometry.geometry_for_token(token)
        if geometry is None:
            return None
        return geometry.weight_text_rect

    def _cancel_exact_weight_edit(self) -> None:
        """Exit exact edit mode without mutating prompt text."""

        if self._exact_edit.cancel():
            self.refresh_geometry()

    def set_pointer_from_viewport(self, viewport_position: QPointF) -> None:
        """Store the current pointer position in host coordinates from the viewport."""

        if not self._runtime_widgets_are_valid():
            self._gestures.pointer_host_position = None
            return
        host_point = self._geometry.host_point_from_viewport_position(viewport_position)
        self._gestures.pointer_host_position = (
            QPointF(host_point) if host_point is not None else None
        )

    def set_pointer_from_overlay(self, overlay_position: QPointF) -> None:
        """Store the current pointer position in host coordinates from the overlay."""

        self._gestures.pointer_host_position = QPointF(
            self.mapToParent(overlay_position.toPoint())
        )

    def set_pointer_from_global(self, global_position: QPointF) -> None:
        """Store the current pointer position in host coordinates from one global point."""

        host_point = self.host_point_from_global(global_position)
        self._gestures.pointer_host_position = (
            QPointF(host_point) if host_point is not None else None
        )

    def _refresh_pointer_from_action_position_if_needed(self) -> None:
        """Re-sample pointer ownership from the real cursor during control-driven geometry churn."""

        if not self._runtime_widgets_are_valid():
            self._gestures.pointer_host_position = None
            return
        action_position = self._gestures.action_pointer_global_position
        if action_position is None:
            return
        global_position = action_position
        if not self._gestures.action_in_progress:
            global_position = QPointF(QCursor.pos())
        self.set_pointer_from_global(global_position)

    def start_hide_linger(self) -> None:
        """Delay hiding briefly so pointer travel into the controls stays stable."""

        self._gestures.start_hide_linger(visible_token=self._visible_token)

    def _handle_hide_timeout(self) -> None:
        """Hide controls after the pointer has remained outside the activation zone."""

        if self._gestures.pressed_control is not None:
            return
        geometry = self.interaction_geometry_at_pointer()
        if geometry is None:
            self._hide_controls()
            return
        self.apply_geometry(geometry)

    def geometry_for_visible_token(self) -> _TokenControlGeometry | None:
        """Return fresh geometry for the token currently owning visible controls."""

        if self._visible_token is None:
            return None
        return self._geometry_for_token(self._visible_token)

    def interaction_geometry_at_pointer(self) -> _TokenControlGeometry | None:
        """Return the weighted token whose activation zone contains the pointer."""

        return self._geometry_snapshot.geometry_at_pointer(
            self._gestures.pointer_host_position
        )

    def record_wheel_intent_pointer_from_viewport(
        self,
        event: QMouseEvent,
    ) -> None:
        """Record token hover intent from one real viewport pointer move."""

        token = self.weighted_token_at_viewport_position(event.position())
        fallback_token: PromptProjectionToken | None = None
        if token is None:
            self.set_pointer_from_viewport(event.position())
            geometry = self.interaction_geometry_at_pointer()
            if geometry is not None:
                fallback_token = geometry.token
        self._wheel_intent.record_pointer_move(
            token,
            fallback_token=fallback_token,
            global_position=event.globalPosition(),
        )

    def _global_position_from_host_position(
        self,
        host_position: QPointF,
    ) -> QPointF:
        """Map one host-local position into global coordinates."""

        if not _qt_object_is_valid(self._host):
            return QPointF()
        return self._geometry.global_position_from_host_position(host_position)

    def _geometry_for_token(
        self,
        token: PromptProjectionToken,
    ) -> _TokenControlGeometry | None:
        """Return host-local anchor and control rects for one weighted token."""

        if not self._runtime_widgets_are_valid():
            return None
        geometry = self._geometry_snapshot.geometry_for_token(token)
        if geometry is not None:
            return geometry
        return self._geometry.geometry_for_token(token)

    def update_hovered_control(self, local_position: QPointF) -> None:
        """Refresh the hovered control based on one overlay-local pointer position."""

        next_control = self.control_at_local_position(local_position)
        if next_control == self._gestures.hovered_control:
            return
        self._gestures.hovered_control = next_control
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if next_control
            else Qt.CursorShape.ArrowCursor
        )
        self.update()

    def control_at_local_position(
        self,
        local_position: QPointF,
    ) -> Literal["increase", "decrease"] | None:
        """Return the visible control currently under one overlay-local point."""

        if self._increase_rect is not None and self._host_rect_to_local_rect(
            self._increase_rect
        ).contains(local_position):
            return "increase"
        if self._decrease_rect is not None and self._host_rect_to_local_rect(
            self._decrease_rect
        ).contains(local_position):
            return "decrease"
        return None

    def mouse_target_at_local_position(
        self,
        local_position: QPointF,
    ) -> Literal["increase", "decrease", "weight"] | None:
        """Classify one overlay-local point so ambiguous hits never resolve to exact edit."""

        control = self.control_at_local_position(local_position)
        if control is not None:
            return control
        if self._local_position_hits_weight(local_position):
            return "weight"
        return None

    def _local_position_hits_weight(self, local_position: QPointF) -> bool:
        """Return whether one overlay-local point hits the painted weight slot."""

        return self._weight_hit_rect is not None and self._host_rect_to_local_rect(
            self._weight_hit_rect
        ).contains(local_position)

    def _host_rect_to_local_rect(self, host_rect: QRectF) -> QRectF:
        """Return one host-local control rect translated into overlay-local coordinates."""

        top_left = self.mapFromParent(host_rect.topLeft().toPoint())
        return QRectF(QPointF(top_left), host_rect.size())

    def resolve_post_action_preview_token(
        self,
        source_token: PromptProjectionToken,
    ) -> PromptProjectionToken | None:
        """Resolve the current token that should own mutation feedback."""

        return self._preview_controller.resolve_post_action_token(
            source_token,
            visible_token=self._visible_token,
            geometry_snapshot=self._geometry_snapshot,
        )

    def show_weight_preview_for_token(
        self,
        token: PromptProjectionToken | None,
        *,
        pointer_global_position: QPointF,
    ) -> None:
        """Show a short-lived weight label above the current mouse pointer."""

        if not self._runtime_widgets_are_valid():
            self.clear_weight_preview()
            return
        host_point = self.host_point_from_global(pointer_global_position)
        preview = self._preview_controller.prepare(
            token,
            pointer_host_position=host_point,
            host_rect=self._host_rect(),
            base_font=self.font(),
        )
        if preview is None:
            self.clear_weight_preview()
            return
        self._gestures.show_weight_preview(text=preview.text, rect=preview.rect)
        self._refresh_overlay_bounds()

    def host_point_supports_weight_preview(
        self,
        *,
        host_point: QPointF,
        geometry: _TokenControlGeometry,
    ) -> bool:
        """Return whether the pointer is over the number or the up control."""

        return geometry.anchor_rect.contains(
            host_point
        ) or geometry.increase_rect.contains(host_point)

    def _current_projection_token_for(
        self,
        source_token: PromptProjectionToken,
    ) -> PromptProjectionToken | None:
        """Return the current projection token matching one cached weighted token."""

        return self._geometry_snapshot.current_token_for(source_token)

    def clear_weight_preview(self) -> None:
        """Remove any visible pointer-owned weight preview bubble."""

        if not self._gestures.clear_weight_preview():
            return
        self._refresh_overlay_bounds()

    def _refresh_overlay_bounds(self) -> None:
        """Resize the overlay to cover visible controls and any pointer-owned preview."""

        if not _qt_object_is_valid(self):
            return
        bounds = self._geometry.overlay_bounds(
            (
                self._increase_rect,
                self._decrease_rect,
                self._weight_hit_rect,
                self._gestures.weight_preview_rect,
            )
        )
        if bounds is None:
            self.hide()
            self._sync_view_render_state()
            return
        self.setGeometry(bounds.toAlignedRect())
        self._view.setGeometry(self.rect())
        self._sync_view_render_state()
        self.show()
        self.raise_()
        self._view.raise_()

    def _sync_view_render_state(self) -> None:
        """Publish prepared local paint rects to the passive token-weight view."""

        controls_state: PromptTokenWeightControlPaintState | None = None
        if self._increase_rect is not None or self._decrease_rect is not None:
            controls_state = PromptTokenWeightControlPaintState(
                increase_rect=(
                    None
                    if self._increase_rect is None
                    else self._host_rect_to_local_rect(self._increase_rect)
                ),
                decrease_rect=(
                    None
                    if self._decrease_rect is None
                    else self._host_rect_to_local_rect(self._decrease_rect)
                ),
                hovered_control=self._gestures.hovered_control,
                pressed_control=self._gestures.pressed_control,
            )
        preview_state: PromptTokenWeightPreviewPaintState | None = None
        if (
            self._gestures.weight_preview_rect is not None
            and self._gestures.weight_preview_text is not None
        ):
            preview_state = PromptTokenWeightPreviewPaintState(
                text=self._gestures.weight_preview_text,
                rect=self._host_rect_to_local_rect(self._gestures.weight_preview_rect),
            )
        self._view.set_render_state(
            PromptTokenWeightViewRenderState(
                controls=controls_state,
                preview=preview_state,
            )
        )


def _qt_object_is_valid(candidate: object | None) -> bool:
    """Return whether a Python Qt wrapper still has a live C++ object."""

    if candidate is None:
        return False
    try:
        return bool(isValid(cast(QObject, candidate)))
    except (RuntimeError, TypeError):
        return False


__all__ = [
    "PromptTokenWeightControls",
    "PromptTokenWeightControlsSurface",
    "PromptTokenWeightGestureControllerFactory",
    "PromptTokenWeightViewFactory",
]
