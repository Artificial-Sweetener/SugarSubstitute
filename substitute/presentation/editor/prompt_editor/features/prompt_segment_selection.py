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

"""Define saved prompt-segment selection and insertion boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.presentation.editor.prompt_editor.commands import PromptCommandResult


@dataclass(frozen=True, slots=True)
class PromptSegmentSelectionSnapshot:
    """Capture exact selected source text before menu side effects."""

    start: int
    end: int
    text: str

    def as_tuple(self) -> tuple[int, int, str]:
        """Return the shell selection tuple shape."""

        return (self.start, self.end, self.text)


@dataclass(frozen=True, slots=True)
class PromptSegmentContextInsertState:
    """Describe context-menu insertion state for saved segment inserts."""

    insert_position: int | None
    should_replace_selection: bool | None


class PromptSegmentCursor(Protocol):
    """Describe cursor reads needed for selection and insertion."""

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor currently selects source text."""

    def selectionStart(self) -> int:  # noqa: N802
        """Return one selection endpoint."""

    def selectionEnd(self) -> int:  # noqa: N802
        """Return one selection endpoint."""

    def position(self) -> int:
        """Return current source cursor position."""


class PromptSegmentPresetHost(Protocol):
    """Describe prompt-editor hooks needed by segment preset ownership."""

    def textCursor(self) -> PromptSegmentCursor:
        """Return a source-backed cursor."""

    def toPlainText(self) -> str:
        """Return current source text."""

    def prompt_command_source_identity(self) -> object | None:
        """Return current source identity when available."""

    def prompt_segment_dialog_parent(self) -> object:
        """Return parent object for save-segment dialogs."""

    def restore_prompt_segment_selection(self, *, start: int, end: int) -> None:
        """Restore a captured source selection."""


class PromptSegmentTextInsertionExecutor(Protocol):
    """Describe saved segment insertion routing."""

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[object]:
        """Insert text at the active context-menu target."""


__all__ = [
    "PromptSegmentContextInsertState",
    "PromptSegmentCursor",
    "PromptSegmentPresetHost",
    "PromptSegmentSelectionSnapshot",
    "PromptSegmentTextInsertionExecutor",
]
