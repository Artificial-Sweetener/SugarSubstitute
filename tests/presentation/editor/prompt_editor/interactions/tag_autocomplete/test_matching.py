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

"""Test real prompt-editor tag autocomplete matching boundaries."""

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


def test_prompt_editor_real_widget_uses_comma_delimited_space_tag_matching(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should treat spaces as tag content and commas as delimiters."""

    app = ensure_qapp()
    suggestions = (
        PromptAutocompleteSuggestion("long hair", 500),
        PromptAutocompleteSuggestion("long hairs", 200),
    )
    gateway = StaticPromptAutocompleteGateway({"long ha": suggestions})
    host = QWidget()
    host.resize(480, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "1girl, long ha")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert gateway.calls[-1] == ("long ha", 10)
    assert editor.toPlainText() == "1girl, long ha"
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(editor) == "ir"

    row = panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert editor.toPlainText() == "1girl, long hair"


def test_prompt_editor_real_widget_uses_suffix_fallback_without_leading_comma(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should complete the local token when typing inside no-comma prose."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("hair", 500),)
    gateway = StaticPromptAutocompleteGateway({"ha": suggestions})
    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    editor.setPlainText("1girl blue  solo")
    cursor = editor.textCursor()
    cursor.setPosition(len("1girl blue "))
    editor.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "ha")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert ("1girl blue ha", 10) in gateway.calls
    assert gateway.calls[-1] == ("ha", 10)
    assert editor.toPlainText() == "1girl blue ha solo"
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(editor) == "ir"

    row = panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert editor.toPlainText() == "1girl blue hair solo"


def test_prompt_editor_real_widget_accepts_underscore_input_as_spaced_completion(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should let underscore input complete to a spaced tag."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = StaticPromptAutocompleteGateway({"long_ha": suggestions})
    host = QWidget()
    host.resize(480, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "1girl, long_ha")
    process_events(app)

    assert gateway.calls[-1] == ("long_ha", 10)
    assert editor_autocomplete_preview_text(editor) == "ir"

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    row = panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert editor.toPlainText() == "1girl, long hair"


def test_prompt_editor_real_widget_hides_noop_autocomplete_suggestion_for_fully_typed_tag(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should hide when its only match is already present."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("looking_at_viewer", 500),)
    gateway = StaticPromptAutocompleteGateway({"looking at viewer": suggestions})
    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "looking at viewer")
    process_events(app)

    panel = cast(
        PromptAutocompletePanel | None,
        getattr(editor, "_autocomplete_panel"),
    )
    assert gateway.calls[-1] == ("looking at viewer", 10)
    assert panel is None or panel.is_panel_visible() is False
    assert editor_autocomplete_preview_text(editor) == ""


def test_prompt_editor_real_widget_ignores_quoted_and_bracketed_commas_for_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should keep the active segment after quoted or bracketed commas."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = StaticPromptAutocompleteGateway({"long ha": suggestions})
    host = QWidget()
    host.resize(560, 240)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, '"cat, dog", [bird, fish], long ha')
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert gateway.calls[-1] == ("long ha", 10)
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(editor) == "ir"

    row = panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert editor.toPlainText() == '"cat, dog", [bird, fish], long hair'


def test_prompt_editor_real_widget_ignores_braced_commas_for_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should keep the active segment after commas inside braces."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = StaticPromptAutocompleteGateway({"long ha": suggestions})
    host = QWidget()
    host.resize(560, 240)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "{animal, texture}, long ha")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert gateway.calls[-1] == ("long ha", 10)
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(editor) == "ir"

    row = panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert editor.toPlainText() == "{animal, texture}, long hair"
