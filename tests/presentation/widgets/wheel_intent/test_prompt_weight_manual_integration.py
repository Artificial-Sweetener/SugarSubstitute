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

"""Test manual prompt-weight control integration."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.wheel_intent import (
    WheelIntentArbiter,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    token_weight_controls_for,
)
from tests.support.qt.lifecycle import destroy_widget_roots

from tests.presentation.widgets.wheel_intent.integration_support import (
    _first_weighted_token,
    _install_token_wheel_handlers,
    _reveal_weight_controls_without_dwell,
)


def test_prompt_weight_controls_reveal_on_hover_without_token_dwell() -> None:
    """Weighted-token hover controls should not require wheel dwell."""

    _ = ensure_qapp()
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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)


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
    process_events(app)
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

    destroy_widget_roots(widgets)


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

    destroy_widget_roots(widgets)
