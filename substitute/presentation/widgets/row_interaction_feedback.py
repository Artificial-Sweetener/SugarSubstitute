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

"""Reusable Windows-style hover, press, activation, and row overlay feedback."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, cast

from PySide6.QtCore import (
    QObject,
    Property,
    QEvent,
    QPropertyAnimation,
    QRect,
    Qt,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget
from qfluentwidgets import isDarkTheme  # type: ignore[import-untyped]

from substitute.presentation.shell.chrome_style import (
    windows_list_item_state_overlay_color,
)

_BRUSH_TRANSITION_DURATION_MS = 83


class RowInteractionFeedback(QObject):
    """Provide reusable row hover, press, activation, and overlay feedback."""

    def __init__(
        self,
        owner: QWidget,
        *,
        overlay_path: Callable[[QRect], QPainterPath],
        activation: Callable[[], None] | None = None,
        feedback_enabled: bool = False,
        cursor_when_enabled: object | None = None,
        animate: bool = True,
        manage_cursor: bool = True,
        consume_target_press: bool = True,
    ) -> None:
        """Create feedback for one owner widget while leaving geometry to the owner."""

        super().__init__(owner)
        self._owner = owner
        self._overlay_path = overlay_path
        self._activation = activation
        self._feedback_enabled = feedback_enabled
        self._cursor_when_enabled = cursor_when_enabled or _pointing_hand_cursor()
        self._manage_cursor = manage_cursor
        self._consume_target_press = consume_target_press
        self._interactive_targets: tuple[QWidget, ...] = ()
        self._is_hovered = False
        self._is_pressed = False
        self._is_forced_hovered = False
        self._overlay_alpha = float(self._target_alpha())
        self._animation: QPropertyAnimation | None = None
        if animate:
            self._animation = QPropertyAnimation(self, b"overlayAlpha", self)
            self._animation.setDuration(_BRUSH_TRANSITION_DURATION_MS)
        set_attribute = getattr(self._owner, "setAttribute", None)
        widget_attribute = getattr(Qt, "WidgetAttribute", None)
        hover_attribute = getattr(widget_attribute, "WA_Hover", None)
        if callable(set_attribute) and hover_attribute is not None:
            set_attribute(hover_attribute, True)
        set_mouse_tracking = getattr(self._owner, "setMouseTracking", None)
        if callable(set_mouse_tracking):
            set_mouse_tracking(True)
        self._sync_cursors()

    def set_activation(self, callback: Callable[[], None] | None) -> None:
        """Set or clear row activation."""

        self._activation = callback
        if callback is None:
            self.clear_transient_state()
        else:
            under_mouse = getattr(self._owner, "underMouse", None)
            if callable(under_mouse) and bool(under_mouse()):
                self.set_hovered(True)
        self._sync_cursors()
        self._retarget_overlay_alpha()

    def activate(self) -> None:
        """Invoke the current activation callback when one exists."""

        if self._activation is not None:
            self._activation()

    def set_feedback_enabled(self, enabled: bool) -> None:
        """Enable or disable feedback without requiring a click activation callback."""

        if self._feedback_enabled == enabled:
            return
        self._feedback_enabled = enabled
        if not enabled and self._activation is None:
            self.clear_transient_state()
        self._sync_cursors()
        self._retarget_overlay_alpha()

    def set_interactive_targets(self, targets: Iterable[QWidget]) -> None:
        """Register child widgets whose body clicks should be handled as row clicks."""

        for target in self._interactive_targets:
            remove_event_filter = getattr(target, "removeEventFilter", None)
            if callable(remove_event_filter):
                remove_event_filter(self)
        self._interactive_targets = tuple(targets)
        for target in self._interactive_targets:
            install_event_filter = getattr(target, "installEventFilter", None)
            if callable(install_event_filter):
                install_event_filter(self)
        self._sync_cursors()

    def set_cursor_when_enabled(self, cursor: object) -> None:
        """Update the cursor used when feedback or activation is enabled."""

        self._cursor_when_enabled = cursor
        self._sync_cursors()

    def set_hovered(self, hovered: bool) -> None:
        """Set pointer-over state and repaint only when it changes."""

        if self._is_hovered == hovered:
            return
        self._is_hovered = hovered
        self._retarget_overlay_alpha()

    def set_pressed(self, pressed: bool) -> None:
        """Set pressed state and repaint only when it changes."""

        if self._is_pressed == pressed:
            return
        self._is_pressed = pressed
        self._retarget_overlay_alpha()

    def set_forced_hovered(self, hovered: bool) -> None:
        """Force hover-style feedback for active or selected rows."""

        if self._is_forced_hovered == hovered:
            return
        self._is_forced_hovered = hovered
        self._retarget_overlay_alpha()

    def clear_transient_state(self) -> None:
        """Clear hover and pressed state without changing forced hover state."""

        hover_changed = self._is_hovered
        press_changed = self._is_pressed
        self._is_hovered = False
        self._is_pressed = False
        if hover_changed or press_changed:
            self._retarget_overlay_alpha()

    def is_feedback_enabled(self) -> bool:
        """Return whether row hover and press feedback is active."""

        return getattr(self, "_activation", None) is not None or bool(
            getattr(self, "_feedback_enabled", False)
        )

    def has_activation(self) -> bool:
        """Return whether row click activation is active."""

        return getattr(self, "_activation", None) is not None

    def handle_mouse_press(self, event: object) -> bool:
        """Handle an owner mouse press and return whether it was consumed."""

        if not self.is_feedback_enabled() or not is_left_mouse_press(event):
            return False
        self.set_pressed(True)
        accept = getattr(event, "accept", None)
        if callable(accept):
            accept()
        return True

    def handle_mouse_release(self, event: object) -> bool:
        """Handle an owner mouse release and return whether it was consumed."""

        if not self.is_feedback_enabled() or not is_left_mouse_release(event):
            return False
        self._release_row_activation(event)
        accept = getattr(event, "accept", None)
        if callable(accept):
            accept()
        return True

    def eventFilter(self, watched: object, event: object) -> bool:
        """Route registered child-target mouse events through row feedback."""

        if (
            self.is_feedback_enabled()
            and isinstance(watched, QWidget)
            and watched in self._interactive_targets
        ):
            if is_left_mouse_press(event):
                self.set_pressed(True)
                return self._consume_target_press
            if is_left_mouse_release(event):
                self._release_row_activation(event)
                return True
        if isinstance(watched, QObject) and isinstance(event, QEvent):
            return bool(super().eventFilter(watched, event))
        return False

    def current_overlay_color(self) -> QColor:
        """Return the effective overlay color for the current animated state."""

        color = windows_list_item_state_overlay_color(
            is_dark=bool(isDarkTheme()),
            is_pressed=self.is_feedback_enabled() and self._is_pressed,
            is_hovered=(
                self._is_forced_hovered
                or (self.is_feedback_enabled() and self._is_hovered)
            ),
        )
        color.setAlpha(max(0, min(255, round(self._overlay_alpha))))
        return color

    def paint_overlay(self, painter: QPainter) -> None:
        """Paint the current overlay using the consumer-provided path."""

        color = self.current_overlay_color()
        if color.alpha() == 0:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(self._overlay_path(self._owner.rect()))

    def _get_overlay_alpha(self) -> float:
        """Return the current animated overlay alpha."""

        return self._overlay_alpha

    def _set_overlay_alpha(self, alpha: float) -> None:
        """Store animated overlay alpha and schedule an owner repaint."""

        if self._overlay_alpha == alpha:
            return
        self._overlay_alpha = alpha
        self._owner.update()

    overlayAlpha = Property(float, _get_overlay_alpha, _set_overlay_alpha)

    def _release_row_activation(self, event: object) -> None:
        """Clear press feedback and activate if a click release remains inside."""

        self.set_pressed(False)
        if self._activation is None or not self._event_inside_owner(event):
            return
        self._activation()

    def _event_inside_owner(self, event: object) -> bool:
        """Return whether an event position is still inside the owner widget."""

        position = _event_owner_position(event)
        if position is None:
            return True
        contains = getattr(self._owner.rect(), "contains", None)
        return not callable(contains) or bool(contains(position))

    def _sync_cursors(self) -> None:
        """Synchronize owner and child cursors with feedback state."""

        if not self._manage_cursor:
            return
        cursor = (
            self._cursor_when_enabled if self.is_feedback_enabled() else _arrow_cursor()
        )
        self._owner.setCursor(cast(Any, cursor))
        for target in self._interactive_targets:
            target.setCursor(cast(Any, cursor))

    def _target_alpha(self) -> int:
        """Return target overlay alpha for the current logical state."""

        if self.is_feedback_enabled() and self._is_pressed:
            return windows_list_item_state_overlay_color(
                is_dark=bool(isDarkTheme()),
                is_pressed=True,
                is_hovered=True,
            ).alpha()
        if self._is_forced_hovered or (self.is_feedback_enabled() and self._is_hovered):
            return windows_list_item_state_overlay_color(
                is_dark=bool(isDarkTheme()),
                is_pressed=False,
                is_hovered=True,
            ).alpha()
        return 0

    def _retarget_overlay_alpha(self) -> None:
        """Move the painted overlay alpha toward the current target state."""

        target_alpha = float(self._target_alpha())
        if self._animation is None or (self.is_feedback_enabled() and self._is_pressed):
            if self._animation is not None:
                self._animation.stop()
            self._set_overlay_alpha(target_alpha)
            return
        self._animation.stop()
        self._animation.setStartValue(self._overlay_alpha)
        self._animation.setEndValue(target_alpha)
        self._animation.start()


def is_left_mouse_press(event: object) -> bool:
    """Return whether an object looks like a left-button mouse press event."""

    event_type = getattr(event, "type", None)
    button = getattr(event, "button", None)
    return (
        callable(event_type)
        and event_type() == QEvent.Type.MouseButtonPress
        and callable(button)
        and button() == _left_mouse_button()
    )


def is_left_mouse_release(event: object) -> bool:
    """Return whether an object looks like a left-button mouse release event."""

    event_type = getattr(event, "type", None)
    button = getattr(event, "button", None)
    return (
        callable(event_type)
        and event_type() == QEvent.Type.MouseButtonRelease
        and callable(button)
        and button() == _left_mouse_button()
    )


def _event_owner_position(event: object) -> object | None:
    """Return a mouse event position usable by QWidget.rect().contains(...)."""

    position = getattr(event, "position", None)
    if callable(position):
        point = position()
        to_point = getattr(point, "toPoint", None)
        return cast(object, to_point() if callable(to_point) else point)
    pos = getattr(event, "pos", None)
    if callable(pos):
        return cast(object, pos())
    return None


def _left_mouse_button() -> object:
    """Return the active Qt binding's left mouse button enum."""

    mouse_button = getattr(Qt, "MouseButton", None)
    return getattr(mouse_button, "LeftButton", getattr(Qt, "LeftButton", None))


def _pointing_hand_cursor() -> object:
    """Return the active Qt binding's pointing-hand cursor enum."""

    cursor_shape = getattr(Qt, "CursorShape", None)
    return getattr(
        cursor_shape,
        "PointingHandCursor",
        getattr(Qt, "PointingHandCursor", None),
    )


def _arrow_cursor() -> object:
    """Return the active Qt binding's arrow cursor enum."""

    cursor_shape = getattr(Qt, "CursorShape", None)
    return getattr(cursor_shape, "ArrowCursor", getattr(Qt, "ArrowCursor", None))
