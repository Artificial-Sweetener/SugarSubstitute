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

"""Provide shared real-widget boundaries for wheel-intent integration tests."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QEnterEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSlider, QWidget

from substitute.application.node_behavior import NodeBehaviorService
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)
from substitute.presentation.widgets.wheel_intent import (
    WheelIntentArbiter,
    WheelIntentTarget,
    WheelIntentTargetKind,
)
from substitute.presentation.widgets.wheel_permission import set_wheel_intent_permission
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    surface_for,
    token_weight_controls_for,
)
from tests.support.execution.runtime_support import (
    immediate_editor_panel_execution_factories,
)
from tests.support.localization import empty_node_presentation_service


class _EmptyNodeDefinitionGateway:
    """Return empty node definitions for editor-panel construction."""

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no live node definition data for the requested class."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no required live node definition data for the requested class."""

        _ = node_class
        return {}


def _wheel_event(widget: QWidget, *, angle_delta_y: int) -> QWheelEvent:
    """Build one wheel event at the center of a widget."""

    local_point = widget.rect().center()
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


def _wheel_event_at_viewport_point(
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


def _hover_mouse_move(widget: QWidget, local_point: QPoint) -> QMouseEvent:
    """Build one passive hover move event with no pressed buttons."""

    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _send_pointer_enter(widget: QWidget) -> None:
    """Send pointer arrival without a mouse-move event."""

    local_point = widget.rect().center()
    global_point = widget.mapToGlobal(local_point)
    QApplication.sendEvent(
        widget,
        QEnterEvent(
            QPointF(local_point),
            QPointF(local_point),
            QPointF(global_point),
        ),
    )


def _editor_panel_for_wheel_intent_tests() -> EditorPanel:
    """Build a real editor panel with inert collaborators for widget wiring tests."""

    node_definition_gateway = _EmptyNodeDefinitionGateway()
    return EditorPanel(
        node_definition_gateway=node_definition_gateway,
        prompt_autocomplete_gateway=SimpleNamespace(),
        prompt_wildcard_catalog_gateway=SimpleNamespace(),
        node_behavior_service=NodeBehaviorService(
            node_definition_gateway=node_definition_gateway
        ),
        node_presentation_service=empty_node_presentation_service(),
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )


def _numeric_target(widget: QWidget) -> WheelIntentTarget:
    """Return the arbiter target for one numeric widget."""

    return WheelIntentTarget(
        kind=WheelIntentTargetKind.NUMERIC_ADJUSTMENT,
        widget=widget,
        identity=("numeric", id(widget)),
    )


def _install_numeric_wheel_permission(
    widget: QWidget,
    arbiter: WheelIntentArbiter,
    target: WheelIntentTarget,
    timestamp: Callable[[], int],
) -> None:
    """Install numeric wheel permission backed by one test arbiter."""

    def allow_wheel(_widget: QWidget, _event: QWheelEvent) -> bool:
        owner = arbiter.wheel_owner_for_event(
            target=target,
            timestamp_ms=timestamp(),
        )
        return owner == target

    set_wheel_intent_permission(widget, allow_wheel)


def _arm_numeric_wheel_target(
    widget: QWidget,
    arbiter: WheelIntentArbiter,
    target: WheelIntentTarget,
    timestamp_ms: int,
) -> int:
    """Arm numeric wheel intent and return a timestamp past dwell."""

    arbiter.clear_gesture()
    arbiter.handle_pointer_move(
        global_position=widget.mapToGlobal(widget.rect().center()),
        target=target,
        timestamp_ms=timestamp_ms,
    )
    return timestamp_ms + 400


def _bind_spinner_slider_field(
    field: QWidget,
    *,
    value: float | int,
    key: str = "strength",
) -> SimpleNamespace:
    """Bind one spinner-slider composite to a fake cube-state input."""

    metadata = {"node_name": "Node", "key": key}
    field.setProperty("input_metadata", metadata)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"Node": {"inputs": {key: value}}}},
        dirty=False,
    )
    EditorPanelFieldStateController().bind_node_widget_state(
        field, cube_state, metadata
    )
    return cube_state


def _assert_slider_wheel_does_not_edit_bound_field(
    *,
    app: QApplication,
    panel: EditorPanel,
    field: QWidget,
    cube_state: SimpleNamespace,
    key: str = "strength",
) -> None:
    """Assert wheel input over a spinner-slider slider is ignored."""

    panel.configure_wheel_intent_for_widget(field)
    field.show()
    process_events(app)

    slider = field.findChild(QSlider)
    assert slider is not None
    spinbox = getattr(field, "spinbox")
    initial_slider_value = slider.value()
    initial_spinbox_value = spinbox.value()
    initial_buffer_value = cube_state.buffer["nodes"]["Node"]["inputs"][key]

    wheel_event = _wheel_event(slider, angle_delta_y=120)
    QApplication.sendEvent(slider, wheel_event)
    process_events(app)

    assert not wheel_event.isAccepted()
    assert slider.value() == initial_slider_value
    assert spinbox.value() == initial_spinbox_value
    assert cube_state.buffer["nodes"]["Node"]["inputs"][key] == initial_buffer_value
    assert cube_state.dirty is False


def _prompt_scroll_target(widget: QWidget) -> WheelIntentTarget:
    """Return the arbiter target for one prompt editor."""

    return WheelIntentTarget(
        kind=WheelIntentTargetKind.PROMPT_SCROLL,
        widget=widget,
        identity=("prompt", id(widget)),
    )


def _install_prompt_scroll_permission(
    box: PromptEditor,
    arbiter: WheelIntentArbiter,
    timestamp: Callable[[], int],
) -> None:
    """Install prompt scroll permission backed by one test arbiter."""

    target = _prompt_scroll_target(box)

    def allow_wheel(_widget: QWidget, _event: QWheelEvent) -> bool:
        owner = arbiter.wheel_owner_for_event(
            target=target,
            timestamp_ms=timestamp(),
        )
        return owner == target

    set_wheel_intent_permission(box, allow_wheel)


def _arm_prompt_scroll(
    box: PromptEditor,
    arbiter: WheelIntentArbiter,
    timestamp_ms: int,
) -> int:
    """Arm prompt scroll intent and return a timestamp past dwell."""

    arbiter.clear_gesture()
    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(box.viewport().rect().center()),
        target=_prompt_scroll_target(box),
        timestamp_ms=timestamp_ms,
    )
    return timestamp_ms + 400


def _prompt_shell_viewport(box: PromptEditor) -> QWidget:
    """Return the real host viewport watched by QFluent's scroll delegate."""

    return box.findChild(QWidget, "qt_scrollarea_viewport") or box.viewport()


def _first_weighted_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first weighted token from a prompt editor."""

    app = ensure_qapp()
    for _attempt in range(20):
        box.flush_pending_projection_update(reason="test_first_weighted_token")
        surface = surface_for(box)
        layout = cast(Any, surface)._layout
        for token in surface.projection_document().tokens:
            if token.kind in {
                PromptProjectionTokenKind.EMPHASIS,
                PromptProjectionTokenKind.LORA,
            }:
                return cast(
                    PromptProjectionToken,
                    layout.frame.paint_input.effective_token(token.token_id) or token,
                )
        process_events(app)
    raise AssertionError("expected weighted token")


def _token_target(box: PromptEditor, token: PromptProjectionToken) -> WheelIntentTarget:
    """Return the arbiter target for one weighted prompt token."""

    return WheelIntentTarget(
        kind=WheelIntentTargetKind.PROMPT_WEIGHT_ADJUSTMENT,
        widget=box,
        identity=("prompt_weight", id(box), box.prompt_weight_wheel_identity(token)),
    )


def _install_token_wheel_handlers(
    box: PromptEditor,
    arbiter: WheelIntentArbiter,
    timestamp: Callable[[], int],
) -> None:
    """Install prompt-token wheel handlers backed by the real arbiter."""

    box.set_wheel_intent_token_handlers(
        token_pointer_moved=lambda token, global_position: arbiter.handle_pointer_move(
            global_position=global_position.toPoint(),
            target=_token_target(box, token),
            timestamp_ms=timestamp(),
        ),
        token_wheel_ready=lambda token, _global_position: arbiter.target_is_armed(
            _token_target(box, token),
            timestamp_ms=timestamp(),
        ),
        token_wheel_allowed=lambda token, _event: (
            arbiter.wheel_owner_for_event(
                target=_token_target(box, token),
                timestamp_ms=timestamp(),
            )
            == _token_target(box, token)
        ),
        token_wheel_activated=None,
    )


def _token_weight_wheel_owner(box: PromptEditor) -> Any:
    """Return the token-weight wheel-intent owner for focused integration checks."""

    return cast(Any, box)._wheel_controller.token_weight_wheel_intent


def _reveal_weight_controls_without_dwell(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> QPoint:
    """Reveal weighted-token controls from hover without arming wheel intent."""

    app = ensure_qapp()
    controls = token_weight_controls_for(box)
    token_rect = surface_for(box).token_anchor_rect(token)
    assert token_rect is not None
    token_point = token_rect.center().toPoint()
    reset_point = QPoint(
        max(1, box.viewport().width() - 3),
        max(1, box.viewport().height() - 3),
    )
    QTest.mouseMove(box.viewport(), reset_point)
    process_events(app)
    QTest.mouseMove(box.viewport(), token_point)
    process_events(app)
    controls._set_pointer_from_viewport(QPointF(token_point))  # noqa: SLF001
    controls.refresh_geometry()
    process_events(app)
    return token_point
