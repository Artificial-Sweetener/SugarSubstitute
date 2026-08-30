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

"""Test real prompt-editor source normalization behavior."""

from __future__ import annotations

import pytest

from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    create_prompt_editor,
)

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


def move_cursor_to_end(editor: PromptEditor) -> None:
    """Move the prompt-editor cursor to the document end."""

    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)


def test_prompt_editor_paste_normalizes_emphasis_weight(
    widgets: list[QWidget],
) -> None:
    """Pasted completed emphasis weights should use canonical two-decimal text."""

    app = ensure_qapp()
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    QApplication.clipboard().setText("(cat:1)")

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == "(cat:1.00)"
    assert editor.textCursor().selectionStart() == len("(cat:1.00)")


def test_prompt_editor_paste_keeps_cursor_after_normalized_insert(
    widgets: list[QWidget],
) -> None:
    """Cursor placement after paste should account for expanded weight text."""

    app = ensure_qapp()
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    widgets.append(editor)
    editor.show()
    editor.setPlainText("alpha, ")
    move_cursor_to_end(editor)
    editor.setFocus()
    QApplication.clipboard().setText("(cat:1)")

    editor.paste()
    process_events(app)

    assert editor.toPlainText() == "alpha, (cat:1.00)"
    assert editor.textCursor().selectionStart() == len("alpha, (cat:1.00)")


def test_prompt_editor_typing_does_not_normalize_incomplete_weight(
    widgets: list[QWidget],
) -> None:
    """Ordinary typing should not fight incomplete weight entry buffers."""

    app = ensure_qapp()
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    cursor = editor.textCursor()

    cursor.insertText("(cat:0.")
    process_events(app)

    assert editor.toPlainText() == "(cat:0."


def test_prompt_editor_cursor_insertion_preserves_completed_inline_emphasis_weight(
    widgets: list[QWidget],
) -> None:
    """Cursor insertion should preserve valid authored inline emphasis weights."""

    app = ensure_qapp()
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()
    cursor = editor.textCursor()

    cursor.insertText("black underbust (ribbon:1.2)")
    process_events(app)

    assert editor.toPlainText() == "black underbust (ribbon:1.2)"
    assert editor.textCursor().selectionStart() == len("black underbust (ribbon:1.2)")


def test_prompt_editor_key_typing_preserves_inline_weight_shape(
    widgets: list[QWidget],
) -> None:
    """Key-by-key typing should preserve valid inline emphasis while typing."""

    app = ensure_qapp()
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()

    QTest.keyClicks(editor, "black underbust (ribbon:1.2)")
    process_events(app)

    assert editor.toPlainText() == "black underbust (ribbon:1.2)"
    assert editor.textCursor().selectionStart() == len("black underbust (ribbon:1.2)")


def test_prompt_editor_key_typing_preserves_parenthetical_prompt_words(
    widgets: list[QWidget],
) -> None:
    """Key-by-key typing should preserve authored parenthetical prompt words."""

    app = ensure_qapp()
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    widgets.append(editor)
    editor.show()
    editor.setFocus()

    QTest.keyClicks(editor, "vertin (reverse:1999)")
    process_events(app)

    assert editor.toPlainText() == "vertin (reverse:1999)"


def test_prompt_editor_set_plain_text_normalizes_weights(
    widgets: list[QWidget],
) -> None:
    """Programmatic text loading should enter the same canonical source form."""

    app = ensure_qapp()
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    widgets.append(editor)
    editor.show()

    editor.setPlainText("black underbust (ribbon:1.2)")
    process_events(app)

    assert editor.toPlainText() == "black underbust (ribbon:1.20)"
