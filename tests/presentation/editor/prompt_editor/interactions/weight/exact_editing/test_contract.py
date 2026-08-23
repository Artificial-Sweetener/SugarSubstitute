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

"""Verify exact weighted-token editing contracts."""

from __future__ import annotations


from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.projection_engine_support import (
    token_weight_controls_for,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from ..mounting import (
    click_control_rect,
    emphasis_token_for,
    exact_weight_edit_token,
    lora_token_for,
    reveal_emphasis_controls,
    show_lora_prompt_editor,
    start_exact_weight_edit,
    token_rect_for,
    weight_rect_for,
    wheel_widget_at_point,
)


def test_double_clicking_the_painted_weight_number_starts_exact_edit_mode(
    widgets: list[QWidget],
) -> None:
    """Only the painted number should enter native-looking exact weight edit mode."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = start_exact_weight_edit(box, token)
    exact_edit_token = exact_weight_edit_token(box)

    assert exact_edit_token is not None
    assert exact_edit_token.editing_value_text == "1.05"
    assert exact_edit_token.editing_select_all is True
    assert controls.increase_rect is None
    assert controls.decrease_rect is None
    assert controls.isVisible() is False
    assert surface_for(box).projection_document().tokens != ()


def test_double_clicking_lora_weight_starts_exact_edit_mode(
    widgets: list[QWidget],
) -> None:
    """LoRA weight numbers should enter the same exact edit mode as emphasis."""

    box = show_lora_prompt_editor(
        widgets,
        text="<lora:Mineru:0.80>",
        width=240,
    )
    token = lora_token_for(box)
    controls = start_exact_weight_edit(box, token)
    exact_edit_token = exact_weight_edit_token(box)

    assert exact_edit_token is not None
    assert exact_edit_token.kind is PromptProjectionTokenKind.LORA
    assert exact_edit_token.editing_value_text == "0.80"
    assert exact_edit_token.editing_select_all is True
    assert controls.increase_rect is None
    assert controls.decrease_rect is None
    assert controls.isVisible() is False


def test_lora_exact_weight_edit_commits_exact_value(
    widgets: list[QWidget],
) -> None:
    """LoRA exact edits should update the first schedule weight."""

    box = show_lora_prompt_editor(
        widgets,
        text="<lora:Mineru:0.80>",
        width=240,
    )
    token = lora_token_for(box)
    start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1.25")
    process_events(ensure_qapp(), cycles=2)
    assert exact_weight_edit_token(box) is not None

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "<lora:Mineru:1.25>"
    assert exact_weight_edit_token(box) is None


def test_double_clicking_emphasis_words_selects_only_the_inner_prompt_text(
    widgets: list[QWidget],
) -> None:
    """Double clicking emphasized words should select only the visible prompt text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(alpha beta:1.05)",
        width=220,
    )
    token = emphasis_token_for(box)
    assert token.content_start is not None
    assert token.content_end is not None
    token_rect = token_rect_for(box, token)
    weight_rect = weight_rect_for(box, token)
    word_point = QPoint(
        int((token_rect.left() + weight_rect.left()) / 2.0),
        int(token_rect.center().y()),
    )

    QTest.mouseDClick(box.viewport(), Qt.MouseButton.LeftButton, pos=word_point)
    process_events(app, cycles=4)

    cursor = box.textCursor()
    assert exact_weight_edit_token(box) is None
    assert cursor.selectionStart() == token.content_start
    assert cursor.selectionEnd() == token.content_end
    assert cursor.selectedText() == "alpha beta"
    assert surface_for(box).projection_document().tokens != ()


def test_double_clicking_emphasis_parens_selects_only_the_inner_prompt_text(
    widgets: list[QWidget],
) -> None:
    """Paren double clicks should still select only the inner prompt text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    assert token.content_start is not None
    assert token.content_end is not None
    token_rect = token_rect_for(box, token)
    paren_point = QPoint(int(token_rect.left() + 1), int(token_rect.center().y()))

    QTest.mouseDClick(box.viewport(), Qt.MouseButton.LeftButton, pos=paren_point)
    process_events(app, cycles=4)

    cursor = box.textCursor()
    assert exact_weight_edit_token(box) is None
    assert cursor.selectionStart() == token.content_start
    assert cursor.selectionEnd() == token.content_end
    assert cursor.selectedText() == "cat"
    assert surface_for(box).projection_document().tokens != ()


def test_double_clicking_emphasis_arrows_does_not_start_exact_edit_mode(
    widgets: list[QWidget],
) -> None:
    """Arrow double clicks should stay on the step-control path and never open exact edit."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = reveal_emphasis_controls(box, token)
    assert controls.increase_rect is not None
    assert controls.decrease_rect is not None

    QTest.mouseDClick(
        controls,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        controls.mapFromParent(controls.increase_rect.center().toPoint()),
    )
    process_events(ensure_qapp(), cycles=4)
    assert exact_weight_edit_token(box) is None

    token = emphasis_token_for(box)
    controls = reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None
    QTest.mouseDClick(
        controls,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        controls.mapFromParent(controls.decrease_rect.center().toPoint()),
    )
    process_events(ensure_qapp(), cycles=4)
    assert exact_weight_edit_token(box) is None


def test_weight_click_candidate_cannot_promote_overlap_down_click_into_exact_edit(
    widgets: list[QWidget],
) -> None:
    """A prior weight click must not let the down-arrow overlap open exact edit."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.10)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None
    assert controls._weight_hit_rect is not None  # noqa: SLF001

    overlap_rect = controls.decrease_rect.intersected(controls._weight_hit_rect)  # noqa: SLF001
    assert overlap_rect.isEmpty() is False

    weight_point = controls.mapFromParent(controls._weight_hit_rect.center().toPoint())  # noqa: SLF001
    overlap_point = controls.mapFromParent(overlap_rect.center().toPoint())

    QTest.mouseClick(controls, Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(ensure_qapp(), cycles=2)
    QTest.mouseClick(controls, Qt.MouseButton.LeftButton, pos=overlap_point)
    process_events(ensure_qapp(), cycles=4)

    assert exact_weight_edit_token(box) is None
    assert box.toPlainText() == "(cat:1.05)"


def test_exact_weight_edit_commits_exact_value_and_hides_step_controls(
    widgets: list[QWidget],
) -> None:
    """Exact weight editing should commit through Enter without exposing arrow controls."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    controls = start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1.20")
    process_events(ensure_qapp(), cycles=2)
    assert exact_weight_edit_token(box) is not None
    assert controls.increase_rect is None
    assert controls.decrease_rect is None

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "(cat:1.20)"
    assert exact_weight_edit_token(box) is None


def test_exact_weight_edit_commits_negative_emphasis_value(
    widgets: list[QWidget],
) -> None:
    """Exact weight editing should preserve a user-entered negative value."""

    box = show_prompt_editor(
        widgets,
        text="(cat:0.00)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "-0.25")
    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "(cat:-0.25)"
    assert emphasis_token_for(box).value_text == "-0.25"
    assert exact_weight_edit_token(box) is None


def test_exact_weight_edit_committing_one_unwraps_to_plain_text(
    widgets: list[QWidget],
) -> None:
    """Entering `1` should commit `1.00` and unwrap the source text."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1")
    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "cat"


def test_exact_weight_edit_can_restore_subneutral_emphasis_from_transient_neutral_token(
    widgets: list[QWidget],
) -> None:
    """Synthetic neutral tokens should support exact weight entry the same way as real shells."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    controls = token_weight_controls_for(box)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(ensure_qapp(), cycles=4)
    synthetic_token = controls.visible_token
    assert synthetic_token is not None
    assert synthetic_token.synthetic is True

    start_exact_weight_edit(box, synthetic_token)
    QTest.keyClicks(box, "0.95")
    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "(cat:0.95)"


def test_exact_weight_edit_escape_cancels_without_mutating_the_prompt(
    widgets: list[QWidget],
) -> None:
    """Escape should dismiss exact edit mode and leave the prompt text unchanged."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)

    QTest.keyClicks(box, "1.20")
    QTest.keyClick(box, Qt.Key.Key_Escape)
    process_events(ensure_qapp(), cycles=4)

    assert box.toPlainText() == "(cat:1.05)"
    assert exact_weight_edit_token(box) is None


def test_exact_weight_edit_ignores_wheel_adjustment_while_active(
    widgets: list[QWidget],
) -> None:
    """Exact edit mode should suppress wheel-based step adjustment for the active token."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)
    exact_edit_token = exact_weight_edit_token(box)
    assert exact_edit_token is not None
    exact_weight_rect = weight_rect_for(box, exact_edit_token)

    wheel_widget_at_point(
        box.viewport(),
        local_point=exact_weight_rect.center().toPoint(),
        angle_delta_y=120,
    )

    assert box.toPlainText() == "(cat:1.05)"
    assert exact_weight_edit_token(box) is not None


def test_exact_weight_edit_outside_click_commits_and_still_reaches_editor(
    widgets: list[QWidget],
) -> None:
    """Outside clicks should finalize exact edit and then continue through normal editor hit testing."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)
    QTest.keyClicks(box, "1.20")
    process_events(app, cycles=2)
    token_rect = token_rect_for(box, emphasis_token_for(box))
    click_point = QPoint(int(token_rect.left() + 2), int(token_rect.center().y()))
    expected_position = (
        surface_for(box)
        ._layout.frame.geometry.hit_testing.hit_test(  # noqa: SLF001
            QPointF(click_point),
            scroll_offset=float(box.verticalScrollBar().value()),
        )
        .source_position
    )

    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=click_point)
    process_events(app, cycles=4)

    assert box.toPlainText() == "(cat:1.20)"
    assert exact_weight_edit_token(box) is None
    assert box.textCursor().position() == expected_position


def test_exact_weight_edit_invalid_outside_click_cancels_and_still_reaches_editor(
    widgets: list[QWidget],
) -> None:
    """Outside clicks should cancel invalid exact edits and still continue into the editor."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    token = emphasis_token_for(box)
    start_exact_weight_edit(box, token)
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app, cycles=2)
    token_rect = token_rect_for(box, emphasis_token_for(box))
    click_point = QPoint(int(token_rect.left() + 2), int(token_rect.center().y()))
    expected_position = (
        surface_for(box)
        ._layout.frame.geometry.hit_testing.hit_test(  # noqa: SLF001
            QPointF(click_point),
            scroll_offset=float(box.verticalScrollBar().value()),
        )
        .source_position
    )

    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=click_point)
    process_events(app, cycles=4)

    assert box.toPlainText() == "(cat:1.05)"
    assert exact_weight_edit_token(box) is None
    assert box.textCursor().position() == expected_position
