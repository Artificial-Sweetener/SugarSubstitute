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

"""Test real prompt-editor LoRA autocomplete interactions."""

from __future__ import annotations

from typing import cast

import pytest

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget

from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
    PromptLoraWallView,
)
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_fixtures import (
    sample_lora,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    editor_autocomplete_preview_text,
)
from tests.presentation.editor.prompt_editor.interactions.lora_autocomplete.support import (
    create_lora_prompt_editor,
)

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


def test_prompt_editor_paste_normalizes_lora_first_weight(
    widgets: list[QWidget],
) -> None:
    """Pasted completed LoRA first weights should use canonical two-decimal text."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(loras=())
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    QApplication.clipboard().setText("<lora:Ranni_illusXLNoobAI_Incrs_v1:1>")

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == "<lora:Ranni_illusXLNoobAI_Incrs_v1:1.00>"


def test_prompt_editor_paste_normalizes_lora_second_weight(
    widgets: list[QWidget],
) -> None:
    """Pasted completed LoRA second weights should normalize with first weights."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(loras=())
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    QApplication.clipboard().setText("<lora:Name:0.9:1>")

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == "<lora:Name:0.90:1.00>"


def test_prompt_editor_lora_autocomplete_opens_wall_without_search_box(
    widgets: list[QWidget],
) -> None:
    """Typing a LoRA token prefix should open the wall-based autocomplete surface."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    editor = create_lora_prompt_editor(loras=(sample_lora(),))
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "<lora:Civ")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    wall = panel.lora_wall()
    assert panel.is_panel_visible() is True
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    assert wall.items()[0].title == "CivitAI Midna"
    assert panel.findChildren(QLineEdit) == []
    assert editor_autocomplete_preview_text(editor) == "itAI Midna"


def test_prompt_editor_lora_autocomplete_one_row_up_down_stays_open(
    widgets: list[QWidget],
) -> None:
    """Vertical no-op navigation should not dismiss a one-row LoRA wall."""

    app = ensure_qapp()
    loras = tuple(
        sample_lora(
            display_name=f"LoRA {index}",
            basename=f"lora_{index}",
            prompt_name=rf"folder\lora_{index}",
        )
        for index in range(3)
    )
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    editor = create_lora_prompt_editor(loras=loras)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "<lora:LoRA")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    cursor_before_navigation = editor.textCursor().position()

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0

    QTest.keyClick(editor, Qt.Key.Key_Down)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert editor.textCursor().position() == cursor_before_navigation

    QTest.keyClick(editor, Qt.Key.Key_Up)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert editor.textCursor().position() == cursor_before_navigation

    QTest.keyClick(editor, Qt.Key.Key_Right)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 1
    assert editor.textCursor().position() == cursor_before_navigation


def test_prompt_editor_lora_autocomplete_prefix_does_not_scroll_up(
    widgets: list[QWidget],
) -> None:
    """Typing a bottom-of-prompt LoRA prefix should preserve the viewport."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(430, 760)
    layout = QVBoxLayout(host)
    editor = create_lora_prompt_editor(loras=(sample_lora(),))
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    editor.setPlainText(
        ("one two three four five six seven eight nine ten " * 60).strip()
    )
    process_events(app)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    process_events(app)
    scroll_bar = editor.verticalScrollBar()
    scroll_bar.setValue(scroll_bar.maximum())
    process_events(app)

    QTest.keyClick(editor, Qt.Key.Key_Return)
    process_events(app)
    previous_value = scroll_bar.value()
    for text in ("<", "l", "o", "r", "a", ":"):
        QTest.keyClicks(editor, text)
        process_events(app)
        assert scroll_bar.value() >= previous_value
        previous_value = scroll_bar.value()
    assert editor.toPlainText().endswith("\n<lora:")


def test_prompt_editor_lora_autocomplete_accepts_scheduler_safe_prompt_name(
    widgets: list[QWidget],
) -> None:
    """LoRA autocomplete should insert the raw prompt name, not the display label."""

    app = ensure_qapp()
    lora = sample_lora()
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    editor = create_lora_prompt_editor(loras=(lora,))
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "<lora:Civ")
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    process_events(app)

    assert editor.toPlainText() == r"<lora:illustrious\characters\raw_midna:1.00>"
    assert editor.hasFocus() is True


def test_prompt_editor_lora_autocomplete_click_accepts_selected_lora(
    widgets: list[QWidget],
) -> None:
    """Clicking the LoRA wall should accept through the same coordinator path."""

    app = ensure_qapp()
    lora = sample_lora()
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    editor = create_lora_prompt_editor(loras=(lora,))
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "<lora:Civ")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    wall = panel.lora_wall()
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    assert wall.activate_current() is True
    process_events(app)

    assert editor.toPlainText() == r"<lora:illustrious\characters\raw_midna:1.00>"
