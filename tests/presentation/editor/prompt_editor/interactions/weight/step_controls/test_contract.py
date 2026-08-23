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

"""Verify weighted-token step controls and undo contracts."""

from __future__ import annotations


import pytest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    token_weight_controls_for,
    ensure_qapp,
    process_events,
    show_prompt_editor,
)
from ..mounting import (
    anchor_rect_for,
    click_control_rect,
    emphasis_token_for,
    reveal_emphasis_controls,
    set_cursor_position,
    wheel_widget_at_point,
)


def test_inline_increase_click_updates_prompt_text_without_selecting_emphasis_content(
    widgets: list[QWidget],
) -> None:
    """Clicking the visible up control should mutate text without leaving selection highlight."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)

    cursor = box.textCursor()
    assert box.toPlainText() == "(cat:1.10)"
    assert box.hasFocus() is True
    assert cursor.selectionStart() == 2
    assert cursor.selectionEnd() == 2
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None
    assert emphasis_token_for(box).decoration_accented is True
    assert controls._gestures.weight_preview_text == "1.10"  # noqa: SLF001
    assert controls._gestures.weight_preview_rect is not None  # noqa: SLF001
    assert (
        controls._gestures.weight_preview_rect.bottom()  # noqa: SLF001
        >= controls.increase_rect.center().y() - 6.0
    )


def test_inline_emphasis_clicks_keep_controls_visible_without_mouse_rehover(
    widgets: list[QWidget],
) -> None:
    """Successive arrow clicks should not require pointer movement to keep the controls alive."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "(cat:1.10)"
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "(cat:1.15)"
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None


def test_emphasis_controls_keep_a_stable_horizontal_anchor_while_values_change(
    widgets: list[QWidget],
) -> None:
    """Repeated emphasis adjustments should not shift the arrow stack horizontally."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    initial_center_x = controls.increase_rect.center().x()

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())
    assert controls.increase_rect is not None
    assert controls.increase_rect.center().x() == pytest.approx(initial_center_x)

    assert controls.decrease_rect is not None
    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert controls.increase_rect is not None
    assert controls.increase_rect.center().x() == pytest.approx(initial_center_x)


def test_inline_decrease_click_unwraps_neutral_emphasis(
    widgets: list[QWidget],
) -> None:
    """Clicking down to neutral should unwrap source text but keep a visible `1.00` step."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    cursor = box.textCursor()
    assert box.toPlainText() == "cat"
    assert cursor.selectionStart() == 2
    assert cursor.selectionEnd() == 2
    visible_token = controls.visible_token
    assert visible_token is not None
    assert controls.isVisible() is True
    assert controls.decrease_rect is not None
    assert visible_token.synthetic is True
    assert visible_token.value_text == "1.00"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001


def test_inline_decrease_click_can_continue_below_transient_neutral_emphasis(
    widgets: list[QWidget],
) -> None:
    """A second down-click from the transient neutral step should create sub-neutral emphasis."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert controls.isVisible() is True
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:0.95)"


def test_inline_decrease_click_crosses_zero_into_negative_emphasis(
    widgets: list[QWidget],
) -> None:
    """The inline decrease control should step from zero to negative emphasis."""

    box = show_prompt_editor(
        widgets,
        text="(cat:0.00)",
        width=180,
    )
    controls = token_weight_controls_for(box)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:-0.05)"
    assert emphasis_token_for(box).value_text == "-0.05"

    controls = token_weight_controls_for(box)
    reveal_emphasis_controls(box, emphasis_token_for(box))
    assert controls.increase_rect is not None
    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:0.00)"
    assert emphasis_token_for(box).value_text == "0.00"


def test_inline_increase_click_can_restore_emphasis_from_transient_neutral_step(
    widgets: list[QWidget],
) -> None:
    """The transient neutral step should support an immediate increase back to `1.05`."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert controls.isVisible() is True
    assert controls.increase_rect is not None

    click_control_rect(controls, controls.increase_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:1.05)"


def test_inline_decrease_click_keeps_transient_neutral_visible_when_caret_is_elsewhere(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should survive even when the caret is outside."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, len(box.toPlainText()))
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "cat, dog"
    visible_token = controls.visible_token
    assert visible_token is not None
    assert visible_token.synthetic is True
    assert visible_token.value_text == "1.00"
    assert controls.isVisible() is True


def test_inline_decrease_click_with_caret_elsewhere_can_continue_below_transient_neutral(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should support a second click below neutral."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, len(box.toPlainText()))
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat, dog"
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:0.95), dog"


def test_emphasis_controls_round_trip_through_editor_undo_stack(
    widgets: list[QWidget],
) -> None:
    """Projection-engine emphasis control clicks should remain undoable and redoable."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    click_control_rect(controls, controls.increase_rect)
    assert box.toPlainText() == "(cat:1.10)"

    box.undo()
    process_events(app)
    assert box.toPlainText() == "(cat:1.05)"

    box.redo()
    process_events(app)
    assert box.toPlainText() == "(cat:1.10)"


def test_visible_emphasis_controls_accept_mouse_wheel_like_a_spinbox(
    widgets: list[QWidget],
) -> None:
    """Wheel input over the token or controls should adjust emphasis on the source text."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)
    token = emphasis_token_for(box)
    token_center = anchor_rect_for(box, token).center().toPoint()

    wheel_widget_at_point(box.viewport(), local_point=token_center, angle_delta_y=120)
    assert box.toPlainText() == "(cat:1.10)"
    assert emphasis_token_for(box).value_text == "1.10"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001

    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    wheel_widget_at_point(
        controls,
        local_point=controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    assert box.toPlainText() == "(cat:1.05)"

    wheel_widget_at_point(
        controls,
        local_point=controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    process_events(ensure_qapp())
    assert box.toPlainText() == "cat"
    assert controls._gestures.weight_preview_text == "1.00"  # noqa: SLF001
    assert controls.visible_token is not None
    assert controls.isVisible() is True
    assert controls.increase_rect is not None
    assert controls.visible_token.synthetic is True
    assert controls.visible_token.value_text == "1.00"

    wheel_widget_at_point(
        controls,
        local_point=controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    process_events(ensure_qapp())
    assert box.toPlainText() == "(cat:0.95)"
    assert controls._gestures.weight_preview_text == "0.95"  # noqa: SLF001


def test_visible_emphasis_controls_wheel_crosses_zero_into_negative_emphasis(
    widgets: list[QWidget],
) -> None:
    """Wheel-down over emphasis controls should step through zero."""

    box = show_prompt_editor(
        widgets,
        text="(cat:0.00)",
        width=180,
    )
    controls = token_weight_controls_for(box)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None

    wheel_widget_at_point(
        controls,
        local_point=controls.mapFromParent(controls.increase_rect.center().toPoint()),
        angle_delta_y=-120,
    )
    process_events(ensure_qapp())

    assert box.toPlainText() == "(cat:-0.05)"
    assert emphasis_token_for(box).value_text == "-0.05"
