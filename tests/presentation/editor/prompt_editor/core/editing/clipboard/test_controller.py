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

"""Test source-backed clipboard intent ownership."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.editing.clipboard import (
    PromptClipboardController,
)
from substitute.presentation.editor.prompt_editor.core.editing.selection import (
    PromptSelection,
)


def test_clipboard_controller_reports_copy_cut_and_paste_source_ranges() -> None:
    """Report source-backed clipboard intents without mutating source text."""

    controller = PromptClipboardController()
    selection = PromptSelection(anchor_position=1, cursor_position=5)

    assert controller.copy(source_text="abcdef", selection=selection).text == "bcde"
    assert controller.cut(source_text="abcdef", selection=selection) is not None
    cut_result = controller.cut(source_text="abcdef", selection=selection)
    assert cut_result is not None
    assert cut_result.text == "bcde"
    assert (cut_result.start, cut_result.end) == (1, 5)
    paste_result = controller.paste(
        pasted_text="XYZ",
        source_text="abcdef",
        selection=selection,
    )
    assert (paste_result.start, paste_result.end, paste_result.text) == (1, 5, "XYZ")


def test_clipboard_controller_cut_ignores_empty_selection() -> None:
    """Avoid fabricating a deletion intent for an empty selection."""

    result = PromptClipboardController().cut(
        source_text="abcdef",
        selection=PromptSelection(anchor_position=3, cursor_position=3),
    )

    assert result is None
