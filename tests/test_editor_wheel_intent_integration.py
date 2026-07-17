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

"""Integration coverage for editor wheel-intent widget wiring."""

from __future__ import annotations

import os
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QCursor, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSlider, QWidget

from substitute.application.node_behavior import NodeBehaviorService
from substitute.presentation.editor.panel.factories.numeric_factory import (
    _build_color_slider_widget,
    _build_int_spinner_slider_widget,
    _build_spinner_slider_widget,
)
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)
from substitute.presentation.widgets.wheel_intent import (
    DEFAULT_WHEEL_GESTURE_IDLE_MS,
    WheelIntentArbiter,
    WheelIntentTarget,
    WheelIntentTargetKind,
)
from substitute.presentation.widgets import DoubleSpinBox, SeedBox, SpinBox
from substitute.presentation.widgets.wheel_permission import set_wheel_intent_permission
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
    token_weight_controls_for,
)
from tests.execution_test_helpers import immediate_editor_panel_execution_factories

_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real PromptEditor wheel-control state is verified serially outside xdist",
)


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

    QCursor.setPos(widget.mapToGlobal(widget.rect().center()))
    QApplication.sendEvent(widget, QEvent(QEvent.Type.Enter))


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


def test_spinbox_does_not_adjust_until_pointer_dwell_arms_it() -> None:
    """Numeric wheel edits should require deliberate pointer dwell."""

    app = ensure_qapp()
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    spinbox.show()
    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _numeric_target(spinbox)
    timestamp_ms = 1000

    def allow_wheel(_widget: QWidget, _event: QWheelEvent) -> bool:
        owner = arbiter.wheel_owner_for_event(
            target=target,
            timestamp_ms=timestamp_ms,
        )
        return owner == target

    set_wheel_intent_permission(spinbox, allow_wheel)

    unarmed_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, unarmed_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not unarmed_event.isAccepted()

    timestamp_ms = 2000
    arbiter.clear_gesture()
    arbiter.handle_pointer_move(
        global_position=spinbox.mapToGlobal(spinbox.rect().center()),
        target=target,
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400

    armed_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, armed_event)
    process_events(app)

    assert spinbox.value() == 6
    assert armed_event.isAccepted()

    spinbox.close()
    spinbox.deleteLater()
    process_events(app)


def test_spinbox_wheel_edit_does_not_select_line_edit_text() -> None:
    """Allowed integer wheel edits should not enter text-selection state."""

    app = ensure_qapp()
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    spinbox.show()
    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _numeric_target(spinbox)
    timestamp_ms = 1000
    _install_numeric_wheel_permission(
        spinbox,
        arbiter,
        target,
        lambda: timestamp_ms,
    )
    timestamp_ms = _arm_numeric_wheel_target(
        spinbox,
        arbiter,
        target,
        timestamp_ms,
    )

    wheel_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, wheel_event)
    process_events(app)

    assert spinbox.value() == 6
    assert wheel_event.isAccepted()
    assert not spinbox.lineEdit().hasSelectedText()
    assert spinbox.lineEdit().selectedText() == ""

    spinbox.close()
    spinbox.deleteLater()
    process_events(app)


def test_doublespinbox_wheel_edit_does_not_select_line_edit_text() -> None:
    """Allowed floating wheel edits should not enter text-selection state."""

    app = ensure_qapp()
    spinbox = DoubleSpinBox()
    spinbox.setRange(0.0, 10.0)
    spinbox.setSingleStep(0.25)
    spinbox.setValue(5.0)
    spinbox.show()
    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _numeric_target(spinbox)
    timestamp_ms = 1000
    _install_numeric_wheel_permission(
        spinbox,
        arbiter,
        target,
        lambda: timestamp_ms,
    )
    timestamp_ms = _arm_numeric_wheel_target(
        spinbox,
        arbiter,
        target,
        timestamp_ms,
    )

    wheel_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, wheel_event)
    process_events(app)

    assert spinbox.value() == 5.25
    assert wheel_event.isAccepted()
    assert not spinbox.lineEdit().hasSelectedText()
    assert spinbox.lineEdit().selectedText() == ""

    spinbox.close()
    spinbox.deleteLater()
    process_events(app)


def test_allowed_numeric_wheel_preserves_existing_keyboard_focus() -> None:
    """Allowed spin-box wheel input should not steal focus from another widget."""

    app = ensure_qapp()
    focus_owner = QWidget()
    focus_owner.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    focus_owner.show()
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    spinbox.show()
    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _numeric_target(spinbox)
    timestamp_ms = 1000
    _install_numeric_wheel_permission(
        spinbox,
        arbiter,
        target,
        lambda: timestamp_ms,
    )
    timestamp_ms = _arm_numeric_wheel_target(
        spinbox,
        arbiter,
        target,
        timestamp_ms,
    )
    process_events(app)
    focus_owner.setFocus()
    process_events(app)
    initial_focus = QApplication.focusWidget()

    wheel_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, wheel_event)
    process_events(app)

    assert spinbox.value() == 6
    assert wheel_event.isAccepted()
    if initial_focus is focus_owner:
        assert QApplication.focusWidget() is focus_owner
    assert QApplication.focusWidget() is not spinbox
    assert QApplication.focusWidget() is not spinbox.lineEdit()
    assert not spinbox.lineEdit().hasSelectedText()
    assert spinbox.lineEdit().selectedText() == ""

    spinbox.close()
    spinbox.deleteLater()
    focus_owner.close()
    focus_owner.deleteLater()
    process_events(app)


def test_numeric_wheel_widgets_do_not_use_wheel_focus_policy() -> None:
    """Wheel-adjustable numeric widgets should not focus from blocked wheel input."""

    app = ensure_qapp()
    seedbox = SeedBox()
    widgets = [SpinBox(), DoubleSpinBox(), seedbox]

    for widget in widgets:
        assert widget.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert seedbox.line_edit.focusPolicy() == Qt.FocusPolicy.StrongFocus

    for widget in widgets:
        widget.deleteLater()
    process_events(app)


def test_blocked_numeric_wheel_preserves_existing_keyboard_focus() -> None:
    """Blocked spin-box wheel input should not steal focus from another widget."""

    app = ensure_qapp()
    focus_owner = QWidget()
    focus_owner.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    focus_owner.show()
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    spinbox.show()
    set_wheel_intent_permission(spinbox, lambda _widget, _event: False)
    process_events(app)
    focus_owner.setFocus()
    process_events(app)
    initial_focus = QApplication.focusWidget()

    blocked_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, blocked_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not blocked_event.isAccepted()
    if initial_focus is focus_owner:
        assert QApplication.focusWidget() is focus_owner
    assert QApplication.focusWidget() is not spinbox

    spinbox.close()
    spinbox.deleteLater()
    focus_owner.close()
    focus_owner.deleteLater()
    process_events(app)


def test_premature_spinbox_wheel_restarts_dwell_for_next_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Early spin-box wheel attempts should require a fresh dwell, not a reset."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    clock_ms = [0]
    controller = cast(Any, panel)._wheel_intent_controller
    monkeypatch.setattr(controller, "_wheel_intent_now_ms", lambda: clock_ms[0])
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    panel.configure_wheel_intent_for_widget(spinbox)
    spinbox.show()
    process_events(app)

    QApplication.sendEvent(
        spinbox,
        _hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    process_events(app)
    premature_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, premature_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not premature_event.isAccepted()

    clock_ms[0] = 350
    still_too_early_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, still_too_early_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not still_too_early_event.isAccepted()

    clock_ms[0] = 650
    restarted_dwell_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, restarted_dwell_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not restarted_dwell_event.isAccepted()

    clock_ms[0] = 1100
    allowed_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, allowed_event)
    process_events(app)

    assert spinbox.value() == 6
    assert allowed_event.isAccepted()

    spinbox.close()
    spinbox.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


def test_spinbox_target_to_target_dwell_without_editor_background_reset() -> None:
    """Moving between spinboxes should let the new target dwell directly."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    first = SpinBox()
    first.setRange(0, 10)
    first.setValue(5)
    second = SpinBox()
    second.setRange(0, 10)
    second.setValue(2)
    panel.configure_wheel_intent_for_widget(first)
    panel.configure_wheel_intent_for_widget(second)
    first.show()
    second.show()
    process_events(app)

    QApplication.sendEvent(
        first,
        _hover_mouse_move(first, first.rect().center()),
    )
    process_events(app)
    QTest.qWait(450)
    process_events(app)
    first_event = _wheel_event(first, angle_delta_y=120)
    QApplication.sendEvent(first, first_event)
    process_events(app)

    assert first.value() == 6
    assert first_event.isAccepted()

    QApplication.sendEvent(
        second,
        _hover_mouse_move(second, second.rect().center()),
    )
    process_events(app)
    QTest.qWait(450)
    process_events(app)
    second_event = _wheel_event(second, angle_delta_y=120)
    QApplication.sendEvent(second, second_event)
    process_events(app)

    assert second.value() == 3
    assert second_event.isAccepted()

    first.close()
    first.deleteLater()
    second.close()
    second.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


def test_spinbox_enter_without_mouse_move_starts_wheel_dwell() -> None:
    """Pointer enter should start dwell even when Qt sends no mouse move."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    panel.configure_wheel_intent_for_widget(spinbox)
    spinbox.show()
    process_events(app)

    _send_pointer_enter(spinbox)
    process_events(app)
    QTest.qWait(450)
    process_events(app)
    wheel_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, wheel_event)
    process_events(app)

    assert spinbox.value() == 6
    assert wheel_event.isAccepted()

    spinbox.close()
    spinbox.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


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


def test_float_spinner_slider_ignores_slider_wheel_input() -> None:
    """Float spinner-slider sliders should not wheel-edit values."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    field = _build_spinner_slider_widget(
        panel,
        0.5,
        0.0,
        1.0,
        0.1,
    )
    cube_state = _bind_spinner_slider_field(field, value=0.5)

    _assert_slider_wheel_does_not_edit_bound_field(
        app=app,
        panel=panel,
        field=field,
        cube_state=cube_state,
    )

    field.close()
    field.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


def test_integer_spinner_slider_ignores_slider_wheel_input() -> None:
    """Integer spinner-slider sliders should not wheel-edit values."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    field = _build_int_spinner_slider_widget(
        panel,
        5,
        0,
        10,
        1,
    )
    cube_state = _bind_spinner_slider_field(field, value=5)

    _assert_slider_wheel_does_not_edit_bound_field(
        app=app,
        panel=panel,
        field=field,
        cube_state=cube_state,
    )

    field.close()
    field.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


def test_color_spinner_slider_ignores_slider_wheel_input() -> None:
    """Color slider composites should not wheel-edit through their slider."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    field = _build_color_slider_widget(
        panel,
        0.5,
        0.0,
        1.0,
        0.1,
    )
    cube_state = _bind_spinner_slider_field(field, value=0.5)

    _assert_slider_wheel_does_not_edit_bound_field(
        app=app,
        panel=panel,
        field=field,
        cube_state=cube_state,
    )

    field.close()
    field.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


def test_spinner_slider_spinbox_wheel_keeps_dwell_intent_and_syncs_slider() -> None:
    """Spinner-slider spinboxes should keep dwell-gated wheel editing."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    field = _build_spinner_slider_widget(
        panel,
        0.5,
        0.0,
        1.0,
        0.1,
    )
    _bind_spinner_slider_field(field, value=0.5)
    panel.configure_wheel_intent_for_widget(field)
    field.show()
    process_events(app)
    spinbox = cast(Any, field).spinbox
    slider = field.findChild(QSlider)
    assert slider is not None

    blocked_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, blocked_event)
    process_events(app)

    assert not blocked_event.isAccepted()
    assert spinbox.value() == 0.5
    assert slider.value() == 5

    QApplication.sendEvent(
        spinbox,
        _hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    process_events(app)
    QTest.qWait(450)
    process_events(app)

    allowed_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, allowed_event)
    process_events(app)

    assert allowed_event.isAccepted()
    assert spinbox.value() == 0.6
    assert slider.value() == 6

    field.close()
    field.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


def test_spinner_slider_hover_move_does_not_adjust_or_dirty_state() -> None:
    """Passive hover over a spinner slider should not behave like a drag."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    field = _build_spinner_slider_widget(
        panel,
        0.5,
        0.0,
        1.0,
        0.1,
    )
    field.setProperty("input_metadata", {"node_name": "Node", "key": "strength"})
    cube_state = SimpleNamespace(
        buffer={"nodes": {"Node": {"inputs": {"strength": 0.5}}}},
        dirty=False,
    )
    EditorPanelFieldStateController().bind_node_widget_state(
        field,
        cube_state,
        {"node_name": "Node", "key": "strength"},
    )
    panel.configure_wheel_intent_for_widget(field)
    field.show()
    process_events(app)

    slider = field.findChild(QSlider)
    assert slider is not None
    spinbox = cast(Any, field).spinbox
    initial_slider_value = slider.value()
    initial_spinbox_value = spinbox.value()
    hover_point = QPoint(slider.width() - 2, slider.height() // 2)

    QApplication.sendEvent(slider, _hover_mouse_move(slider, hover_point))
    process_events(app)

    assert slider.value() == initial_slider_value
    assert spinbox.value() == initial_spinbox_value
    assert cube_state.buffer["nodes"]["Node"]["inputs"]["strength"] == 0.5
    assert cube_state.dirty is False

    spinbox.setValue(0.7)
    process_events(app)

    assert slider.value() == 7

    field.close()
    field.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


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


def test_prompt_scroll_requires_pointer_dwell_before_internal_scroll() -> None:
    """Prompt editors should not steal wheel input before deliberate dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    target = _prompt_scroll_target(box)
    timestamp_ms = 1000

    def allow_wheel(_widget: QWidget, _event: QWheelEvent) -> bool:
        owner = arbiter.wheel_owner_for_event(
            target=target,
            timestamp_ms=timestamp_ms,
        )
        return owner == target

    set_wheel_intent_permission(box, allow_wheel)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    unarmed_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), unarmed_event)
    process_events(app)

    assert scrollbar.value() == 0
    assert not unarmed_event.isAccepted()

    timestamp_ms = 2000
    arbiter.clear_gesture()
    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(box.viewport().rect().center()),
        target=target,
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400

    armed_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), armed_event)
    process_events(app)

    assert scrollbar.value() > 0
    assert armed_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_focused_prompt_scrolls_without_hover_dwell() -> None:
    """Keyboard focus from explicit editing should count as prompt scroll intent."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    panel = _editor_panel_for_wheel_intent_tests()
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    panel.configure_wheel_intent_for_widget(box)
    box.setFocus()
    process_events(app)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    host_viewport = _prompt_shell_viewport(box)
    focused_event = _wheel_event(host_viewport, angle_delta_y=-120)
    QApplication.sendEvent(host_viewport, focused_event)
    process_events(app)

    assert scrollbar.value() > 0
    assert focused_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    panel.close()
    panel.deleteLater()
    process_events(app)


def test_prompt_host_wheel_denial_does_not_scroll_surface() -> None:
    """Host-viewport wheel input should not bypass prompt scroll permission."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    host_viewport = _prompt_shell_viewport(box)
    denied_event = _wheel_event(host_viewport, angle_delta_y=-120)
    QApplication.sendEvent(host_viewport, denied_event)
    process_events(app)

    assert scrollbar.value() == 0
    assert not denied_event.isAccepted()
    assert surface_for(box)._wheel_handler._boundary_spill is None  # noqa: SLF001

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_prompt_host_wheel_denial_forwards_to_editor_scroll_owner() -> None:
    """Denied host-viewport prompt wheel input should bubble deliberately."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    host = widgets[0]
    forwarded_events: list[QWheelEvent] = []

    def handle_external_wheel(event: QWheelEvent) -> None:
        forwarded_events.append(event)
        event.accept()

    setattr(host, "handle_external_wheel", handle_external_wheel)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    host_viewport = _prompt_shell_viewport(box)
    denied_event = _wheel_event(host_viewport, angle_delta_y=-120)
    QApplication.sendEvent(host_viewport, denied_event)
    process_events(app)

    assert scrollbar.value() == 0
    assert denied_event.isAccepted()
    assert forwarded_events == [denied_event]

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_prompt_bottom_boundary_consumes_same_burst_spill() -> None:
    """Immediate down-wheel spill after reaching bottom should stay in the prompt."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    timestamp_ms = _arm_prompt_scroll(box, arbiter, timestamp_ms)

    scrollbar.setValue(scrollbar.maximum() - 1)
    to_bottom_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), to_bottom_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.maximum()
    assert to_bottom_event.isAccepted()

    timestamp_ms += 10
    spill_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), spill_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.maximum()
    assert spill_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_prompt_top_boundary_consumes_same_burst_spill() -> None:
    """Immediate up-wheel spill after reaching top should stay in the prompt."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    timestamp_ms = _arm_prompt_scroll(box, arbiter, timestamp_ms)

    scrollbar.setValue(scrollbar.minimum() + 1)
    to_top_event = _wheel_event(box.viewport(), angle_delta_y=120)
    QApplication.sendEvent(box.viewport(), to_top_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.minimum()
    assert to_top_event.isAccepted()

    timestamp_ms += 10
    spill_event = _wheel_event(box.viewport(), angle_delta_y=120)
    QApplication.sendEvent(box.viewport(), spill_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.minimum()
    assert spill_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_prompt_boundary_wheel_after_idle_is_not_spill() -> None:
    """A fresh boundary wheel gesture after idle should be allowed to bubble."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    timestamp_ms = _arm_prompt_scroll(box, arbiter, timestamp_ms)

    scrollbar.setValue(scrollbar.maximum() - 1)
    to_bottom_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), to_bottom_event)
    process_events(app)
    assert to_bottom_event.isAccepted()

    timestamp_ms += 10
    spill_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), spill_event)
    process_events(app)
    assert spill_event.isAccepted()

    QTest.qWait(DEFAULT_WHEEL_GESTURE_IDLE_MS + 50)
    timestamp_ms += DEFAULT_WHEEL_GESTURE_IDLE_MS + 50
    after_idle_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), after_idle_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.maximum()
    assert not after_idle_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_prompt_boundary_direction_change_scrolls_prompt_back() -> None:
    """Opposite-direction input at a boundary should scroll prompt content."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    timestamp_ms = _arm_prompt_scroll(box, arbiter, timestamp_ms)

    scrollbar.setValue(scrollbar.maximum() - 1)
    to_bottom_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), to_bottom_event)
    process_events(app)
    assert scrollbar.value() == scrollbar.maximum()
    assert to_bottom_event.isAccepted()

    timestamp_ms += 10
    up_event = _wheel_event(box.viewport(), angle_delta_y=120)
    QApplication.sendEvent(box.viewport(), up_event)
    process_events(app)

    assert scrollbar.value() < scrollbar.maximum()
    assert up_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_unarmed_prompt_boundary_wheel_does_not_create_spill() -> None:
    """Unarmed boundary input should not be consumed or seed spill state."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())

    boundary_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), boundary_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.maximum()
    assert not boundary_event.isAccepted()
    assert surface_for(box)._wheel_handler._boundary_spill is None  # noqa: SLF001

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_prompt_boundary_spill_clears_on_pointer_leave() -> None:
    """Prompt-local spill suppression should end when the pointer leaves."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_prompt_scroll_permission(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    timestamp_ms = _arm_prompt_scroll(box, arbiter, timestamp_ms)

    scrollbar.setValue(scrollbar.maximum() - 1)
    to_bottom_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), to_bottom_event)
    process_events(app)
    assert to_bottom_event.isAccepted()

    timestamp_ms += 10
    spill_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), spill_event)
    process_events(app)
    assert spill_event.isAccepted()

    QApplication.sendEvent(box.viewport(), QEvent(QEvent.Type.Leave))
    process_events(app)

    timestamp_ms += 10
    after_leave_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), after_leave_event)
    process_events(app)

    assert scrollbar.value() == scrollbar.maximum()
    assert not after_leave_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


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
                    layout.effective_token_for_paint(token.token_id) or token,
                )
        process_events(app, cycles=1)
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
    process_events(app, cycles=8)
    QTest.mouseMove(box.viewport(), token_point)
    process_events(app, cycles=8)
    controls._set_pointer_from_viewport(QPointF(token_point))  # noqa: SLF001
    controls.refresh_geometry()
    process_events(app, cycles=8)
    return token_point


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_controls_reveal_on_hover_without_token_dwell() -> None:
    """Weighted-token hover controls should not require wheel dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controls = token_weight_controls_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)

    _reveal_weight_controls_without_dwell(box, token)

    assert controls.visible_token is not None
    assert controls.visible_token.token_id == token.token_id
    assert controls.isVisible()
    assert controls.increase_rect is not None
    assert controls.decrease_rect is not None

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_manual_arrow_adjusts_without_token_dwell() -> None:
    """Manual weighted-token arrows should work independently of wheel dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controls = token_weight_controls_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)

    _reveal_weight_controls_without_dwell(box, token)
    assert controls.increase_rect is not None

    QTest.mouseClick(
        controls,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
    )
    process_events(app)

    assert box.toPlainText() != "(cat:1.20)"

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_phase25_1_prompt_weight_manual_arrow_is_undoable() -> None:
    """Phase 25.1 freezes manual token-control undo before owner extraction."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controls = token_weight_controls_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)

    _reveal_weight_controls_without_dwell(box, token)
    assert controls.increase_rect is not None

    QTest.mouseClick(
        controls,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
    )
    process_events(app)

    assert box.toPlainText() != "(cat:1.20)"

    box.undo()
    process_events(app)

    assert box.toPlainText() == "(cat:1.20)"

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_phase25_1_prompt_weight_hide_linger_keeps_visible_controls() -> None:
    """Phase 25.1 freezes hover hide-linger behavior before owner extraction."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controls = token_weight_controls_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)

    _reveal_weight_controls_without_dwell(box, token)
    assert controls.isVisible()

    controls.leaveEvent(QEvent(QEvent.Type.Leave))
    process_events(app)

    assert controls.isVisible()
    assert cast(Any, controls)._gestures.hide_timeout.isActive() is True
    assert controls.visible_token is not None

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_phase25_1_prompt_weight_invalid_exact_edit_cancels_without_mutation() -> None:
    """Phase 25.1 freezes invalid exact-weight handling before owner extraction."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controls = token_weight_controls_for(box)
    token = _first_weighted_token(box)

    cast(Any, controls)._start_exact_weight_edit(token)
    cast(Any, controls)._exact_edit_host.update_exact_weight_edit(
        buffer_text="abc",
        caret_index=3,
        select_all=False,
    )
    cast(Any, controls)._finalize_exact_weight_edit()
    process_events(app)

    assert box.toPlainText() == "(cat:1.20)"
    assert cast(Any, controls)._exact_edit_host.exact_weight_edit_active() is False

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_phase25_1_prompt_weight_manual_arrow_preserves_scroll_position() -> None:
    """Phase 25.1 freezes scroll preservation around overlay-owned commits."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    text = "\n".join(f"line {index}" for index in range(18)) + "\n(cat:1.20)"
    box = show_prompt_editor(widgets, text=text, width=320, height=160)
    controls = token_weight_controls_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    scrollbar = box.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    process_events(app, cycles=8)
    token = _first_weighted_token(box)

    _reveal_weight_controls_without_dwell(box, token)
    assert controls.increase_rect is not None
    preserved_scroll_value = scrollbar.value()

    QTest.mouseClick(
        controls,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
    )
    process_events(app)

    assert box.toPlainText() != text
    assert scrollbar.value() == preserved_scroll_value

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_click_reports_token_wheel_activation() -> None:
    """Clicking a weighted token should report explicit wheel activation."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    activated_token_ids: list[str] = []
    box.set_wheel_intent_token_handlers(
        token_pointer_moved=None,
        token_wheel_ready=None,
        token_wheel_allowed=None,
        token_wheel_activated=lambda token, _global_position: (
            activated_token_ids.append(token.token_id)
        ),
    )
    token = _first_weighted_token(box)
    token_point = _reveal_weight_controls_without_dwell(box, token)

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        token_point,
    )
    process_events(app)

    assert activated_token_ids == [token.token_id]

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_wheel_does_not_adjust_before_token_dwell() -> None:
    """Weighted-token wheel adjustment should wait for deliberate dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)
    token_point = _reveal_weight_controls_without_dwell(box, token)
    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(token_point),
        target=_token_target(box, token),
        timestamp_ms=timestamp_ms,
    )

    unarmed_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), unarmed_event)
    process_events(app)

    assert box.toPlainText() == "(cat:1.20)"
    assert not unarmed_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_wheel_adjusts_after_token_dwell() -> None:
    """Weighted-token wheel adjustment should work after deliberate dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)
    token_point = _reveal_weight_controls_without_dwell(box, token)
    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(token_point),
        target=_token_target(box, token),
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400

    armed_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), armed_event)
    process_events(app)

    assert box.toPlainText() != "(cat:1.20)"
    assert armed_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_dwell_accents_emphasis_parentheses() -> None:
    """Dwell-owned wheel readiness should light the emphasis decoration."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    surface = surface_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)
    token_point = _reveal_weight_controls_without_dwell(box, token)
    surface.set_overlay_emphasis_accent_range(None)
    process_events(app)
    assert _first_weighted_token(box).decoration_accented is False

    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(token_point),
        target=_token_target(box, token),
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400
    _token_weight_wheel_owner(box).refresh_ready_token()
    process_events(app)

    assert _first_weighted_token(box).decoration_accented is True

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_dwell_accents_when_pointer_is_over_content_text() -> None:
    """Dwell readiness should survive hover refresh outside the control zone."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    panel = _editor_panel_for_wheel_intent_tests()
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    panel.configure_wheel_intent_for_widget(box)
    controls = token_weight_controls_for(box)
    surface = surface_for(box)
    token = _first_weighted_token(box)
    assert token.content_start is not None
    assert token.content_end is not None
    content_fragments = surface.source_range_fragments(
        start=token.content_start,
        end=token.content_end,
    )
    assert content_fragments
    content_point = content_fragments[0].center().toPoint()

    QApplication.sendEvent(
        box.viewport(), _hover_mouse_move(box.viewport(), content_point)
    )
    process_events(app, cycles=5)

    assert controls.visible_token is None
    assert _token_weight_wheel_owner(box).candidate_token is not None
    assert _first_weighted_token(box).decoration_accented is False

    QTest.qWait(450)
    process_events(app, cycles=5)

    assert _first_weighted_token(box).decoration_accented is True

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    panel.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_dwell_accent_recovers_after_idle_wheel_latch() -> None:
    """Expired wheel ownership should not block later prompt-weight dwell accent."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    surface = surface_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400, gesture_idle_ms=250)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)
    token_point = _reveal_weight_controls_without_dwell(box, token)
    target = _token_target(box, token)
    surface.set_overlay_emphasis_accent_range(None)
    process_events(app)
    assert _first_weighted_token(box).decoration_accented is False

    timestamp_ms = 1100
    assert arbiter.wheel_owner_for_event(target=target, timestamp_ms=timestamp_ms) == (
        WheelIntentTarget.editor_scroll()
    )

    timestamp_ms = 1400
    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(token_point),
        target=target,
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400
    _token_weight_wheel_owner(box).refresh_ready_token()
    process_events(app)

    assert _first_weighted_token(box).decoration_accented is True

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_dwell_accents_when_pointer_is_over_control_activation() -> None:
    """Dwell readiness should use the same activation area as visible controls."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controls = token_weight_controls_for(box)
    surface = surface_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)
    _reveal_weight_controls_without_dwell(box, token)
    assert controls.increase_rect is not None
    surface.set_overlay_emphasis_accent_range(None)
    process_events(app)
    assert _first_weighted_token(box).decoration_accented is False

    control_point = controls.increase_rect.center()
    controls._gestures.pointer_host_position = QPointF(control_point)  # noqa: SLF001
    global_position = controls._global_position_from_host_position(  # noqa: SLF001
        QPointF(control_point)
    )
    arbiter.handle_pointer_move(
        global_position=global_position.toPoint(),
        target=_token_target(box, token),
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400
    _token_weight_wheel_owner(box).refresh_ready_token()
    process_events(app)

    assert _first_weighted_token(box).decoration_accented is True

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_wheel_stays_latched_when_emphasis_reaches_neutral() -> None:
    """Wheel intent should survive the synthetic neutral token rebuilt at 1.00."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.05)", width=320)
    controls = token_weight_controls_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)
    token_point = _reveal_weight_controls_without_dwell(box, token)
    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(token_point),
        target=_token_target(box, token),
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400

    assert controls.increase_rect is not None
    neutral_event = _wheel_event_at_viewport_point(
        controls,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    QApplication.sendEvent(controls, neutral_event)
    process_events(app)

    assert neutral_event.isAccepted()
    assert box.toPlainText() == "cat"
    assert controls.visible_token is not None
    assert controls.visible_token.synthetic is True
    assert controls.visible_token.value_text == "1.00"

    assert controls.increase_rect is not None
    below_neutral_event = _wheel_event_at_viewport_point(
        controls,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    QApplication.sendEvent(controls, below_neutral_event)
    process_events(app)

    assert below_neutral_event.isAccepted()
    assert box.toPlainText() == "(cat:0.95)"

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)


@_REAL_PROMPT_EDITOR_WHEEL_CONTROL_XDIST_SKIP
def test_prompt_weight_wheel_can_restore_emphasis_from_latched_neutral() -> None:
    """Wheel intent should also remain valid when leaving neutral upward."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    box = show_prompt_editor(widgets, text="(cat:1.05)", width=320)
    controls = token_weight_controls_for(box)
    arbiter = WheelIntentArbiter(dwell_ms=400)
    timestamp_ms = 1000
    _install_token_wheel_handlers(box, arbiter, lambda: timestamp_ms)
    token = _first_weighted_token(box)
    token_point = _reveal_weight_controls_without_dwell(box, token)
    arbiter.handle_pointer_move(
        global_position=box.viewport().mapToGlobal(token_point),
        target=_token_target(box, token),
        timestamp_ms=timestamp_ms,
    )
    timestamp_ms += 400

    assert controls.increase_rect is not None
    neutral_event = _wheel_event_at_viewport_point(
        controls,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    QApplication.sendEvent(controls, neutral_event)
    process_events(app)

    assert neutral_event.isAccepted()
    assert box.toPlainText() == "cat"
    assert controls.visible_token is not None
    assert controls.visible_token.synthetic is True

    assert controls.increase_rect is not None
    above_neutral_event = _wheel_event_at_viewport_point(
        controls,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=120,
    )
    QApplication.sendEvent(controls, above_neutral_event)
    process_events(app)

    assert above_neutral_event.isAccepted()
    assert box.toPlainText() == "(cat:1.05)"

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    process_events(app)
