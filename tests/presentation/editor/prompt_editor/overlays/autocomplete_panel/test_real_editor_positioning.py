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

"""Test real-editor autocomplete panel positioning behavior."""

from __future__ import annotations

from typing import cast

from PySide6.QtTest import QTest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
)
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_fixtures import (
    sample_suggestions,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    create_prompt_editor,
)


def test_prompt_editor_real_widget_repositions_panel_when_editor_moves(
    widgets: list[QWidget],
) -> None:
    """Moving the editor inside its host should move the autocomplete panel with it."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(640, 260)
    editor = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    editor.setGeometry(40, 40, 260, editor.minimumEditorHeight())
    host.show()
    host.activateWindow()
    editor.show()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    initial_geometry = panel.geometry()
    editor.move(180, 92)
    process_events(app)

    moved_geometry = panel.geometry()
    assert moved_geometry != initial_geometry
    assert moved_geometry.left() > initial_geometry.left()
    assert moved_geometry.top() > initial_geometry.top()


def test_prompt_editor_real_widget_repositions_panel_when_editor_resizes(
    widgets: list[QWidget],
) -> None:
    """Resizing the editor should recompute panel placement from the wrapped caret."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(640, 260)
    editor = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    editor.setGeometry(40, 40, 360, editor.minimumEditorHeight())
    host.show()
    host.activateWindow()
    editor.show()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "alpha alpha alpha alpha alpha, 1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    initial_geometry = panel.geometry()
    editor.resize(140, editor.height())
    process_events(app)

    resized_geometry = panel.geometry()
    assert resized_geometry != initial_geometry
    assert resized_geometry.top() > initial_geometry.top()


def test_prompt_editor_real_widget_repositions_panel_when_vertical_scrollbar_moves(
    widgets: list[QWidget],
) -> None:
    """Scrolling the editor viewport should reposition the active autocomplete panel."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(640, 260)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    editor.setPlainText(("alpha,\n" * 12) + "prefix, ")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    process_events(app)
    QTest.keyClicks(editor, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    scrollbar = editor.verticalScrollBar()
    assert scrollbar.maximum() > 0
    initial_geometry = panel.geometry()

    scrollbar.setValue(0)
    process_events(app)

    scrolled_geometry = panel.geometry()
    assert scrolled_geometry != initial_geometry
    assert scrolled_geometry.top() != initial_geometry.top()
