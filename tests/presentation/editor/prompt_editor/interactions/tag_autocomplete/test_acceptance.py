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

"""Test real prompt-editor tag autocomplete acceptance boundaries."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
)
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_assertions import (
    panel_rows,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    create_prompt_editor,
    editor_autocomplete_preview_text,
)


def test_prompt_editor_real_widget_consumes_matching_right_text_on_accept(
    widgets: list[QWidget],
) -> None:
    """Mid-tag autocomplete should replace matching right text without duplication."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = StaticPromptAutocompleteGateway({"long h": suggestions})
    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    editor.setPlainText("long ir")
    cursor = editor.textCursor()
    cursor.setPosition(len("long "))
    editor.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "h")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert gateway.calls[-1] == ("long h", 10)
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(editor) == "a"

    row = panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert editor.toPlainText() == "long hair"


def test_prompt_editor_real_widget_keeps_unrelated_right_text_on_accept(
    widgets: list[QWidget],
) -> None:
    """Mid-tag autocomplete should leave unrelated text after the caret untouched."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = StaticPromptAutocompleteGateway({"long h": suggestions})
    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    editor.setPlainText("long x")
    cursor = editor.textCursor()
    cursor.setPosition(len("long "))
    editor.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "h")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert gateway.calls[-1] == ("long h", 10)
    assert editor_autocomplete_preview_text(editor) == "air"

    row = panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert editor.toPlainText() == "long hairx"
