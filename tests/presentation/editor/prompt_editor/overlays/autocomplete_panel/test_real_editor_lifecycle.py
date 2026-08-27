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

"""Test real-editor autocomplete panel lifecycle behavior."""

from __future__ import annotations

from typing import cast

from PySide6.QtTest import QTest
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
    editor_autocomplete_preview_text,
)


def test_prompt_editor_real_widget_hide_event_clears_autocomplete_state(
    widgets: list[QWidget],
) -> None:
    """Hiding the editor should clear both autocomplete surfaces immediately."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(editor) == "irl"

    editor.hide()
    process_events(app)

    assert panel.is_panel_visible() is False
    assert editor_autocomplete_preview_text(editor) == ""
