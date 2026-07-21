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
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QMouseEvent,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptSyntaxSpanView,
)

from ..projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from ..projection.tokens import emphasis_weight_font
from .token_weight_geometry import (
    PromptTokenWeightControlGeometry,
    PromptTokenWeightGeometry,
    PromptTokenWeightGeometrySnapshot,
    tokens_share_content_range,
)
from .token_weight_gestures import (
    PromptTokenWeightControl,
    PromptTokenWeightGestureController,
    PromptTokenWeightStepIntent,
    PromptTokenWeightWheelStepIntent,
)
from .token_weight_view import (
    PromptTokenWeightControlPaintState,
    PromptTokenWeightPreviewPaintState,
    PromptTokenWeightView,
    PromptTokenWeightViewRenderState,
)


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

    def projection_document(self) -> _ProjectionSnapshotLike:
        """Return the current token-aware projection document."""

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local anchor rect for one token."""

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local painted weight rect for one weighted token."""

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start one projection-owned exact weight edit session."""

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update the active projection-owned exact weight edit state."""

    def clear_exact_weight_edit(self) -> None:
        """Clear any active projection-owned exact weight edit session."""

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the projection token currently owning exact edit mode."""

    def exact_weight_edit_active(self) -> bool:
        """Return whether exact weight edit mode is currently active."""


class PromptTokenWeightExactEditHost(Protocol):
    """Coordinate projection-owned exact edit lifecycle for token controls."""

    def begin_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start one projection-owned exact weight edit session."""

    def cancel_exact_weight_edit(self) -> None:
        """Cancel any active projection-owned exact weight edit session."""

    def finalize_exact_weight_edit(self) -> None:
        """Commit or cancel the active exact weight edit session."""

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the projection token currently owning exact edit mode."""

    def exact_weight_edit_active(self) -> bool:
        """Return whether exact weight edit mode is currently active."""

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local painted weight rect for one weighted token."""

    def update_exact_weight_caret(
        self,
        *,
        token: PromptProjectionToken,
        caret_index: int,
    ) -> None:
        """Move the active exact-weight edit caret."""

    def handle_exact_weight_key_press(self, event: QKeyEvent) -> bool:
        """Handle one exact-weight edit key press."""

    def clear_overlay_emphasis_session_for_exact_weight(self) -> None:
        """Clear overlay-owned emphasis state after controls lose ownership."""


class PromptTokenWeightWheelIntentOwner(Protocol):
    """Own token-weight wheel dwell, activation, and accent publication."""

    def record_token_pointer_move(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record pointer movement over one numeric token."""

    def activate_token(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record explicit token activation for focus-required wheel mode."""

    def token_wheel_is_allowed(
        self,
        token: PromptProjectionToken,
        event: QWheelEvent,
    ) -> bool:
        """Return whether one token may consume wheel input."""

    def refresh_candidate_from_pointer(
        self,
        candidate: tuple[PromptProjectionToken, QPointF] | None,
    ) -> None:
        """Refresh dwell accent state from the current pointer candidate."""

    def clear_candidate(self) -> None:
        """Clear token-wheel dwell and accent state."""


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
    WEIGHT_PREVIEW_MS = 240
    _WEIGHT_PREVIEW_CURSOR_OFFSET = 4.0
    _WEIGHT_PREVIEW_MARGIN = 6.0
    _WEIGHT_PREVIEW_HORIZONTAL_PADDING = 3.5
    _WEIGHT_PREVIEW_VERTICAL_PADDING = 1.0

    def __init__(
        self,
        surface: PromptTokenWeightControlsSurface,
        *,
        host: QWidget,
        geometry: PromptTokenWeightGeometry,
        view_factory: PromptTokenWeightViewFactory,
        gesture_controller_factory: PromptTokenWeightGestureControllerFactory,
        exact_edit_host: PromptTokenWeightExactEditHost,
        wheel_intent_owner: PromptTokenWeightWheelIntentOwner,
    ) -> None:
        """Create the non-clipping overlay used for token-adjacent controls."""

        self._surface = surface
        self._exact_edit_host = exact_edit_host
        self._surface_widget = cast(QWidget, surface)
        self._host = host
        super().__init__(self._host)
        self._geometry = geometry
        self._geometry_snapshot = PromptTokenWeightGeometrySnapshot()
        self._view = view_factory(self, surface_widget=self._surface_widget)
        self._gestures = gesture_controller_factory(self)
        self._gestures.hide_timeout.timeout.connect(self._handle_hide_timeout)
        self._gestures.preview_timeout.timeout.connect(self._clear_weight_preview)
        self._wheel_intent_owner = wheel_intent_owner
        self._visible_token: PromptProjectionToken | None = None
        self._increase_rect: QRectF | None = None
        self._decrease_rect: QRectF | None = None
        self._weight_hit_rect: QRectF | None = None

        viewport = self._surface.viewport()
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)
        self._surface_widget.installEventFilter(self)
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
        if self._exact_edit_host.exact_weight_edit_active():
            self._gestures.stop_hide_linger()
            self._clear_weight_preview()
            token = self._exact_edit_host.exact_weight_edit_token()
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
        geometry = self._interaction_geometry_at_pointer()
        if geometry is None and self._gestures.pressed_control is not None:
            geometry = self._geometry_for_visible_token()
        if geometry is None and self._gestures.hide_timeout.isActive():
            geometry = self._geometry_for_visible_token()
            keep_hide_linger = True

        if geometry is None and self._gestures.action_in_progress:
            return

        if geometry is None:
            if (
                self._visible_token is not None
                and self._gestures.pointer_host_position is not None
            ):
                self._start_hide_timer()
                geometry = self._geometry_for_visible_token()
                keep_hide_linger = True
            else:
                self._hide_controls()
                return

        if geometry is None:
            self._hide_controls()
            return

        if not keep_hide_linger:
            self._gestures.stop_hide_linger()
        self._apply_geometry(geometry)

    def _controls_are_dormant(self) -> bool:
        """Return whether no interaction state can consume prepared geometry."""

        return (
            not self._exact_edit_host.exact_weight_edit_active()
            and self._gestures.pointer_host_position is None
            and self._visible_token is None
            and self._gestures.pressed_control is None
            and not self._gestures.action_in_progress
            and not self._gestures.hide_timeout.isActive()
        )

    def _refresh_geometry_snapshot(self) -> None:
        """Publish the latest prepared token-control geometry snapshot."""

        self._geometry_snapshot = self._geometry.build_snapshot()

    def _apply_geometry(self, geometry: _TokenControlGeometry) -> None:
        """Apply one host-local geometry snapshot to the visible control overlay."""

        self._set_visible_token(geometry.token)
        self._increase_rect = geometry.increase_rect
        self._decrease_rect = geometry.decrease_rect
        self._weight_hit_rect = geometry.weight_text_rect
        self._refresh_wheel_intent_candidate_for_geometry(geometry)
        self._refresh_overlay_bounds()

    def _hide_controls(self) -> None:
        """Hide the overlay and clear any non-pressed visibility state."""

        self._set_visible_token(None)
        self._exact_edit_host.clear_overlay_emphasis_session_for_exact_weight()
        if self._weighted_token_at_current_pointer() is None:
            self._clear_wheel_intent_candidate()
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
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Refresh controls after the prompt snapshot changes."""

        _ = (document_view, render_plan)
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
        self._gestures.clear_transient_state()
        self._clear_wheel_intent_candidate()
        self.unsetCursor()
        self.refresh_geometry()

    def begin_exact_weight_edit_at_position(self, position: QPointF) -> bool:
        """Start exact weight editing when one viewport-local point hits a painted number."""

        token = self._weight_token_at_surface_or_viewport_position(position)
        if token is None or token.kind is PromptProjectionTokenKind.WILDCARD:
            return False
        self._start_exact_weight_edit(token)
        return True

    def handle_exact_weight_click(self, position: QPointF) -> bool:
        """Advance the number-only click recognizer for one surface or overlay click."""

        return self._maybe_begin_exact_weight_edit_from_click(position)

    def handle_host_wheel_event(self, event: QWheelEvent) -> bool:
        """Handle one wheel event delivered through the prompt host viewport."""

        if not self._runtime_widgets_are_valid():
            return False
        if self._exact_edit_host.exact_weight_edit_active():
            event.accept()
            return True
        viewport_position = QPointF(
            self._surface.viewport().mapFromGlobal(event.globalPosition().toPoint())
        )
        if self._emit_viewport_wheel_action(event, viewport_position=viewport_position):
            event.accept()
            return True
        return False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Track pointer ownership from the surface viewport."""

        if not self._runtime_widgets_are_valid():
            return False
        if watched is self._surface.viewport():
            if self._exact_edit_host.exact_weight_edit_active():
                if event.type() == QEvent.Type.MouseButtonPress:
                    return self._handle_exact_edit_viewport_press(
                        cast(QMouseEvent, event)
                    )
                if event.type() == QEvent.Type.MouseButtonDblClick:
                    return self._handle_exact_edit_viewport_double_click(
                        cast(QMouseEvent, event)
                    )
                if event.type() == QEvent.Type.Wheel:
                    return True
            if event.type() == QEvent.Type.MouseMove:
                mouse_event = cast(QMouseEvent, event)
                self._set_pointer_from_viewport(mouse_event.position())
                self._record_wheel_intent_pointer_from_viewport(mouse_event)
                self.refresh_geometry()
            elif event.type() == QEvent.Type.MouseButtonPress:
                mouse_event = cast(QMouseEvent, event)
                if mouse_event.button() == Qt.MouseButton.LeftButton and (
                    token := self._weight_token_at_surface_or_viewport_position(
                        mouse_event.position()
                    )
                ):
                    self._activate_wheel_intent_token(
                        token,
                        mouse_event.globalPosition(),
                    )
                elif mouse_event.button() == Qt.MouseButton.LeftButton:
                    self._clear_exact_weight_click_candidate()
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                mouse_event = cast(QMouseEvent, event)
                if mouse_event.button() == Qt.MouseButton.LeftButton:
                    if self.begin_exact_weight_edit_at_position(mouse_event.position()):
                        mouse_event.accept()
                        return True
            elif event.type() == QEvent.Type.Wheel:
                wheel_event = cast(QWheelEvent, event)
                if self._emit_viewport_wheel_action(
                    wheel_event,
                    viewport_position=wheel_event.position(),
                ):
                    wheel_event.accept()
                    return True
            elif event.type() == QEvent.Type.Leave:
                if self._gestures.action_in_progress:
                    return super().eventFilter(watched, event)
                self._gestures.pointer_host_position = None
                self._start_hide_timer()
        if watched is self._surface_widget:
            if self._exact_edit_host.exact_weight_edit_active():
                if event.type() == QEvent.Type.MouseButtonPress:
                    return self._handle_exact_edit_viewport_press(
                        cast(QMouseEvent, event)
                    )
                if event.type() == QEvent.Type.MouseButtonDblClick:
                    return self._handle_exact_edit_viewport_double_click(
                        cast(QMouseEvent, event)
                    )
                if event.type() == QEvent.Type.Wheel:
                    return True
            if event.type() == QEvent.Type.MouseButtonDblClick:
                mouse_event = cast(QMouseEvent, event)
                if mouse_event.button() == Qt.MouseButton.LeftButton:
                    if self.begin_exact_weight_edit_at_position(mouse_event.position()):
                        mouse_event.accept()
                        return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                mouse_event = cast(QMouseEvent, event)
                if mouse_event.button() == Qt.MouseButton.LeftButton and (
                    token := self._weight_token_at_surface_or_viewport_position(
                        mouse_event.position()
                    )
                ):
                    self._activate_wheel_intent_token(
                        token,
                        mouse_event.globalPosition(),
                    )
                elif mouse_event.button() == Qt.MouseButton.LeftButton:
                    self._clear_exact_weight_click_candidate()
        if (
            watched is not self._surface.viewport()
            and self._exact_edit_host.exact_weight_edit_active()
            and event.type() == QEvent.Type.KeyPress
        ):
            return self._handle_exact_edit_key_press(cast(QKeyEvent, event))
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

    def _host_point_from_global(self, global_position: QPointF) -> QPointF | None:
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

        self._set_pointer_from_overlay(event.position())
        self._update_hovered_control(event.position())
        self.refresh_geometry()
        super().enterEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Refresh hovered control ownership while the pointer moves."""

        self._set_pointer_from_overlay(event.position())
        self._update_hovered_control(event.position())
        self.refresh_geometry()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Release overlay hover ownership once the pointer leaves the control host."""

        if self._gestures.action_in_progress:
            super().leaveEvent(event)
            return
        self._gestures.hovered_control = None
        self.unsetCursor()
        self._gestures.pointer_host_position = None
        self._clear_wheel_intent_candidate()
        self._start_hide_timer()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Capture one pressed control without interfering with text selection."""

        if self._exact_edit_host.exact_weight_edit_active():
            if self._handle_exact_edit_overlay_press(event):
                event.accept()
                return
            event.ignore()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        target = self._mouse_target_at_local_position(event.position())
        if target == "weight":
            visible_token = self._visible_token
            if visible_token is not None:
                self._activate_wheel_intent_token(
                    visible_token,
                    event.globalPosition(),
                )
            if (
                visible_token is not None
                and visible_token.kind is not PromptProjectionTokenKind.WILDCARD
            ):
                if self._gestures.weight_click_starts_exact_edit(
                    visible_token,
                    double_click_interval_ms=QApplication.doubleClickInterval(),
                ):
                    self._start_exact_weight_edit(visible_token)
            event.accept()
            return
        if target is None:
            self._clear_exact_weight_click_candidate()
            event.ignore()
            return
        self._clear_exact_weight_click_candidate()
        self._gestures.pressed_control = target
        self._gestures.hovered_control = target
        if self._visible_token is not None:
            self._activate_wheel_intent_token(
                self._visible_token,
                event.globalPosition(),
            )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Start exact edit only from an unambiguous weight double click."""

        if self._exact_edit_host.exact_weight_edit_active():
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        target = self._mouse_target_at_local_position(event.position())
        if (
            target == "weight"
            and self._visible_token is not None
            and self._visible_token.kind is not PromptProjectionTokenKind.WILDCARD
        ):
            self._start_exact_weight_edit(self._visible_token)
            event.accept()
            return
        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit one typed emphasis action when the same control is released."""

        if self._exact_edit_host.exact_weight_edit_active():
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        released_control = self._control_at_local_position(event.position())
        pressed_control = self._gestures.pressed_control
        self._gestures.pressed_control = None
        self._gestures.hovered_control = released_control
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if released_control
            else Qt.CursorShape.ArrowCursor
        )
        self.update()
        if pressed_control is not None and released_control == pressed_control:
            source_token = self._visible_token
            if source_token is not None:
                self._emit_control_step_intent(
                    released_control,
                    pointer_global_position=event.globalPosition(),
                    source_token=source_token,
                    show_weight_preview=(released_control == "increase"),
                )
        event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Adjust emphasis when the wheel is used over visible controls."""

        if self._exact_edit_host.exact_weight_edit_active():
            event.accept()
            return
        if self._visible_token is not None and not self._token_wheel_is_allowed(
            self._visible_token,
            event,
        ):
            event.ignore()
            return
        geometry = self._geometry_for_visible_token()
        if self._emit_wheel_action(
            event.angleDelta().y(),
            global_position=event.globalPosition(),
            source_geometry=geometry,
        ):
            event.accept()
            return
        event.ignore()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the passive child view aligned with overlay bounds."""

        self._view.setGeometry(self.rect())
        self._sync_view_render_state()
        super().resizeEvent(event)

    def _emit_wheel_action(
        self,
        angle_delta_y: int,
        *,
        global_position: QPointF,
        source_geometry: _TokenControlGeometry | None = None,
    ) -> bool:
        """Emit one wheel-driven weight action when controls are active."""

        if angle_delta_y == 0:
            return False
        if self._visible_token is None:
            return False
        self._emit_wheel_step_intent(
            angle_delta_y,
            pointer_global_position=global_position,
            source_token=self._visible_token,
            show_weight_preview=(
                source_geometry is not None
                and (host_point := self._host_point_from_global(global_position))
                is not None
                and self._host_point_supports_weight_preview(
                    host_point=host_point,
                    geometry=source_geometry,
                )
            ),
        )
        return True

    def _emit_viewport_wheel_action(
        self,
        event: QWheelEvent,
        *,
        viewport_position: QPointF,
    ) -> bool:
        """Emit one wheel-driven action when the pointer is over a weighted token."""

        angle_delta_y = event.angleDelta().y()
        if angle_delta_y == 0:
            return False
        self._set_pointer_from_viewport(viewport_position)
        geometry = self._interaction_geometry_at_pointer()
        if geometry is not None:
            self._apply_geometry(geometry)
            if not self._token_wheel_is_allowed(geometry.token, event):
                return False
            return self._emit_wheel_action(
                angle_delta_y,
                global_position=event.globalPosition(),
                source_geometry=geometry,
            )

        token = self._weighted_token_at_viewport_position(viewport_position)
        if token is None:
            return False
        if not self._token_wheel_is_allowed(token, event):
            return False
        self._emit_wheel_step_intent(
            angle_delta_y,
            pointer_global_position=event.globalPosition(),
            source_token=token,
            show_weight_preview=False,
        )
        return True

    def _weighted_token_at_viewport_position(
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
        return self._weighted_token_at_viewport_position(viewport_position)

    def _weight_token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the weighted token whose painted number contains one viewport point."""

        self._refresh_geometry_snapshot()
        return self._geometry_snapshot.token_at_weight_viewport_position(position)

    def _weight_token_at_surface_or_viewport_position(
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

    @staticmethod
    def _exact_edit_state_for_token(
        token: PromptProjectionToken,
    ) -> tuple[str, int, bool] | None:
        """Return the projection-owned edit buffer state for one exact-edit token."""

        if token.editing_value_text is None:
            return None
        caret_index = (
            len(token.editing_value_text)
            if token.editing_caret_index is None
            else token.editing_caret_index
        )
        return (
            token.editing_value_text,
            caret_index,
            token.editing_select_all,
        )

    def _start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Enter projection-owned exact edit mode for one emphasis number."""

        value_text = token.value_text
        if (
            value_text is None
            or token.content_start is None
            or token.content_end is None
        ):
            return
        self._gestures.stop_hide_linger()
        self._clear_weight_preview()
        self._gestures.pressed_control = None
        self._gestures.hovered_control = None
        self.unsetCursor()
        self._exact_edit_host.begin_exact_weight_edit(token)
        self.refresh_geometry()
        self.update()

    def _cancel_exact_weight_edit(self) -> None:
        """Exit exact edit mode without mutating prompt text."""

        if not self._exact_edit_host.exact_weight_edit_active():
            return
        self._exact_edit_host.cancel_exact_weight_edit()
        self._clear_exact_weight_click_candidate()
        self.refresh_geometry()

    def _maybe_begin_exact_weight_edit_from_click(self, position: QPointF) -> bool:
        """Start exact edit only when two consecutive clicks resolve to the same weight token."""

        token = self._weight_token_at_surface_or_viewport_position(position)
        if token is None:
            self._clear_exact_weight_click_candidate()
            return False
        if token.kind is PromptProjectionTokenKind.WILDCARD:
            self._clear_exact_weight_click_candidate()
            return False
        if self._gestures.weight_click_starts_exact_edit(
            token,
            double_click_interval_ms=QApplication.doubleClickInterval(),
        ):
            self._start_exact_weight_edit(token)
            return True
        return token.synthetic

    def _handle_exact_edit_viewport_double_click(self, event: QMouseEvent) -> bool:
        """Consume viewport double clicks while exact edit mode is active."""

        if event.button() != Qt.MouseButton.LeftButton:
            return True
        return self._handle_exact_edit_viewport_press(event)

    def _handle_exact_edit_viewport_press(self, event: QMouseEvent) -> bool:
        """Finalize exact edit state before outside viewport clicks continue normally."""

        if event.button() != Qt.MouseButton.LeftButton:
            return True
        token = self._exact_edit_host.exact_weight_edit_token()
        weight_rect = (
            None
            if token is None
            else self._exact_edit_host.token_weight_text_rect(token)
        )
        if weight_rect is not None and weight_rect.contains(event.position()):
            if token is not None:
                self._exact_edit_host.update_exact_weight_caret(
                    token=token,
                    caret_index=self._nearest_exact_weight_caret_index(
                        event.position(),
                        token,
                    ),
                )
                self.refresh_geometry()
            event.accept()
            return True
        self._finalize_exact_weight_edit()
        return False

    def _handle_exact_edit_overlay_press(self, event: QMouseEvent) -> bool:
        """Ignore overlay-local exact-edit presses because projection owns the number paint."""

        _ = event
        return False

    def _handle_exact_edit_key_press(self, event: QKeyEvent) -> bool:
        """Apply native number-editing keys while the exact weight editor is active."""

        handled = self._exact_edit_host.handle_exact_weight_key_press(event)
        if handled:
            self.refresh_geometry()
        return handled

    def _finalize_exact_weight_edit(self) -> None:
        """Commit valid exact weight input or cancel invalid input."""

        self._run_weight_commit(
            lambda: self._exact_edit_host.finalize_exact_weight_edit(),
            pointer_global_position=QPointF(QCursor.pos()),
            source_token=self._exact_edit_host.exact_weight_edit_token(),
            show_weight_preview=False,
        )

    def _exact_weight_font(self) -> QFont:
        """Return the font used by exact edit mode so it matches rendered weights."""

        return emphasis_weight_font(self._surface_widget.font())

    def _nearest_exact_weight_caret_index(
        self,
        viewport_position: QPointF,
        token: PromptProjectionToken,
    ) -> int:
        """Return the nearest caret boundary for one viewport-local exact edit click."""

        buffer_state = self._exact_edit_state_for_token(token)
        if buffer_state is None:
            return 0
        buffer_text, _, _ = buffer_state
        weight_rect = self._exact_edit_host.token_weight_text_rect(token)
        if weight_rect is None:
            return len(buffer_text)
        metrics = QFontMetricsF(self._exact_weight_font())
        text_left = weight_rect.left()
        boundaries = [
            text_left + metrics.horizontalAdvance(buffer_text[:index])
            for index in range(len(buffer_text) + 1)
        ]
        return min(
            range(len(boundaries)),
            key=lambda index: abs(boundaries[index] - viewport_position.x()),
        )

    def _set_pointer_from_viewport(self, viewport_position: QPointF) -> None:
        """Store the current pointer position in host coordinates from the viewport."""

        if not self._runtime_widgets_are_valid():
            self._gestures.pointer_host_position = None
            return
        host_point = self._geometry.host_point_from_viewport_position(viewport_position)
        self._gestures.pointer_host_position = (
            QPointF(host_point) if host_point is not None else None
        )

    def _set_pointer_from_overlay(self, overlay_position: QPointF) -> None:
        """Store the current pointer position in host coordinates from the overlay."""

        self._gestures.pointer_host_position = QPointF(
            self.mapToParent(overlay_position.toPoint())
        )

    def _set_pointer_from_global(self, global_position: QPointF) -> None:
        """Store the current pointer position in host coordinates from one global point."""

        host_point = self._host_point_from_global(global_position)
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
        self._set_pointer_from_global(global_position)

    def _emit_control_step_intent(
        self,
        control: PromptTokenWeightControl,
        *,
        pointer_global_position: QPointF,
        source_token: PromptProjectionToken,
        show_weight_preview: bool,
    ) -> None:
        """Emit one typed arrow-step intent through the interaction owner."""

        self._run_weight_commit(
            lambda: self.tokenWeightStepTriggered.emit(
                PromptTokenWeightStepIntent(
                    token=source_token,
                    control=control,
                    pointer_global_position=QPointF(pointer_global_position),
                    show_weight_preview=show_weight_preview,
                )
            ),
            pointer_global_position=pointer_global_position,
            source_token=source_token,
            show_weight_preview=show_weight_preview,
        )

    def _emit_wheel_step_intent(
        self,
        angle_delta_y: int,
        *,
        pointer_global_position: QPointF,
        source_token: PromptProjectionToken,
        show_weight_preview: bool,
    ) -> None:
        """Emit one typed wheel-step intent through the interaction owner."""

        self._run_weight_commit(
            lambda: self.tokenWeightWheelStepTriggered.emit(
                PromptTokenWeightWheelStepIntent(
                    token=source_token,
                    angle_delta_y=angle_delta_y,
                    pointer_global_position=QPointF(pointer_global_position),
                    show_weight_preview=show_weight_preview,
                )
            ),
            pointer_global_position=pointer_global_position,
            source_token=source_token,
            show_weight_preview=show_weight_preview,
        )

    def _run_weight_commit(
        self,
        commit: Callable[[], None],
        *,
        pointer_global_position: QPointF,
        source_token: PromptProjectionToken | None,
        show_weight_preview: bool,
    ) -> None:
        """Run an interaction-owned token-weight commit and refresh overlay feedback."""

        self._gestures.begin_action(pointer_global_position)
        self._set_pointer_from_global(pointer_global_position)
        try:
            commit()
        finally:
            self._gestures.finish_action()
            self.refresh_geometry()
            if show_weight_preview and source_token is not None:
                self._show_weight_preview_for_token(
                    self._resolved_post_action_token(source_token),
                    pointer_global_position=pointer_global_position,
                )
            else:
                self._clear_weight_preview()

    def _start_hide_timer(self) -> None:
        """Delay hiding briefly so pointer travel into the controls stays stable."""

        self._gestures.start_hide_linger(visible_token=self._visible_token)

    def _handle_hide_timeout(self) -> None:
        """Hide controls after the pointer has remained outside the activation zone."""

        if self._gestures.pressed_control is not None:
            return
        geometry = self._interaction_geometry_at_pointer()
        if geometry is None:
            self._hide_controls()
            return
        self._apply_geometry(geometry)

    def _geometry_for_visible_token(self) -> _TokenControlGeometry | None:
        """Return fresh geometry for the token currently owning visible controls."""

        if self._visible_token is None:
            return None
        return self._geometry_for_token(self._visible_token)

    def _interaction_geometry_at_pointer(self) -> _TokenControlGeometry | None:
        """Return the weighted token whose activation zone contains the pointer."""

        return self._geometry_snapshot.geometry_at_pointer(
            self._gestures.pointer_host_position
        )

    def _record_wheel_intent_pointer_from_viewport(
        self,
        event: QMouseEvent,
    ) -> None:
        """Record token hover intent from one real viewport pointer move."""

        token = self._weighted_token_at_viewport_position(event.position())
        if token is None:
            self._set_pointer_from_viewport(event.position())
            geometry = self._interaction_geometry_at_pointer()
            if geometry is not None:
                token = geometry.token
        if token is None:
            self._clear_wheel_intent_candidate()
            return
        global_position = event.globalPosition()
        self._wheel_intent_owner.record_token_pointer_move(token, global_position)
        self._wheel_intent_owner.refresh_candidate_from_pointer(
            (token, QPointF(global_position))
        )

    def _activate_wheel_intent_token(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record explicit click activation for one numeric token wheel target."""

        self._wheel_intent_owner.activate_token(token, global_position)

    def _clear_wheel_intent_candidate(self) -> None:
        """Clear any pending or ready token from hover-driven wheel intent."""

        self._wheel_intent_owner.clear_candidate()

    def _refresh_wheel_intent_candidate_for_geometry(
        self,
        geometry: _TokenControlGeometry,
    ) -> None:
        """Publish the current control-zone token to the wheel-intent owner."""

        pointer_position = self._gestures.pointer_host_position
        if pointer_position is None:
            return
        self._wheel_intent_owner.refresh_candidate_from_pointer(
            (
                geometry.token,
                self._global_position_from_host_position(pointer_position),
            )
        )

    def _token_wheel_is_allowed(
        self,
        token: PromptProjectionToken,
        event: QWheelEvent,
    ) -> bool:
        """Return whether one token may consume the wheel event."""

        return self._wheel_intent_owner.token_wheel_is_allowed(token, event)

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

    def _update_hovered_control(self, local_position: QPointF) -> None:
        """Refresh the hovered control based on one overlay-local pointer position."""

        next_control = self._control_at_local_position(local_position)
        if next_control == self._gestures.hovered_control:
            return
        self._gestures.hovered_control = next_control
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if next_control
            else Qt.CursorShape.ArrowCursor
        )
        self.update()

    def _control_at_local_position(
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

    def _mouse_target_at_local_position(
        self,
        local_position: QPointF,
    ) -> Literal["increase", "decrease", "weight"] | None:
        """Classify one overlay-local point so ambiguous hits never resolve to exact edit."""

        control = self._control_at_local_position(local_position)
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

    def _clear_exact_weight_click_candidate(self) -> None:
        """Forget any pending number click waiting for a second unambiguous weight click."""

        self._gestures.clear_click_candidate()

    def _host_rect_to_local_rect(self, host_rect: QRectF) -> QRectF:
        """Return one host-local control rect translated into overlay-local coordinates."""

        top_left = self.mapFromParent(host_rect.topLeft().toPoint())
        return QRectF(QPointF(top_left), host_rect.size())

    def _show_weight_preview_for_token(
        self,
        token: PromptProjectionToken | None,
        *,
        pointer_global_position: QPointF,
    ) -> None:
        """Show a short-lived weight label above the current mouse pointer."""

        if (
            token is None
            or token.value_text is None
            or not self._runtime_widgets_are_valid()
        ):
            self._clear_weight_preview()
            return
        preview_text = (
            token.wildcard_display_tag
            if token.kind is PromptProjectionTokenKind.WILDCARD
            else token.value_text
        )
        if preview_text is None:
            self._clear_weight_preview()
            return
        preview_font = self._weight_preview_font()
        metrics = QFontMetricsF(preview_font)
        text_width = metrics.horizontalAdvance(preview_text)
        text_height = metrics.height()
        preview_rect = QRectF(
            0.0,
            0.0,
            text_width + self._WEIGHT_PREVIEW_HORIZONTAL_PADDING * 2.0,
            text_height + self._WEIGHT_PREVIEW_VERTICAL_PADDING * 2.0,
        )
        host_point = self._host_point_from_global(pointer_global_position)
        if host_point is None:
            self._clear_weight_preview()
            return
        preview_rect.moveLeft(host_point.x() - preview_rect.width() / 2.0)
        preview_rect.moveTop(
            host_point.y() - self._WEIGHT_PREVIEW_CURSOR_OFFSET - preview_rect.height()
        )
        host_rect = self._host_rect()
        if host_rect.isNull():
            self._clear_weight_preview()
            return
        preview_rect.moveLeft(
            max(
                host_rect.left() + self._WEIGHT_PREVIEW_MARGIN,
                min(
                    preview_rect.left(),
                    host_rect.right()
                    - preview_rect.width()
                    - self._WEIGHT_PREVIEW_MARGIN,
                ),
            )
        )
        preview_rect.moveTop(
            max(
                host_rect.top() + self._WEIGHT_PREVIEW_MARGIN,
                min(
                    preview_rect.top(),
                    host_rect.bottom()
                    - preview_rect.height()
                    - self._WEIGHT_PREVIEW_MARGIN,
                ),
            )
        )
        self._gestures.show_weight_preview(text=preview_text, rect=preview_rect)
        self._refresh_overlay_bounds()

    def _host_point_supports_weight_preview(
        self,
        *,
        host_point: QPointF,
        geometry: _TokenControlGeometry,
    ) -> bool:
        """Return whether the pointer is over the number or the up control."""

        return geometry.anchor_rect.contains(
            host_point
        ) or geometry.increase_rect.contains(host_point)

    def _resolved_post_action_token(
        self,
        source_token: PromptProjectionToken,
    ) -> PromptProjectionToken | None:
        """Resolve the weighted token that owns the updated value after one mutation."""

        visible_token = self._visible_token
        resolved_token = self._geometry_snapshot.current_token_for(source_token)
        if resolved_token is not None:
            return resolved_token
        if visible_token is not None and tokens_share_content_range(
            visible_token, source_token
        ):
            return visible_token
        if visible_token is not None and visible_token.kind is source_token.kind:
            return visible_token
        return None

    def _current_projection_token_for(
        self,
        source_token: PromptProjectionToken,
    ) -> PromptProjectionToken | None:
        """Return the current projection token matching one cached weighted token."""

        return self._geometry_snapshot.current_token_for(source_token)

    def _clear_weight_preview(self) -> None:
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

    def _weight_preview_font(self) -> QFont:
        """Return the font used by the floating weight preview bubble."""

        font = QFont(self.font())
        if font.pointSizeF() > 0:
            font.setPointSizeF(max(8.0, font.pointSizeF() - 1.0))
        else:
            font.setPixelSize(max(12, font.pixelSize() - 1))
        return font


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
