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

"""Test source cursor session ownership."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.editing.cursor import (
    PromptCursorSession,
)
from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.core.editing.selection import (
    PromptSelection,
)


def test_cursor_session_clamps_and_selects_all_source() -> None:
    """Keep source cursor state clamped and selection-backed."""

    session = PromptCursorSession()

    assert session.set_positions(
        cursor_position=12,
        anchor_position=3,
        source_length=7,
    ) == PromptCursorState(cursor_position=7, anchor_position=3)
    assert session.selection() == PromptSelection(anchor_position=3, cursor_position=7)
    assert session.select_all(source_length=5) == PromptCursorState(
        cursor_position=5,
        anchor_position=0,
    )
