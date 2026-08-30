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

"""Provide the state-aware prompt editor double."""

from __future__ import annotations

from tests.presentation.editor.prompt_editor.interactions.support.editor import (
    ControllerEditorDouble,
    MenuCursorDouble,
)


class StateEditorDouble(ControllerEditorDouble):
    """Add mutation replacement tracking to the shared controller editor double."""

    def __init__(self, *, text: str, position: int) -> None:
        """Initialize the editor with matching click and caret cursors."""

        super().__init__(
            clicked_cursor=MenuCursorDouble(text=text, position=position),
            current_cursor=MenuCursorDouble(text=text, position=position),
            text=text,
        )
        self.replace_document_text_calls: list[str] = []
        self.replace_document_text_with_prompt_state_calls: list[
            tuple[str, object, object]
        ] = []
        self.blocked_signals: list[bool] = []

    def replace_document_text(self, text: str) -> None:
        """Replace backing text through the undo-safe surface hook."""

        self.setPlainText(text)
        self.replace_document_text_calls.append(text)

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: object,
        render_plan: object,
    ) -> None:
        """Replace backing text through the prompt-state optimized hook."""

        self.setPlainText(text)
        self.replace_document_text_with_prompt_state_calls.append(
            (text, document_view, render_plan)
        )

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        """Record signal blocking requested by controller mutations."""

        self.blocked_signals.append(blocked)
