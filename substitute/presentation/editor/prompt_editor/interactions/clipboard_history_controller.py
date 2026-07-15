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
from typing import Generic, Protocol, TypeVar, cast

from ..commands import (
    PromptClipboardCommandResult,
    PromptCopySelectionCommand,
    PromptCutSelectionCommand,
    PromptPasteTextCommand,
    PromptSelectAllCommand,
)
from ..editing_session import (
    PromptCursorState,
    PromptEditingSessionRestoreResult,
    PromptSourceEditOrigin,
)
from ..editing_session.edit_controller import PromptEditController

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


class PromptClipboardHistorySink(Protocol[TPayload]):
    """Apply clipboard/history effects to the current presentation sink."""

    def set_clipboard_history_cursor_state(
        self,
        cursor_state: PromptCursorState,
    ) -> None:
        """Apply a command-produced cursor state."""

    def restore_clipboard_history_state(
        self,
        restore_result: PromptEditingSessionRestoreResult[TPayload],
    ) -> None:
        """Apply one undo or redo restoration."""


class PromptDanbooruPasteScheduler(Protocol):
    """Schedule Danbooru URL paste handling before literal paste fallback."""

    def try_schedule_clipboard_danbooru_paste(self, text: str) -> bool:
        """Return whether the pasted text was scheduled as a Danbooru import."""


class PromptClipboardSourceReplacementExecutor(Protocol):
    """Replace source ranges prepared by clipboard/history commands."""

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str = "replace_source_range",
        record_undo: bool = True,
    ) -> object:
        """Replace one prepared source range through the command router."""


@dataclass(frozen=True, slots=True)
class PromptClipboardHistoryController(Generic[TPayload]):
    """Own user-facing clipboard and history routing for one prompt editor."""

    edit_controller: PromptEditController[TPayload]
    clipboard: PromptTextClipboard
    sink: PromptClipboardHistorySink[TPayload]
    source_replacement_executor: PromptClipboardSourceReplacementExecutor
    danbooru_paste_scheduler: PromptDanbooruPasteScheduler
    editing_enabled: Callable[[], bool]
    paste_completed: Callable[[str], None] = _ignore_paste_completion

    def copy(self) -> None:
        """Copy selected raw source text to the system clipboard."""

        result = cast(
            PromptClipboardCommandResult[TPayload],
            self.edit_controller.dispatch_command(PromptCopySelectionCommand()),
        )
        self.clipboard.set_text(result.clipboard_text or "")

    def cut(self) -> None:
        """Cut selected raw source text when editing is enabled."""

        if not self._editing_enabled():
            return
        self.edit_controller.finish_pending_key_edit_block(reason="cut")
        result = cast(
            PromptClipboardCommandResult[TPayload],
            self.edit_controller.dispatch_command(PromptCutSelectionCommand()),
        )
        if result.source_range is None:
            return
        self.clipboard.set_text(result.clipboard_text or "")
        self.source_replacement_executor.replace_source_range(
            start=result.source_range.start,
            end=result.source_range.end,
            replacement_text=result.replacement_text or "",
            origin=PromptSourceEditOrigin.TYPED,
        )

    def paste(self) -> None:
        """Paste clipboard text when editing is enabled."""

        if not self._editing_enabled():
            return
        self.edit_controller.finish_pending_key_edit_block(reason="paste")
        clipboard_text = self.clipboard.text()
        if self.danbooru_paste_scheduler.try_schedule_clipboard_danbooru_paste(
            clipboard_text
        ):
            self.paste_completed("paste")
            return
        result = cast(
            PromptClipboardCommandResult[TPayload],
            self.edit_controller.dispatch_command(
                PromptPasteTextCommand(clipboard_text)
            ),
        )
        if result.source_range is None or result.replacement_text is None:
            return
        self.source_replacement_executor.replace_source_range(
            start=result.source_range.start,
            end=result.source_range.end,
            replacement_text=result.replacement_text,
            origin=PromptSourceEditOrigin.PASTE,
        )
        self.paste_completed("paste")

    def select_all(self) -> None:
        """Select the full raw source text."""

        self.edit_controller.finish_pending_key_edit_block(reason="select_all")
        result = self.edit_controller.dispatch_command(
            PromptSelectAllCommand[TPayload]()
        )
        if result.cursor_state is None:
            return
        self.sink.set_clipboard_history_cursor_state(result.cursor_state)

    def undo(self) -> None:
        """Restore the previous raw prompt source snapshot."""

        self.edit_controller.finish_pending_key_edit_block(reason="undo")
        restore_result = self.edit_controller.undo()
        if restore_result is not None:
            self.sink.restore_clipboard_history_state(restore_result)

    def redo(self) -> None:
        """Reapply the next raw prompt source snapshot."""

        self.edit_controller.finish_pending_key_edit_block(reason="redo")
        restore_result = self.edit_controller.redo()
        if restore_result is not None:
            self.sink.restore_clipboard_history_state(restore_result)

    def _editing_enabled(self) -> bool:
        """Return whether mutating clipboard actions may edit source."""

        return self.editing_enabled()


__all__ = [
    "PromptClipboardHistoryActions",
    "PromptClipboardHistoryController",
    "PromptClipboardHistorySink",
    "PromptClipboardSourceReplacementExecutor",
    "PromptDanbooruPasteScheduler",
    "PromptTextClipboard",
]
