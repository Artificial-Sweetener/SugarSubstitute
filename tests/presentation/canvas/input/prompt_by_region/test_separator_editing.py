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

"""Verify direct editing of Prompt by Region separators."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    set_prompt_cursor_position as _set_cursor_position,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_projection_region_separator_backspace_deletes_only_closing_bracket(
    widgets: list[QWidget],
) -> None:
    """Backspace on the line below a separator should make the marker malformed."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="global\n[SEP]\nregional",
        width=240,
    )
    token = next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )
    _set_cursor_position(box, token.source_end)

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app)

    assert box.toPlainText() == "global\n[SEP\nregional"
    assert not any(
        item.kind is PromptProjectionTokenKind.REGION_SEPARATOR
        for item in surface_for(box).projection_document().tokens
    )


def test_projection_region_separator_delete_removes_only_opening_bracket(
    widgets: list[QWidget],
) -> None:
    """Delete on the line above a separator should make the marker malformed."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="global\n[SEP]\nregional",
        width=240,
    )
    token = next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )
    _set_cursor_position(box, token.source_start)

    QTest.keyClick(box, Qt.Key.Key_Delete)
    process_events(app)

    assert box.toPlainText() == "global\nSEP]\nregional"
    assert not any(
        item.kind is PromptProjectionTokenKind.REGION_SEPARATOR
        for item in surface_for(box).projection_document().tokens
    )
