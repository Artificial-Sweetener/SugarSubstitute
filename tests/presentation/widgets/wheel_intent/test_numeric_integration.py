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

"""Test numeric editor wheel-intent integration."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.widgets.wheel_intent import (
    WheelIntentArbiter,
)
from substitute.presentation.widgets import DoubleSpinBox, SeedBox, SpinBox
from substitute.presentation.widgets.wheel_permission import set_wheel_intent_permission
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
)

from tests.presentation.widgets.wheel_intent.integration_support import (
    _arm_numeric_wheel_target,
    _editor_panel_for_wheel_intent_tests,
    _hover_mouse_move,
    _install_numeric_wheel_permission,
    _numeric_target,
    _send_pointer_enter,
    _wheel_event,
)


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


def test_spinbox_target_to_target_dwell_without_editor_background_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Moving between spinboxes should let the new target dwell directly."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    clock_ms = [0]
    controller = cast(Any, panel)._wheel_intent_controller
    monkeypatch.setattr(controller, "_wheel_intent_now_ms", lambda: clock_ms[0])
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
    clock_ms[0] = 450
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
    clock_ms[0] = 900
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


def test_spinbox_enter_without_mouse_move_starts_wheel_dwell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pointer enter should start dwell even when Qt sends no mouse move."""

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

    _send_pointer_enter(spinbox)
    process_events(app)
    clock_ms[0] = 450
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
