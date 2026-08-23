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

"""Verify deliberate wheel intent for numeric editor controls."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.presentation.widgets import SpinBox
from tests.support.prompt_editor.projection_engine_support import process_events
from tests.presentation.widgets.wheel_intent.support import (
    WheelIntentOwner,
    hover_mouse_move,
    wheel_event,
)


def test_controller_gates_spinbox_wheel_until_dwell(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Configured spin boxes should only wheel-adjust after pointer dwell."""

    app = wheel_owner.application
    controller = wheel_owner.create_controller()
    spinbox = wheel_owner.own(SpinBox())
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    process_events(app)

    QApplication.sendEvent(
        spinbox,
        hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    process_events(app)
    premature_event = wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, premature_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not premature_event.isAccepted()

    wheel_owner.advance(450)
    process_events(app)
    allowed_event = wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, allowed_event)
    process_events(app)

    assert spinbox.value() == 6
    assert allowed_event.isAccepted()


def test_focus_required_spinbox_blocks_hover_dwell_wheel(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focus-required mode should not let hover dwell authorize spin boxes."""

    app = wheel_owner.application
    controller = wheel_owner.create_controller(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    spinbox = wheel_owner.own(SpinBox())
    blocker = wheel_owner.own(QWidget())
    blocker.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    blocker.show()
    blocker.setFocus()
    process_events(app)

    QApplication.sendEvent(
        spinbox,
        hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    wheel_owner.advance(450)
    process_events(app)
    blocked_event = wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, blocked_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not blocked_event.isAccepted()


def test_focus_required_spinbox_allows_focused_wheel(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focus-required mode should allow focused spin boxes to wheel-adjust."""

    app = wheel_owner.application
    controller = wheel_owner.create_controller(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    spinbox = wheel_owner.own(SpinBox())
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    spinbox.setFocus()
    process_events(app)

    allowed_event = wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, allowed_event)
    process_events(app)

    assert spinbox.value() == 6
    assert allowed_event.isAccepted()


def test_switching_controller_mode_clears_stale_hover_authorization(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Changing to focus-required should drop existing hover authorization."""

    app = wheel_owner.application
    controller = wheel_owner.create_controller()
    spinbox = wheel_owner.own(SpinBox())
    blocker = wheel_owner.own(QWidget())
    blocker.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    blocker.show()
    blocker.setFocus()
    process_events(app)

    QApplication.sendEvent(
        spinbox,
        hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    wheel_owner.advance(450)
    process_events(app)

    controller.set_wheel_adjustment_mode(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    blocked_event = wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, blocked_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not blocked_event.isAccepted()
