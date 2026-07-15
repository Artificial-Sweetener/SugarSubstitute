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

"""Define clipboard and source replacement commands for prompt editing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptEditingSession,
    PromptSourceNormalizer,
    PromptUndoSnapshot,
)

from . import (
    PromptCommandResult,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
)

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptClipboardCommandResult(PromptCommandResult[TPayload]):
    """Report clipboard command output without touching the system clipboard."""

    clipboard_text: str | None = None
    source_range: PromptCommandSourceRange | None = None
    replacement_text: str | None = None


@dataclass(frozen=True, slots=True)
class PromptReplaceSourceRangeCommand(Generic[TPayload]):
    """Replace one prepared source range through the editing session."""

    name: str
    replacement: PromptCommandTextReplacement
    normalizer: PromptSourceNormalizer
    undo_snapshot: PromptUndoSnapshot[TPayload]

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Apply this replacement through the supplied editing session."""

        source_change = session.replace_source_range(
            start=self.replacement.source_range.start,
            end=self.replacement.source_range.end,
            replacement_text=self.replacement.replacement_text,
            normalizer=self.normalizer,
            origin=self.replacement.origin,
            exact_source=self.replacement.exact_source,
            record_undo=self.replacement.record_undo,
            undo_snapshot=self.undo_snapshot,
        )
        return PromptCommandResult.from_source_change(self.name, source_change)


@dataclass(frozen=True, slots=True)
class PromptReplaceFullSourceCommand(Generic[TPayload]):
    """Replace the full prompt source through the editing session."""

    name: str
    text: str
    cursor_position: int
    anchor_position: int
    normalizer: PromptSourceNormalizer
    exact_source: bool
    record_undo: bool
    clear_history: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Apply this full-source replacement through the supplied session."""

        source_change = session.replace_full_source(
            self.text,
            cursor_position=self.cursor_position,
            anchor_position=self.anchor_position,
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            record_undo=self.record_undo,
            clear_history=self.clear_history,
            undo_snapshot=self.undo_snapshot,
        )
        return PromptCommandResult.from_source_change(self.name, source_change)


@dataclass(frozen=True, slots=True)
class PromptCopySelectionCommand(Generic[TPayload]):
    """Prepare selected raw source text for clipboard copy."""

    name: str = "copy_selection"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptClipboardCommandResult[TPayload]:
        """Return selected text without mutating source or cursor state."""

        result = session.copy()
        return PromptClipboardCommandResult(
            command_name=self.name,
            status="completed",
            cursor_state=session.cursor_state,
            clipboard_text=result.text,
        )


@dataclass(frozen=True, slots=True)
class PromptCutSelectionCommand(Generic[TPayload]):
    """Prepare selected raw source text and range for clipboard cut."""

    name: str = "cut_selection"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptClipboardCommandResult[TPayload]:
        """Return the selected source range to remove, if any."""

        result = session.cut()
        if result is None:
            return PromptClipboardCommandResult(
                command_name=self.name,
                status="noop",
                cursor_state=session.cursor_state,
                reason="empty_selection",
            )
        return PromptClipboardCommandResult(
            command_name=self.name,
            status="completed",
            cursor_state=session.cursor_state,
            clipboard_text=result.text,
            source_range=PromptCommandSourceRange(result.start, result.end),
            replacement_text="",
        )


@dataclass(frozen=True, slots=True)
class PromptPasteTextCommand(Generic[TPayload]):
    """Prepare one pasted text payload for insertion into the active selection."""

    pasted_text: str
    name: str = "paste_text"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptClipboardCommandResult[TPayload]:
        """Return the source range that should receive pasted text."""

        result = session.paste(self.pasted_text)
        return PromptClipboardCommandResult(
            command_name=self.name,
            status="completed",
            cursor_state=session.cursor_state,
            source_range=PromptCommandSourceRange(result.start, result.end),
            replacement_text=result.text,
        )


@dataclass(frozen=True, slots=True)
class PromptSelectAllCommand(Generic[TPayload]):
    """Select the full raw prompt source through the editing session."""

    name: str = "select_all"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Select the complete source text and return the committed cursor state."""

        cursor_state = session.select_all()
        return PromptCommandResult.completed(
            self.name,
            cursor_state=cursor_state,
        )


def normalized_clipboard_paste_text(
    text: str,
    *,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
) -> str:
    """Return the source text a normal paste would insert for stale checks."""

    if exact_source:
        return text
    return normalizer.normalize_for_storage(text).text


__all__ = [
    "PromptClipboardCommandResult",
    "PromptCopySelectionCommand",
    "PromptCutSelectionCommand",
    "PromptPasteTextCommand",
    "PromptReplaceFullSourceCommand",
    "PromptReplaceSourceRangeCommand",
    "PromptSelectAllCommand",
    "normalized_clipboard_paste_text",
]
