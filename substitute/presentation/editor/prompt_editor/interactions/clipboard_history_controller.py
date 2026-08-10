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

"""Route clipboard and history actions outside the projection surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from ..commands.execution import PromptEditExecution
from ..commands.source_service import PromptSourceCommandService
from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.source_commands import (
    PromptSourceEditOrigin,
)
from .text_mutation_controller import PromptTextMutationActions

TPayload = TypeVar("TPayload")


def _ignore_paste_completion(reason: str) -> None:
    """Provide a default no-op paste completion hook."""

    _ = reason


class PromptClipboardHistoryActions(Protocol):
    """Expose user-facing clipboard and history commands."""

    def copy(self) -> None:
        """Copy the current raw source selection."""

    def cut(self) -> None:
        """Cut the current raw source selection when editing is enabled."""

    def paste(self) -> None:
        """Paste clipboard text when editing is enabled."""

    def select_all(self) -> None:
        """Select all raw source text."""

    def undo(self) -> None:
        """Undo the previous source edit."""

    def redo(self) -> None:
        """Redo the next source edit."""


class PromptTextClipboard(Protocol):
    """Provide system clipboard text through a narrow adapter."""

    def text(self) -> str:
        """Return current clipboard text."""

    def set_text(self, text: str) -> None:
        """Replace current clipboard text."""


class PromptClipboardHistoryCursorSink(Protocol):
    """Apply clipboard cursor effects to the current presentation sink."""

    def set_clipboard_history_cursor_state(
        self,
        cursor_state: PromptCursorState,
    ) -> None:
        """Apply a command-produced cursor state."""


class PromptDanbooruPasteScheduler(Protocol):
    """Schedule Danbooru URL paste handling before literal paste fallback."""

    def try_schedule_clipboard_danbooru_paste(self, text: str) -> bool:
        """Return whether the pasted text was scheduled as a Danbooru import."""


@dataclass(frozen=True, slots=True)
class PromptClipboardHistoryController(Generic[TPayload]):
    """Own user-facing clipboard and history routing for one prompt editor."""

    edit_execution: PromptEditExecution[TPayload]
    clipboard: PromptTextClipboard
    cursor_sink: PromptClipboardHistoryCursorSink
    source_commands: PromptSourceCommandService[TPayload]
    text_mutations: PromptTextMutationActions
    danbooru_paste_scheduler: PromptDanbooruPasteScheduler
    editing_enabled: Callable[[], bool]
    paste_completed: Callable[[str], None] = _ignore_paste_completion

    def copy(self) -> None:
        """Copy selected raw source text to the system clipboard."""

        self.clipboard.set_text(self.edit_execution.session.copy().text)

    def cut(self) -> None:
        """Cut selected raw source text when editing is enabled."""

        if not self._editing_enabled():
            return
        self.edit_execution.finish_pending_key_edit_block(reason="cut")
        result = self.edit_execution.session.cut()
        if result is None:
            return
        self.clipboard.set_text(result.text)
        self.source_commands.replace_source_range(
            start=result.start,
            end=result.end,
            replacement_text="",
            origin=PromptSourceEditOrigin.TYPED,
            command_name="cut",
        )

    def paste(self) -> None:
        """Paste clipboard text when editing is enabled."""

        if not self._editing_enabled():
            return
        self.edit_execution.finish_pending_key_edit_block(reason="paste")
        clipboard_text = self.clipboard.text()
        if self.danbooru_paste_scheduler.try_schedule_clipboard_danbooru_paste(
            clipboard_text
        ):
            self.paste_completed("paste")
            return
        result = self.edit_execution.session.paste(clipboard_text)
        self.text_mutations.replace_text(
            start=result.start,
            end=result.end,
            replacement_text=result.text,
            origin=PromptSourceEditOrigin.PASTE,
            command_name="paste",
        )
        self.paste_completed("paste")

    def select_all(self) -> None:
        """Select the full raw source text."""

        self.edit_execution.finish_pending_key_edit_block(reason="select_all")
        self.cursor_sink.set_clipboard_history_cursor_state(
            self.edit_execution.session.select_all()
        )

    def undo(self) -> None:
        """Restore the previous raw prompt source snapshot."""

        self.edit_execution.finish_pending_key_edit_block(reason="undo")
        self.edit_execution.undo()

    def redo(self) -> None:
        """Reapply the next raw prompt source snapshot."""

        self.edit_execution.finish_pending_key_edit_block(reason="redo")
        self.edit_execution.redo()

    def _editing_enabled(self) -> bool:
        """Return whether mutating clipboard actions may edit source."""

        return self.editing_enabled()


__all__ = [
    "PromptClipboardHistoryActions",
    "PromptClipboardHistoryController",
    "PromptClipboardHistoryCursorSink",
    "PromptDanbooruPasteScheduler",
    "PromptTextClipboard",
]
