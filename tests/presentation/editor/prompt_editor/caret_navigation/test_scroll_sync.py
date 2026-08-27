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

"""Test prompt-editor caret and viewport synchronization."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    set_prompt_cursor_position,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_prompt_editor_enter_at_bottom_keeps_prompt_state_scroll_synced(
    widgets: list[QWidget],
) -> None:
    """Enter at the prompt bottom should not require a second scroll correction."""

    app = ensure_qapp()
    text = "\n".join(
        (
            "wide angle, foreground detail, layered composition, long line start",
            "group portrait",
            " 2 figures, conversation, layered background, reflective lighting, "
            "window shadows, table props, repeated descriptive words,",
            "landscape",
            " mountains, river, {seasonal_detail}1, distant village, morning fog, "
            "foreground leaves, repeated descriptive words,",
            "interior",
            " library shelves, window light, {seasonal_detail}1, desk, chair, "
            "maps, notebooks, repeated descriptive words,",
            "street",
            " market stalls, umbrellas, wet pavement, distant signs, layered crowd, "
            "overlapping shapes, repeated descriptive words,",
            "final scene",
            " calm ending line, seated figure, hands folded, warm light, "
            "background texture, repeated descriptive words, final phrase.",
        )
    )
    editor = show_prompt_editor(
        widgets,
        text=text,
        width=382,
        height=760,
    )
    set_prompt_cursor_position(editor, len(text))
    process_events(app)
    scroll_bar = editor.verticalScrollBar()
    scroll_bar.setValue(scroll_bar.maximum())
    process_events(app)

    QTest.keyClick(editor, Qt.Key.Key_Return)
    process_events(app)

    surface = surface_for(editor)
    assert cast(Any, surface)._caret_visibility_prompt_state_revision is None
    assert scroll_bar.maximum() - scroll_bar.value() <= editor.lineHeight()


def test_prompt_editor_ignores_programmatic_visible_scrollbar_resets(
    widgets: list[QWidget],
) -> None:
    """QFluent scrollbar mirror resets should not overwrite projection scroll."""

    app = ensure_qapp()
    editor = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(80)),
        width=592,
        height=260,
    )
    surface_scrollbar = editor.verticalScrollBar()
    surface_scrollbar.setValue(surface_scrollbar.maximum())
    process_events(app)
    bottom_scroll_value = surface_scrollbar.value()
    scroll_delegate = cast(Any, getattr(editor, "scrollDelegate"))
    visible_scrollbar = scroll_delegate.vScrollBar

    visible_scrollbar.setValue(0, False)
    process_events(app)

    assert bottom_scroll_value > 0
    assert surface_scrollbar.value() == bottom_scroll_value
