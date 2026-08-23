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

"""Own deterministic time, Qt lifetime, and event builders for wheel tests."""

from __future__ import annotations

from typing import TypeVar

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.widgets.wheel_intent_controller import (
    WheelIntentController,
)
from tests.support.prompt_editor.projection_engine_support import (
    process_events,
    surface_for,
    token_weight_controls_for,
)
from tests.support.qt.lifecycle import destroy_qt_object


_WidgetT = TypeVar("_WidgetT", bound=QWidget)


class ManualClock:
    """Provide deterministic monotonic time for wheel-intent dwell policy."""

    def __init__(self) -> None:
        """Start one isolated interaction at zero milliseconds."""

        self._milliseconds = 0

    def __call__(self) -> int:
        """Return the current controlled timestamp."""

        return self._milliseconds

    def advance(self, milliseconds: int) -> None:
        """Advance controlled time without sleeping the process."""

        self._milliseconds += milliseconds


class WheelIntentOwner:
    """Own one test's widgets, controllers, and controlled intent clock."""

    def __init__(self, application: QApplication) -> None:
        """Retain the worker application and initialize isolated ownership."""

        self.application = application
        self.widgets: list[QWidget] = []
        self._controllers: list[WheelIntentController] = []
        self._clock = ManualClock()

    def create_controller(
        self,
        mode: PromptWheelAdjustmentMode = PromptWheelAdjustmentMode.HOVER_DWELL,
    ) -> WheelIntentController:
        """Create and own a controller using this test's manual clock."""

        controller = WheelIntentController(
            wheel_adjustment_mode=mode,
            wheel_intent_now_ms=self._clock,
        )
        self._controllers.append(controller)
        return controller

    def own(self, widget: _WidgetT) -> _WidgetT:
        """Retain one independently constructed widget for exact teardown."""

        self.widgets.append(widget)
        return widget

    def advance(self, milliseconds: int) -> None:
        """Advance wheel-intent policy time without wall-clock waiting."""

        self._clock.advance(milliseconds)

    def destroy_all(self) -> None:
        """Destroy controllers, then each independently owned widget root once."""

        for controller in reversed(self._controllers):
            destroy_qt_object(controller)
        self._controllers.clear()
        owned_widget_ids = {id(widget) for widget in self.widgets}
        roots = [
            widget
            for widget in self.widgets
            if widget.parent() is None or id(widget.parent()) not in owned_widget_ids
        ]
        for widget in reversed(roots):
            destroy_qt_object(widget)
        self.widgets.clear()


def wheel_event(widget: QWidget, *, angle_delta_y: int) -> QWheelEvent:
    """Build one wheel event at the center of a widget."""

    return wheel_event_at_viewport_point(
        widget,
        widget.rect().center(),
        angle_delta_y=angle_delta_y,
    )


def wheel_event_at_viewport_point(
    widget: QWidget,
    local_point: QPoint,
    *,
    angle_delta_y: int,
) -> QWheelEvent:
    """Build one wheel event at a specific viewport-local point."""

    return QWheelEvent(
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def hover_mouse_move(widget: QWidget, local_point: QPoint) -> QMouseEvent:
    """Build one passive hover move event with no pressed buttons."""

    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def first_numeric_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first prompt token that exposes numeric wheel controls."""

    for token in surface_for(box).projection_document().tokens:
        if token.kind in {
            PromptProjectionTokenKind.EMPHASIS,
            PromptProjectionTokenKind.LORA,
        }:
            return token
        if (
            token.kind is PromptProjectionTokenKind.WILDCARD
            and token.wildcard_can_step_tag
        ):
            return token
    raise AssertionError("expected numeric prompt token")


def numeric_tokens(box: PromptEditor) -> tuple[PromptProjectionToken, ...]:
    """Return prompt tokens that expose numeric wheel controls."""

    return tuple(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind
        in {
            PromptProjectionTokenKind.EMPHASIS,
            PromptProjectionTokenKind.LORA,
        }
        or (
            token.kind is PromptProjectionTokenKind.WILDCARD
            and token.wildcard_can_step_tag
        )
    )


def numeric_wildcard_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first numeric wildcard token from a prompt editor."""

    for token in surface_for(box).projection_document().tokens:
        if token.kind is PromptProjectionTokenKind.WILDCARD:
            assert token.wildcard_can_step_tag is True
            return token
    raise AssertionError("expected wildcard token")


def reveal_numeric_token_controls(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> QPoint:
    """Reveal numeric token controls without waiting for wheel dwell."""

    application = QApplication.instance()
    assert isinstance(application, QApplication)
    controls = token_weight_controls_for(box)
    token_rect = surface_for(box).token_anchor_rect(token)
    assert token_rect is not None
    token_point = token_rect.center().toPoint()
    reset_point = QPoint(
        max(1, box.viewport().width() - 3),
        max(1, box.viewport().height() - 3),
    )
    QTest.mouseMove(box.viewport(), reset_point)
    process_events(application, cycles=8)
    QTest.mouseMove(box.viewport(), token_point)
    process_events(application, cycles=8)
    controls._set_pointer_from_viewport(QPointF(token_point))  # noqa: SLF001
    controls._record_wheel_intent_pointer_from_viewport(  # noqa: SLF001
        hover_mouse_move(box.viewport(), token_point)
    )
    controls.refresh_geometry()
    process_events(application, cycles=8)
    return token_point


__all__ = [
    "WheelIntentOwner",
    "first_numeric_token",
    "hover_mouse_move",
    "numeric_tokens",
    "numeric_wildcard_token",
    "reveal_numeric_token_controls",
    "wheel_event",
    "wheel_event_at_viewport_point",
]
