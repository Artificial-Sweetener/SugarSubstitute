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

"""Test prompt-weight wheel activation integration."""

from __future__ import annotations


from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.widgets.wheel_intent import (
    WheelIntentArbiter,
    WheelIntentTarget,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
    token_weight_controls_for,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition
from tests.support.qt.lifecycle import destroy_widget_roots

from tests.presentation.widgets.wheel_intent.integration_support import (
    _editor_panel_for_wheel_intent_tests,
    _first_weighted_token,
    _hover_mouse_move,
    _install_token_wheel_handlers,
    _reveal_weight_controls_without_dwell,
    _token_target,
    _token_weight_wheel_owner,
    _wheel_event_at_viewport_point,
)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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
    process_events(app)

    assert controls.visible_token is None
    assert _token_weight_wheel_owner(box).candidate_token is not None
    assert _first_weighted_token(box).decoration_accented is False

    wait_for_qt_condition(lambda: _first_weighted_token(box).decoration_accented)

    destroy_widget_roots(widgets)
    destroy_widget_roots((panel,))


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)
