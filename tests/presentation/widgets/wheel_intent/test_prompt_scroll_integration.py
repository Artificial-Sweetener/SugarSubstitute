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

"""Test prompt viewport wheel-intent integration."""

from __future__ import annotations


from PySide6.QtCore import QEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.widgets.wheel_intent import (
    WheelIntentArbiter,
)
from substitute.presentation.widgets.wheel_permission import set_wheel_intent_permission
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.qt.lifecycle import destroy_qt_object, destroy_widget_roots
from tests.support.qt.semantic_wait import wait_for_qt_condition

from tests.presentation.widgets.wheel_intent.integration_support import (
    _arm_prompt_scroll,
    _editor_panel_for_wheel_intent_tests,
    _install_prompt_scroll_permission,
    _prompt_scroll_target,
    _prompt_shell_viewport,
    _wheel_event,
)


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

    destroy_widget_roots(widgets)


def test_focused_prompt_scrolls_without_hover_dwell() -> None:
    """Keyboard focus from explicit editing should count as prompt scroll intent."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    panel = _editor_panel_for_wheel_intent_tests()
    try:
        box = show_prompt_editor(
            widgets,
            text="\n".join(f"line {index}" for index in range(30)),
            width=320,
        )
        panel.configure_wheel_intent_for_widget(box)
        box.setFocus()
        wait_for_qt_condition(box.hasFocus)
        scrollbar = box.verticalScrollBar()
        scrollbar.setValue(0)

        host_viewport = _prompt_shell_viewport(box)
        focused_event = _wheel_event(host_viewport, angle_delta_y=-120)
        QApplication.sendEvent(host_viewport, focused_event)
        process_events(app)

        assert scrollbar.value() > 0
        assert focused_event.isAccepted()
    finally:
        if widgets:
            destroy_qt_object(widgets[0])
        destroy_qt_object(panel)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)
