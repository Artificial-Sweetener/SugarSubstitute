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

"""Route Qt input into token-weight interaction owners."""

from __future__ import annotations

from typing import Literal, Protocol, cast

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QCursor, QEnterEvent, QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)

from .token_weight_actions import PromptTokenWeightActionCoordinator
from .token_weight_exact_edit import (
    PromptTokenWeightExactEditController,
    PromptTokenWeightExactEditPressResult,
)
from .token_weight_geometry import PromptTokenWeightControlGeometry
from .token_weight_gestures import (
    PromptTokenWeightControl,
    PromptTokenWeightGestureController,
)
from .token_weight_wheel_intent import PromptTokenWeightWheelIntentRouter


class PromptTokenWeightInputHost(Protocol):
    """Expose mounted geometry and action ports required by Qt input routing."""

    @property
    def visible_token(self) -> PromptProjectionToken | None:
        """Return the token currently owning visible controls."""
        ...

    def refresh_geometry(self) -> None:
        """Recompute mounted control geometry after interaction state changes."""
        ...

    def apply_geometry(self, geometry: PromptTokenWeightControlGeometry) -> None:
        """Publish one already-resolved mounted geometry snapshot."""
        ...

    def token_at_weight_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the token whose painted number owns one surface position."""
        ...

    def set_pointer_from_viewport(self, viewport_position: QPointF) -> None:
        """Store a viewport-local pointer in host coordinates."""
        ...

    def set_pointer_from_overlay(self, overlay_position: QPointF) -> None:
        """Store an overlay-local pointer in host coordinates."""
        ...

    def record_wheel_intent_pointer_from_viewport(self, event: QMouseEvent) -> None:
        """Publish the numeric token under a real viewport pointer move."""
        ...

    def start_hide_linger(self) -> None:
        """Delay hiding while pointer travel into controls remains plausible."""
        ...

    def mouse_target_at_local_position(
        self,
        local_position: QPointF,
    ) -> Literal["increase", "decrease", "weight"] | None:
        """Classify one overlay-local pointer target."""
        ...

    def control_at_local_position(
        self,
        local_position: QPointF,
    ) -> PromptTokenWeightControl | None:
        """Return the arrow control owning one overlay-local point."""
        ...

    def update_hovered_control(self, local_position: QPointF) -> None:
        """Refresh arrow hover state from one overlay-local point."""
        ...

    def interaction_geometry_at_pointer(
        self,
    ) -> PromptTokenWeightControlGeometry | None:
        """Return the weighted-token geometry owning the stored pointer."""
        ...

    def geometry_for_visible_token(
        self,
    ) -> PromptTokenWeightControlGeometry | None:
        """Return fresh geometry for the visible token."""
        ...

    def weighted_token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the weighted token painted under one viewport point."""
        ...

    def host_point_from_global(self, global_position: QPointF) -> QPointF | None:
        """Map a live global point into mounted host coordinates."""
        ...

    def host_point_supports_weight_preview(
        self,
        *,
        host_point: QPointF,
        geometry: PromptTokenWeightControlGeometry,
    ) -> bool:
        """Return whether mounted geometry supports feedback at one host point."""
        ...


class PromptTokenWeightInputRouter:
    """Own Qt event classification and token-weight gesture routing."""

    def __init__(
        self,
        host: PromptTokenWeightInputHost,
        *,
        overlay: QWidget,
        surface_widget: QWidget,
        viewport: QWidget,
        gestures: PromptTokenWeightGestureController,
        exact_edit: PromptTokenWeightExactEditController,
        actions: PromptTokenWeightActionCoordinator,
        wheel_intent: PromptTokenWeightWheelIntentRouter,
    ) -> None:
        """Bind Qt event sources to mounted token-weight interaction owners."""

        self._host = host
        self._overlay = overlay
        self._surface_widget = surface_widget
        self._viewport = viewport
        self._gestures = gestures
        self._exact_edit = exact_edit
        self._actions = actions
        self._wheel_intent = wheel_intent

    def begin_exact_edit_at_position(self, position: QPointF) -> bool:
        """Start exact editing when a surface point hits a supported number."""

        token = self._host.token_at_weight_position(position)
        if token is None or token.kind is PromptProjectionTokenKind.WILDCARD:
            return False
        return self._start_exact_edit(token)

    def handle_exact_weight_click(self, position: QPointF) -> bool:
        """Advance exact-edit activation for one surface or overlay click."""

        token = self._host.token_at_weight_position(position)
        if token is None or token.kind is PromptProjectionTokenKind.WILDCARD:
            self._exact_edit.clear_click_candidate()
            return False
        if self._exact_edit.click_starts_edit(
            token,
            double_click_interval_ms=QApplication.doubleClickInterval(),
        ):
            self._start_exact_edit(token)
            return True
        return token.synthetic

    def handle_host_wheel_event(self, event: QWheelEvent) -> bool:
        """Handle a wheel event delivered through the prompt host viewport."""

        if self._exact_edit.active:
            event.accept()
            return True
        viewport_position = QPointF(
            self._viewport.mapFromGlobal(event.globalPosition().toPoint())
        )
        if self._emit_viewport_wheel_action(
            event,
            viewport_position=viewport_position,
        ):
            event.accept()
            return True
        return False

    def filter_event(self, watched: QObject, event: QEvent) -> bool | None:
        """Route installed surface events or return ``None`` for base handling."""

        if watched is self._viewport:
            handled = self._filter_viewport_event(event)
            if handled is not None:
                return handled
        if watched is self._surface_widget:
            handled = self._filter_surface_event(event)
            if handled is not None:
                return handled
        if (
            watched is not self._viewport
            and self._exact_edit.active
            and event.type() == QEvent.Type.KeyPress
        ):
            return self._handle_exact_key_press(cast(QKeyEvent, event))
        return None

    def enter(self, event: QEnterEvent) -> None:
        """Claim pointer ownership when it enters the overlay."""

        self._host.set_pointer_from_overlay(event.position())
        self._host.update_hovered_control(event.position())
        self._host.refresh_geometry()

    def move(self, event: QMouseEvent) -> None:
        """Refresh pointer and hover ownership over the overlay."""

        self._host.set_pointer_from_overlay(event.position())
        self._host.update_hovered_control(event.position())
        self._host.refresh_geometry()

    def leave(self) -> None:
        """Release overlay hover ownership and begin delayed hiding."""

        if self._gestures.action_in_progress:
            return
        self._gestures.hovered_control = None
        self._overlay.unsetCursor()
        self._gestures.pointer_host_position = None
        self._wheel_intent.clear()
        self._host.start_hide_linger()

    def press(self, event: QMouseEvent) -> None:
        """Route one overlay-local pointer press."""

        if self._exact_edit.active:
            event.ignore()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        target = self._host.mouse_target_at_local_position(event.position())
        if target == "weight":
            self._press_weight(event)
            return
        if target is None:
            self._exact_edit.clear_click_candidate()
            event.ignore()
            return
        self._press_control(target, event)

    def double_click(self, event: QMouseEvent) -> None:
        """Treat rapid arrow clicks as steps and number double-clicks as exact edits."""

        if self._exact_edit.active:
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        target = self._host.mouse_target_at_local_position(event.position())
        if target == "increase" or target == "decrease":
            self._press_control(target, event)
            return
        token = self._host.visible_token
        if (
            target == "weight"
            and token is not None
            and token.kind is not PromptProjectionTokenKind.WILDCARD
        ):
            self._start_exact_edit(token)
            event.accept()
            return
        event.ignore()

    def release(self, event: QMouseEvent) -> None:
        """Dispatch a step when a pressed arrow is released over itself."""

        if self._exact_edit.active:
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        released_control = self._host.control_at_local_position(event.position())
        pressed_control = self._gestures.pressed_control
        self._gestures.pressed_control = None
        self._gestures.hovered_control = released_control
        self._overlay.setCursor(
            Qt.CursorShape.PointingHandCursor
            if released_control
            else Qt.CursorShape.ArrowCursor
        )
        self._overlay.update()
        if pressed_control is not None and released_control == pressed_control:
            source_token = self._host.visible_token
            if source_token is not None:
                self._actions.emit_control_step(
                    released_control,
                    pointer_global_position=event.globalPosition(),
                    source_token=source_token,
                    show_weight_preview=(released_control == "increase"),
                )
        event.accept()

    def wheel(self, event: QWheelEvent) -> None:
        """Route wheel input over the visible mounted controls."""

        if self._exact_edit.active:
            event.accept()
            return
        token = self._host.visible_token
        if token is not None and not self._wheel_intent.wheel_is_allowed(token, event):
            event.ignore()
            return
        geometry = self._host.geometry_for_visible_token()
        if self._emit_wheel_action(
            event.angleDelta().y(),
            global_position=event.globalPosition(),
            source_geometry=geometry,
        ):
            event.accept()
            return
        event.ignore()

    def _emit_wheel_action(
        self,
        angle_delta_y: int,
        *,
        global_position: QPointF,
        source_geometry: PromptTokenWeightControlGeometry | None = None,
    ) -> bool:
        """Dispatch a wheel-driven step when mounted controls are active."""

        if angle_delta_y == 0:
            return False
        token = self._host.visible_token
        if token is None:
            return False
        host_point = self._host.host_point_from_global(global_position)
        self._actions.emit_wheel_step(
            angle_delta_y,
            pointer_global_position=global_position,
            source_token=token,
            show_weight_preview=(
                source_geometry is not None
                and host_point is not None
                and self._host.host_point_supports_weight_preview(
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
        """Dispatch wheel input over mounted or directly painted token geometry."""

        angle_delta_y = event.angleDelta().y()
        if angle_delta_y == 0:
            return False
        self._host.set_pointer_from_viewport(viewport_position)
        geometry = self._host.interaction_geometry_at_pointer()
        if geometry is not None:
            self._host.apply_geometry(geometry)
            if not self._wheel_intent.wheel_is_allowed(geometry.token, event):
                return False
            return self._emit_wheel_action(
                angle_delta_y,
                global_position=event.globalPosition(),
                source_geometry=geometry,
            )

        token = self._host.weighted_token_at_viewport_position(viewport_position)
        if token is None or not self._wheel_intent.wheel_is_allowed(token, event):
            return False
        self._actions.emit_wheel_step(
            angle_delta_y,
            pointer_global_position=event.globalPosition(),
            source_token=token,
            show_weight_preview=False,
        )
        return True

    def _filter_viewport_event(self, event: QEvent) -> bool | None:
        """Route one event installed on the projection viewport."""

        if self._exact_edit.active:
            handled = self._filter_active_exact_event(event)
            if handled is not None:
                return handled
        if event.type() == QEvent.Type.MouseMove:
            mouse_event = cast(QMouseEvent, event)
            self._host.set_pointer_from_viewport(mouse_event.position())
            self._host.record_wheel_intent_pointer_from_viewport(mouse_event)
            self._host.refresh_geometry()
        elif event.type() == QEvent.Type.MouseButtonPress:
            self._record_surface_press(cast(QMouseEvent, event))
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            return self._handle_surface_double_click(cast(QMouseEvent, event))
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
                return None
            self._gestures.pointer_host_position = None
            self._host.start_hide_linger()
        return None

    def _filter_surface_event(self, event: QEvent) -> bool | None:
        """Route one event installed on the projection surface widget."""

        if self._exact_edit.active:
            handled = self._filter_active_exact_event(event)
            if handled is not None:
                return handled
        if event.type() == QEvent.Type.MouseButtonDblClick:
            return self._handle_surface_double_click(cast(QMouseEvent, event))
        if event.type() == QEvent.Type.MouseButtonPress:
            self._record_surface_press(cast(QMouseEvent, event))
        return None

    def _filter_active_exact_event(self, event: QEvent) -> bool | None:
        """Consume pointer and wheel input governed by active exact editing."""

        if event.type() == QEvent.Type.MouseButtonPress:
            return self._handle_exact_viewport_press(cast(QMouseEvent, event))
        if event.type() == QEvent.Type.MouseButtonDblClick:
            mouse_event = cast(QMouseEvent, event)
            if mouse_event.button() != Qt.MouseButton.LeftButton:
                return True
            return self._handle_exact_viewport_press(mouse_event)
        if event.type() == QEvent.Type.Wheel:
            return True
        return None

    def _record_surface_press(self, event: QMouseEvent) -> None:
        """Publish wheel activation or retire stale exact-click state."""

        if event.button() != Qt.MouseButton.LeftButton:
            return
        token = self._host.token_at_weight_position(event.position())
        if token is None:
            self._exact_edit.clear_click_candidate()
            return
        self._wheel_intent.activate(token, event.globalPosition())

    def _handle_surface_double_click(self, event: QMouseEvent) -> bool | None:
        """Activate exact editing from a supported painted number."""

        if event.button() != Qt.MouseButton.LeftButton:
            return None
        if self.begin_exact_edit_at_position(event.position()):
            event.accept()
            return True
        return None

    def _handle_exact_viewport_press(self, event: QMouseEvent) -> bool:
        """Update active exact editing or finalize before an outside click."""

        result = self._exact_edit.handle_viewport_press(event)
        if result is PromptTokenWeightExactEditPressResult.CONSUMED:
            return True
        if result is PromptTokenWeightExactEditPressResult.UPDATED:
            self._host.refresh_geometry()
            event.accept()
            return True
        self._actions.commit(
            self._exact_edit.finalize,
            pointer_global_position=QPointF(QCursor.pos()),
            source_token=self._exact_edit.token,
            show_weight_preview=False,
        )
        return False

    def _handle_exact_key_press(self, event: QKeyEvent) -> bool:
        """Apply native number-editing keys while exact editing is active."""

        handled = self._exact_edit.handle_key_press(event)
        if handled:
            self._host.refresh_geometry()
        return handled

    def _press_weight(self, event: QMouseEvent) -> None:
        """Activate wheel and exact-edit intent for the visible number."""

        token = self._host.visible_token
        if token is not None:
            self._wheel_intent.activate(token, event.globalPosition())
        if token is not None and token.kind is not PromptProjectionTokenKind.WILDCARD:
            if self._exact_edit.click_starts_edit(
                token,
                double_click_interval_ms=QApplication.doubleClickInterval(),
            ):
                self._start_exact_edit(token)
        event.accept()

    def _press_control(
        self,
        control: PromptTokenWeightControl,
        event: QMouseEvent,
    ) -> None:
        """Latch one arrow press and publish explicit wheel activation."""

        self._exact_edit.clear_click_candidate()
        self._gestures.pressed_control = control
        self._gestures.hovered_control = control
        token = self._host.visible_token
        if token is not None:
            self._wheel_intent.activate(token, event.globalPosition())
        self._overlay.setCursor(Qt.CursorShape.PointingHandCursor)
        self._overlay.update()
        event.accept()

    def _start_exact_edit(self, token: PromptProjectionToken) -> bool:
        """Start exact editing and refresh its mounted presentation."""

        if not self._exact_edit.start(token):
            return False
        self._overlay.unsetCursor()
        self._host.refresh_geometry()
        self._overlay.update()
        return True


__all__ = ["PromptTokenWeightInputHost", "PromptTokenWeightInputRouter"]
