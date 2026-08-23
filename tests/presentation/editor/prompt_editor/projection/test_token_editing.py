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

"""Verify direct editing of collapsed prompt-projection tokens."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    set_prompt_cursor_position as _set_cursor_position,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    first_emphasis_token as _first_emphasis_token,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_projection_token_editing_typing_inside_collapsed_emphasis_keeps_token_collapsed(
    widgets: list[QWidget],
) -> None:
    """Typing inside visible emphasis content should not force raw expansion."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    token = _first_emphasis_token(box)
    assert token.content_end is not None

    _set_cursor_position(box, token.content_end)
    process_events(app)
    QTest.keyClicks(box, "s")
    process_events(app)

    next_token = _first_emphasis_token(box)
    assert box.toPlainText() == "(cats:1.05), suffix"
    assert surface_for(box).projection_document().tokens != ()
    assert next_token.display_text == "cats"
    assert box.textCursor().position() == next_token.content_end


def test_projection_token_editing_delete_inside_collapsed_emphasis_keeps_token_collapsed(
    widgets: list[QWidget],
) -> None:
    """Delete inside visible emphasis content should mutate source without expansion."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    token = _first_emphasis_token(box)
    assert token.content_start is not None

    _set_cursor_position(box, token.content_start + 1)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Delete)
    process_events(app)

    next_token = _first_emphasis_token(box)
    assert box.toPlainText() == "(ct:1.05), suffix"
    assert surface_for(box).projection_document().tokens != ()
    assert next_token.display_text == "ct"


def test_projection_token_editing_backspace_inside_collapsed_emphasis_keeps_token_collapsed(
    widgets: list[QWidget],
) -> None:
    """Backspace inside visible emphasis content should mutate source without expansion."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    token = _first_emphasis_token(box)
    assert token.content_start is not None

    _set_cursor_position(box, token.content_start + 2)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app)

    next_token = _first_emphasis_token(box)
    assert box.toPlainText() == "(ct:1.05), suffix"
    assert surface_for(box).projection_document().tokens != ()
    assert next_token.display_text == "ct"


def test_projection_token_editing_invalid_raw_edit_stays_expanded_until_parse_recovers(
    widgets: list[QWidget],
) -> None:
    """Invalid raw edits should remain expanded instead of collapsing prematurely."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    token = _first_emphasis_token(box)
    token_rect = surface_for(box)._layout.frame.geometry.tokens.token_rect(
        token, scroll_offset=0.0
    )  # noqa: SLF001
    assert token_rect is not None

    QTest.mouseDClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=token_rect.center().toPoint(),
    )
    process_events(app)
    QTest.keyClicks(box, "(broken")
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert box.toPlainText() == "(broken, suffix"
    assert surface_for(box).projection_document().tokens == ()


def test_projection_token_backspace_at_collapsed_emphasis_edge_preserves_expand_contract(
    widgets: list[QWidget],
) -> None:
    """Existing collapsed inline tokens should still expand before shell deletion."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    token = _first_emphasis_token(box)
    _set_cursor_position(box, token.source_end)

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app)

    assert box.toPlainText() == "(cat:1.05), suffix"
    assert box.textCursor().selectionStart() == token.source_start
    assert box.textCursor().selectionEnd() == token.source_end
