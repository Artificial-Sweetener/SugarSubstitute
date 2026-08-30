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

"""Verify prompt scrolling remains distinct from token adjustment."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from tests.support.prompt_editor.projection_engine_support import (
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.presentation.widgets.wheel_intent.support import (
    WheelIntentOwner,
    first_numeric_token,
    hover_mouse_move,
    reveal_numeric_token_controls,
    wheel_event,
    wheel_event_at_viewport_point,
)


def test_focus_required_prompt_scroll_requires_focus(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focus-required mode should only allow prompt scrolling after focus."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    blocker = wheel_owner.own(QWidget())
    blocker.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    controller.configure_widget(box)
    blocker.show()
    blocker.setFocus()
    process_events(app)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    blocked_event = wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), blocked_event)
    process_events(app)

    assert scrollbar.value() == 0
    assert not blocked_event.isAccepted()

    box.window().activateWindow()
    box.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
    process_events(app)
    allowed_event = wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert scrollbar.value() > 0
    assert allowed_event.isAccepted()


def test_controller_preserves_focused_prompt_scroll_intent(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focused prompt editors should scroll without hover dwell."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller()
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    controller.configure_widget(box)
    box.setFocus()
    process_events(app)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    focused_event = wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), focused_event)
    process_events(app)

    assert scrollbar.value() > 0
    assert focused_event.isAccepted()


def test_controller_focused_prompt_scroll_does_not_authorize_token_wheel_edit(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Focused prompt scrolling should not bypass token-specific wheel dwell."""

    app = wheel_owner.application
    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.20)\n" + "\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    controller.configure_widget(box)
    token = first_numeric_token(box)
    token_point = reveal_numeric_token_controls(box, token)
    box.setFocus()
    process_events(app)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    focused_token_event = wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=-120,
    )
    QApplication.sendEvent(box.viewport(), focused_token_event)
    process_events(app)

    assert box.toPlainText().startswith("(cat:1.20)")
    assert scrollbar.value() > 0
    assert focused_token_event.isAccepted()


def test_controller_token_tracking_survives_prompt_scroll_tracking_for_same_move(
    wheel_owner: WheelIntentOwner,
) -> None:
    """Prompt-scroll tracking should not overwrite token hover ownership."""

    widgets = wheel_owner.widgets
    controller = wheel_owner.create_controller()
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = first_numeric_token(box)
    token_rect = surface_for(box).token_anchor_rect(token)
    assert token_rect is not None
    global_point = box.viewport().mapToGlobal(token_rect.center().toPoint())
    token_target = controller._prompt_weight_target(box, token)  # noqa: SLF001

    controller._record_prompt_weight_pointer_move(  # noqa: SLF001
        box,
        token,
        QPointF(global_point),
    )
    controller._record_wheel_intent_pointer_move(  # noqa: SLF001
        box,
        hover_mouse_move(box, box.mapFromGlobal(global_point)),
    )
    controller._clear_wheel_intent_hover_for_widget(box)  # noqa: SLF001
    wheel_owner.advance(400)
    owner = controller._wheel_intent_arbiter.wheel_owner_for_event(  # noqa: SLF001
        target=token_target,
        timestamp_ms=controller._wheel_intent_now_ms(),  # noqa: SLF001
        target_can_accept_wheel=True,
    )

    assert owner == token_target
