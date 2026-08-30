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

"""Verify token-specific prompt weight and wildcard wheel intent."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from tests.support.prompt_editor.projection_engine_support import (
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.presentation.widgets.wheel_intent.support import (
    WheelIntentOwner,
    first_numeric_token,
    numeric_tokens,
    numeric_wildcard_token,
    reveal_numeric_token_controls,
    wheel_event_at_viewport_point,
)


def test_controller_gates_prompt_weight_wheel_until_dwell(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Configured prompt emphasis wheel edits should require token dwell."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller()
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = first_numeric_token(box)
    token_point = reveal_numeric_token_controls(box, token)

    premature_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), premature_event)
    process_events(app)

    assert box.toPlainText() == "(cat:1.20)"
    assert not premature_event.isAccepted()

    wheel_owner.advance(450)
    process_events(app)
    allowed_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "(cat:1.20)"
    assert allowed_event.isAccepted()


def test_focus_required_prompt_weight_blocks_hover_dwell_wheel(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focus-required mode should ignore token hover dwell for wheel edits."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = first_numeric_token(box)
    token_point = reveal_numeric_token_controls(box, token)

    wheel_owner.advance(450)
    process_events(app)
    blocked_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), blocked_event)
    process_events(app)

    assert box.toPlainText() == "(cat:1.20)"
    assert not blocked_event.isAccepted()


def test_focus_required_prompt_weight_allows_after_token_click(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focus-required mode should wheel-adjust a clicked weighted token."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = first_numeric_token(box)
    token_point = reveal_numeric_token_controls(box, token)

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        token_point,
    )
    process_events(app)
    allowed_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "(cat:1.20)"
    assert allowed_event.isAccepted()


def test_focus_required_numeric_wildcard_allows_after_token_click(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focus-required mode should wheel-adjust a clicked wildcard tag."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    box = show_prompt_editor(widgets, text="{animal|2}", width=320)
    controller.configure_widget(box)
    token = numeric_wildcard_token(box)
    token_point = reveal_numeric_token_controls(box, token)

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        token_point,
    )
    process_events(app)
    allowed_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "{animal|2}"
    assert allowed_event.isAccepted()


def test_focus_required_token_click_does_not_authorize_other_token(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Click activation should only authorize the clicked token target."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    original_text = "(cat:1.20) (dog:1.30)"
    box = show_prompt_editor(widgets, text=original_text, width=420)
    controller.configure_widget(box)
    first_token, second_token = numeric_tokens(box)
    first_point = reveal_numeric_token_controls(box, first_token)
    second_rect = surface_for(box).token_anchor_rect(second_token)
    assert second_rect is not None
    second_point = second_rect.center().toPoint()

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        first_point,
    )
    process_events(app)
    blocked_event = wheel_event_at_viewport_point(
        box.viewport(),
        second_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), blocked_event)
    process_events(app)

    assert box.toPlainText() == original_text


def test_controller_gates_numeric_wildcard_tag_until_dwell(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Configured prompt wildcard tag wheel edits should require token dwell."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller()
    box = show_prompt_editor(widgets, text="{animal|2}", width=320)
    controller.configure_widget(box)
    token = numeric_wildcard_token(box)
    token_point = reveal_numeric_token_controls(box, token)

    premature_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), premature_event)
    process_events(app)

    assert box.toPlainText() == "{animal|2}"
    assert not premature_event.isAccepted()

    wheel_owner.advance(450)
    process_events(app)
    allowed_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "{animal|2}"
    assert allowed_event.isAccepted()
