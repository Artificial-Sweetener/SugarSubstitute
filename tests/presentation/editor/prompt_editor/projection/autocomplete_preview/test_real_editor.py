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

"""Test real editor autocomplete preview projection behavior."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
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
from tests.support.prompt_editor.projection_engine_support import surface_for


def test_prompt_editor_real_widget_paints_preview_without_changing_projection_layout(
    widgets: list[QWidget],
) -> None:
    """Mid-prompt autocomplete preview should stay outside committed projection."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(420, 220)
    editor = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    editor.setGeometry(24, 24, 180, editor.minimumEditorHeight())
    host.show()
    host.activateWindow()
    editor.show()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    editor.setPlainText("alpha, , omega")
    cursor = editor.textCursor()
    cursor.setPosition(len("alpha, "), QTextCursor.MoveMode.MoveAnchor)
    editor.setTextCursor(cursor)
    process_events(app)

    QTest.keyClicks(editor, "1g")
    process_events(app)

    surface = surface_for(editor)
    assert editor_autocomplete_preview_text(editor) == "irl"
    assert surface.projection_document().source_text == "alpha, 1g, omega"
    assert surface.projection_document().projection_text == "alpha, 1g, omega"
    assert surface.active_projection_document().projection_text == (
        "alpha, 1girl, omega"
    )
    omega_fragment = next(
        fragment
        for fragment in surface._layout.frame.output.snapshot.text_fragments  # noqa: SLF001
        if fragment.text == "omega"
    )

    assert omega_fragment.run_id.startswith("text:")


def test_prompt_editor_real_widget_clears_stale_preview_before_retargeting(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatible typing should clear stale ghost geometry before retargeting."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway(
        {
            "1g": sample_suggestions(),
            "1gi": sample_suggestions(),
        }
    )
    host = QWidget()
    host.resize(420, 220)
    editor = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    editor.setGeometry(24, 24, 180, editor.minimumEditorHeight())
    host.show()
    host.activateWindow()
    editor.show()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "1g")
    process_events(app)

    surface = surface_for(editor)
    assert editor_autocomplete_preview_text(editor) == "irl"

    preview_updates: list[object | None] = []
    session = surface._session  # noqa: SLF001
    session_type = type(session)
    original_set_preview = PromptProjectionSession.set_autocomplete_preview

    def record_preview(
        target: PromptProjectionSession,
        preview: PromptAutocompletePreviewState | None,
    ) -> None:
        """Record projection preview state transitions during compatible typing."""

        if target is session:
            preview_updates.append(preview)
        original_set_preview(target, preview)

    monkeypatch.setattr(session_type, "set_autocomplete_preview", record_preview)

    QTest.keyClick(editor, Qt.Key.Key_I)
    process_events(app)

    assert editor.toPlainText() == "1gi"
    assert editor_autocomplete_preview_text(editor) == "rl"
    assert preview_updates[0] is None
    assert isinstance(preview_updates[-1], PromptAutocompletePreviewState)
