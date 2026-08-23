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

"""Verify visible separator-name editing through the production shell."""

from __future__ import annotations

from itertools import pairwise

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit
import pytest

from substitute.presentation.editor.prompt_editor.interactions.region_inline_editor import (
    REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
)
from tests.support.prompt_editor.real_shell import reorder_rendering
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_f2_names_separator_with_source_backed_undo(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Edit a separator title with source-backed history."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="global\n[SEP]\nregion"
    )
    separator_end = field.editor.toPlainText().index("[SEP]") + len("[SEP]")
    real_shell_scenario.input.set_source_cursor_position(field, separator_end)

    real_shell_scenario.input.press_key(field, Qt.Key.Key_F2)
    real_shell_scenario.wait_until(
        lambda: (
            (
                candidate := field.editor.viewport().findChild(
                    QLineEdit,
                    REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
                )
            )
            is not None
            and candidate.isVisible()
        )
    )
    inline_editor = field.editor.viewport().findChild(
        QLineEdit,
        REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
    )
    assert inline_editor is not None
    assert inline_editor.isVisible()
    assert inline_editor.selectedText() == ""
    QTest.keyClicks(inline_editor, "Subject")
    QTest.keyClick(inline_editor, Qt.Key.Key_Return)
    real_shell_scenario.wait_for_queued_delivery()
    named = real_shell_scenario.snapshots.capture(field, label="named-separator")
    real_shell_scenario.input.undo(field)
    undone = real_shell_scenario.snapshots.capture(field, label="unnamed-separator")
    real_shell_scenario.input.redo(field)
    redone = real_shell_scenario.snapshots.capture(field, label="renamed-separator")

    assert named.source_text == "global\n[SEP|Subject]\nregion"
    assert undone.source_text == "global\n[SEP]\nregion"
    assert redone.source_text == named.source_text
    assert named.projection_region_separator_count == 1


def test_real_shell_double_click_edits_named_separator_in_place(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Reframe a named separator on every uncommitted inline-edit keystroke."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="global\n[SEP|Foreground]\nregion"
    )
    rendered = reorder_rendering.capture_reorder_layout(
        field,
        label="named-separator-before-inline-edit",
    )
    divider = rendered.region_divider_lines[0]
    divider_center = QPoint(
        round((divider[0] + divider[2]) / 2.0),
        round((divider[1] + divider[3]) / 2.0),
    )

    QTest.mouseDClick(
        field.editor.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        divider_center,
    )
    real_shell_scenario.wait_until(
        lambda: (
            (
                candidate := field.editor.viewport().findChild(
                    QLineEdit,
                    REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
                )
            )
            is not None
            and candidate.isVisible()
        )
    )
    inline_editor = field.editor.viewport().findChild(
        QLineEdit,
        REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
    )

    assert inline_editor is not None
    assert inline_editor.isVisible()
    real_shell_scenario.wait_until(inline_editor.hasFocus)
    assert inline_editor.selectedText() == "Foreground"
    divider_length = abs(divider[2] - divider[0])
    editor_widths: list[int] = []
    rule_inner_edges: list[tuple[float, float]] = []
    live_framing_rules: tuple[tuple[float, float, float, float], ...] = ()
    for character in "Subject":
        QTest.keyClicks(inline_editor, character)
        real_shell_scenario.wait_for_queued_delivery()
        live = reorder_rendering.capture_reorder_layout(
            field,
            label=f"named-separator-inline-editor-{character}",
        )
        framing_rules = live.region_stroke_lines[-2:]
        live_framing_rules = framing_rules
        editor_widths.append(inline_editor.width())
        rule_inner_edges.append((framing_rules[0][2], framing_rules[1][0]))

        assert field.editor.toPlainText() == "global\n[SEP|Foreground]\nregion"
        assert abs(framing_rules[0][2] - framing_rules[0][0]) == pytest.approx(
            divider_length
        )
        assert abs(framing_rules[1][2] - framing_rules[1][0]) == pytest.approx(
            divider_length
        )
        assert inline_editor.isVisible()

    assert all(
        current_width > previous_width
        for previous_width, current_width in pairwise(editor_widths)
    )
    assert all(
        current_left < previous_left and current_right > previous_right
        for (previous_left, previous_right), (current_left, current_right) in pairwise(
            rule_inner_edges
        )
    )

    QTest.keyClick(inline_editor, Qt.Key.Key_Return)
    real_shell_scenario.wait_for_queued_delivery()

    after = real_shell_scenario.snapshots.capture(
        field,
        label="separator-inline-renamed",
    )
    settled_framing_rules = reorder_rendering.capture_reorder_layout(
        field,
        label="separator-inline-renamed-rendered",
    ).region_stroke_lines[-2:]
    assert after.source_text == "global\n[SEP|Subject]\nregion"
    assert len(settled_framing_rules) == len(live_framing_rules)
    assert all(
        settled_rule == pytest.approx(live_rule)
        for settled_rule, live_rule in zip(
            settled_framing_rules,
            live_framing_rules,
            strict=True,
        )
    )


def test_real_shell_region_inline_edit_commits_when_focus_leaves(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Commit an active separator title when focus leaves the inline editor."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="global\n[SEP]\nregion"
    )
    separator_end = field.editor.toPlainText().index("[SEP]") + len("[SEP]")
    real_shell_scenario.input.set_source_cursor_position(field, separator_end)
    real_shell_scenario.input.press_key(field, Qt.Key.Key_F2)
    real_shell_scenario.wait_until(
        lambda: (
            (
                candidate := field.editor.viewport().findChild(
                    QLineEdit,
                    REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
                )
            )
            is not None
            and candidate.isVisible()
        )
    )
    inline_editor = field.editor.viewport().findChild(
        QLineEdit,
        REGION_NAME_INLINE_EDITOR_OBJECT_NAME,
    )

    assert inline_editor is not None
    real_shell_scenario.wait_until(inline_editor.hasFocus)
    QTest.keyClicks(inline_editor, "Background")
    field.editor.setFocus(Qt.FocusReason.MouseFocusReason)
    expected_source = "global\n[SEP|Background]\nregion"
    real_shell_scenario.wait_until(
        lambda: (
            field.editor.toPlainText() == expected_source
            and not inline_editor.isVisible()
            and field.editor.hasFocus()
        )
    )

    after = real_shell_scenario.snapshots.capture(
        field,
        label="separator-focus-committed",
    )
    assert after.source_text == expected_source
    assert not inline_editor.isVisible()
