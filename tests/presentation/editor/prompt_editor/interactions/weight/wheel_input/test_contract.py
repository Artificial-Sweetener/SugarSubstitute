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

"""Verify weighted-token pointer and wheel input contracts."""

from __future__ import annotations


from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    token_weight_controls_for,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from ..mounting import (
    anchor_rect_for,
    click_control_rect,
    emphasis_token_for,
    lora_token_for,
    point_outside_token,
    reveal_emphasis_controls,
    set_cursor_position,
    shell_viewport_for,
    show_lora_prompt_editor,
    token_rect_for,
    weight_rect_for,
    wheel_widget_at_point,
)


def test_wheel_outside_emphasis_token_does_not_adjust_when_caret_is_inside_token(
    widgets: list[QWidget],
) -> None:
    """Wheel targeting should ignore caret-owned emphasis when the pointer is outside."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05) plain text that extends right",
        width=420,
    )
    token = emphasis_token_for(box)
    set_cursor_position(box, 2)

    accepted = wheel_widget_at_point(
        box.viewport(),
        local_point=point_outside_token(box, token),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "(cat:1.05) plain text that extends right"
    assert accepted is False


def test_wheel_outside_lora_chip_does_not_adjust_when_caret_is_inside_token(
    widgets: list[QWidget],
) -> None:
    """Wheel targeting should ignore caret-owned LoRA chips when the pointer is outside."""

    box = show_lora_prompt_editor(
        widgets,
        text="<lora:Mineru:0.80> plain text that extends right",
        width=460,
    )
    token = lora_token_for(box)
    set_cursor_position(box, 3)

    wheel_widget_at_point(
        box.viewport(),
        local_point=point_outside_token(box, token),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "<lora:Mineru:0.80> plain text that extends right"


def test_wheel_outside_weighted_tokens_scrolls_when_scrollbar_available(
    widgets: list[QWidget],
) -> None:
    """Wheel input outside weighted tokens should remain available for scrolling."""

    source = "(cat:1.05)\n" + "\n".join(f"line {index}" for index in range(20))
    box = show_prompt_editor(
        widgets,
        text=source,
        width=420,
    )
    token = emphasis_token_for(box)
    set_cursor_position(box, 2)
    scroll_bar = box.verticalScrollBar()
    assert scroll_bar.maximum() > scroll_bar.minimum()
    initial_scroll_value = scroll_bar.value()

    wheel_widget_at_point(
        box.viewport(),
        local_point=point_outside_token(box, token),
        angle_delta_y=-120,
    )

    assert box.toPlainText() == source
    assert scroll_bar.value() > initial_scroll_value


def test_wheel_over_emphasis_token_adjusts_by_pointer(
    widgets: list[QWidget],
) -> None:
    """Pointer hit testing should adjust emphasis even when the caret is elsewhere."""

    box = show_prompt_editor(
        widgets,
        text="prefix (cat:1.05)",
        width=240,
    )
    token = emphasis_token_for(box)
    set_cursor_position(box, 0)

    wheel_widget_at_point(
        box.viewport(),
        local_point=token_rect_for(box, token).center().toPoint(),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "prefix (cat:1.10)"


def test_host_viewport_wheel_over_emphasis_token_adjusts_on_first_tick(
    widgets: list[QWidget],
) -> None:
    """The outer prompt host should give weighted tokens first chance at wheel input."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)\n" + "\n".join(f"line {index}" for index in range(20)),
        width=420,
    )
    token = emphasis_token_for(box)
    host_viewport = shell_viewport_for(box)
    token_center = token_rect_for(box, token).center().toPoint()
    initial_scroll_value = box.verticalScrollBar().value()

    accepted = wheel_widget_at_point(
        host_viewport,
        local_point=token_center,
        angle_delta_y=120,
    )

    assert accepted is True
    assert box.toPlainText().startswith("(cat:1.10)")
    assert box.verticalScrollBar().value() == initial_scroll_value


def test_wheel_over_lora_chip_adjusts_by_pointer(
    widgets: list[QWidget],
) -> None:
    """Pointer hit testing should adjust LoRA weights across the whole chip."""

    box = show_lora_prompt_editor(
        widgets,
        text="prefix <lora:Mineru:0.80>",
        width=360,
    )
    token = lora_token_for(box)
    token_rect = token_rect_for(box, token)
    weight_rect = weight_rect_for(box, token)
    chip_point = QPoint(int(token_rect.left()) + 8, int(token_rect.center().y()))
    assert not weight_rect.contains(QPointF(chip_point))
    set_cursor_position(box, 0)

    wheel_widget_at_point(
        box.viewport(),
        local_point=chip_point,
        angle_delta_y=120,
    )

    assert box.toPlainText() == "prefix <lora:Mineru:0.85>"


def test_overlay_wheel_to_neutral_keeps_caret_at_plain_text_content_end(
    widgets: list[QWidget],
) -> None:
    """Wheel adjustment to neutral should leave caret at the plain-text content end."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    surface = surface_for(box)
    token = emphasis_token_for(box)
    cursor = box.textCursor()
    cursor.setPosition(token.content_end, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    wheel_widget_at_point(
        box.viewport(),
        local_point=anchor_rect_for(box, token).center().toPoint(),
        angle_delta_y=-120,
    )
    process_events(app)

    assert box.textCursor().position() == 3
    assert box.textCursor().selectionStart() == 3
    assert box.textCursor().selectionEnd() == 3
    assert surface._cursor_state.source_position == 3


def test_down_control_does_not_show_pointer_weight_preview(
    widgets: list[QWidget],
) -> None:
    """Down-arrow clicks should not show the floating weight preview bubble."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.10)",
        width=180,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)

    assert box.toPlainText() == "(cat:1.05)"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001
    assert controls._gestures.weight_preview_rect is None  # noqa: SLF001


def test_wheel_over_emphasis_words_does_not_show_pointer_weight_preview(
    widgets: list[QWidget],
) -> None:
    """Wheel adjustments away from the number and up arrow should not show the preview bubble."""

    box = show_prompt_editor(
        widgets,
        text="(alpha beta gamma:1.05)",
        width=220,
    )
    controls = token_weight_controls_for(box)
    token = emphasis_token_for(box)
    anchor_rect = anchor_rect_for(box, token)
    token_rect = token_rect_for(box, token)
    text_point = QPoint(
        int((token_rect.left() + anchor_rect.left()) / 2.0),
        int(token_rect.center().y()),
    )

    wheel_widget_at_point(box.viewport(), local_point=text_point, angle_delta_y=120)

    assert box.toPlainText() == "(alpha beta gamma:1.10)"
    assert controls._gestures.weight_preview_text is None  # noqa: SLF001
    assert controls._gestures.weight_preview_rect is None  # noqa: SLF001
