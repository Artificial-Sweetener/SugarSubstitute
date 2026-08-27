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

"""Test spinner-slider wheel-intent integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QSlider

from substitute.presentation.editor.panel.factories.numeric_factory import (
    _build_color_slider_widget,
    _build_int_spinner_slider_widget,
    _build_spinner_slider_widget,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
)

from tests.presentation.widgets.wheel_intent.integration_support import (
    _assert_slider_wheel_does_not_edit_bound_field,
    _bind_spinner_slider_field,
    _editor_panel_for_wheel_intent_tests,
    _hover_mouse_move,
    _wheel_event,
)


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


def test_spinner_slider_spinbox_wheel_keeps_dwell_intent_and_syncs_slider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spinner-slider spinboxes should keep dwell-gated wheel editing."""

    app = ensure_qapp()
    panel = _editor_panel_for_wheel_intent_tests()
    clock_ms = [0]
    controller = cast(Any, panel)._wheel_intent_controller
    monkeypatch.setattr(controller, "_wheel_intent_now_ms", lambda: clock_ms[0])
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
    clock_ms[0] = 450

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
