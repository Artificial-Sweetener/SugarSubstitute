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

"""Verify seed keyboard, wheel, and menu interaction through real Qt events."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest

from substitute.presentation.widgets.menu_buttons import ToggleSplitToolButton
from substitute.presentation.widgets.seed_box import SeedBox
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_primary_button_toggles_seed_mode() -> None:
    """The real split-button primary action should alternate seed mode."""

    ensure_qt_application()
    widget = SeedBox()

    widget.split_button.button.clicked.emit()
    assert widget.mode() == "fixed"
    widget.split_button.button.clicked.emit()
    assert widget.mode() == "random"
    destroy_qt_object(widget)


def test_mode_menu_is_attached_to_toggle_aware_split_button() -> None:
    """Seed mode actions should use the shared toggle-aware menu boundary."""

    ensure_qt_application()
    widget = SeedBox()

    assert isinstance(widget.split_button, ToggleSplitToolButton)
    assert widget.split_button._attached_popup is widget.menu
    assert widget.random_action.property("menuActionId") == "seed.randomize"
    assert widget.fixed_action.property("menuActionId") == "seed.use_current"
    destroy_qt_object(widget)


def test_up_and_down_keys_step_and_clamp_value() -> None:
    """Real key events should step seed values without crossing configured bounds."""

    ensure_qt_application()
    widget = SeedBox(minimum=0, maximum=11, step=2)
    widget.setValue(10)

    QTest.keyClick(widget, Qt.Key.Key_Up)
    assert widget.value() == 11
    QTest.keyClick(widget, Qt.Key.Key_Down)
    assert widget.value() == 9
    destroy_qt_object(widget)


def test_wheel_events_step_and_clamp_value() -> None:
    """Real wheel payloads should use the configured step and range contract."""

    ensure_qt_application()
    widget = SeedBox(minimum=0, maximum=10, step=5)
    widget.setValue(3)

    upward = _wheel_event(120)
    widget.wheelEvent(upward)
    assert upward.isAccepted()
    assert widget.value() == 8

    widget.setValue(3)
    downward = _wheel_event(-120)
    widget.wheelEvent(downward)
    assert downward.isAccepted()
    assert widget.value() == 0
    destroy_qt_object(widget)


def _wheel_event(delta: int) -> QWheelEvent:
    """Return one local wheel event with the requested vertical delta."""

    return QWheelEvent(
        QPointF(1, 1),
        QPointF(1, 1),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
