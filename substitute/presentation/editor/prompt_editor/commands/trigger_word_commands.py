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

"""Define identity-safe LoRA trigger-word insertion commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptEditingSession,
    PromptSourceEditOrigin,
    PromptSourceNormalizer,
    PromptUndoSnapshot,
)

from . import PromptCommandResult, PromptCommandSourceIdentity

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptTriggerWordInsertionRequest:
    """Describe one prepared prompt-aware trigger-word insertion."""

    trigger_words: str
    source_identity: PromptCommandSourceIdentity
    insert_position: int | None
    selection_start: int
    selection_end: int
    replace_selection: bool

    def __post_init__(self) -> None:
        """Reject invalid insertion requests before command execution."""

        if not self.trigger_words.strip():
            raise ValueError("trigger_words must not be blank")
        if self.selection_start < 0:
            raise ValueError("selection_start must be non-negative")
        if self.selection_end < self.selection_start:
            raise ValueError("selection_end must not precede selection_start")
        if self.insert_position is not None and self.insert_position < 0:
            raise ValueError("insert_position must be non-negative")


@dataclass(frozen=True, slots=True)
class PromptInsertTriggerWordsCommand(Generic[TPayload]):
    """Insert LoRA trigger words through one validated editing-session command."""

    request: PromptTriggerWordInsertionRequest
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "lora_insert_trigger_words"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Validate source identity and apply one prompt-aware insertion."""

        if not self.request.source_identity.matches(
            source_revision=session.source_revision,
            source_length=len(session.source_text),
        ):
            return PromptCommandResult.rejected(self.name, reason="stale_source")
        prepared = prepare_trigger_word_insertion(
            source_text=session.source_text,
            request=self.request,
        )
        if prepared is None:
            return PromptCommandResult.rejected(
                self.name, reason="invalid_source_range"
            )
        start, end, replacement_text = prepared
        source_change = session.replace_source_range(
            start=start,
            end=end,
            replacement_text=replacement_text,
            normalizer=self.normalizer,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            exact_source=self.exact_source,
            record_undo=True,
            undo_snapshot=self.undo_snapshot,
        )
        return PromptCommandResult.from_source_change(self.name, source_change)


def build_trigger_word_insertion_command(
    request: PromptTriggerWordInsertionRequest,
    *,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
) -> PromptInsertTriggerWordsCommand[TPayload]:
    """Return the executable command for one trigger-word request."""

    return PromptInsertTriggerWordsCommand(
        request=request,
        normalizer=normalizer,
        exact_source=exact_source,
        undo_snapshot=undo_snapshot,
    )


def prepare_trigger_word_insertion(
    *,
    source_text: str,
    request: PromptTriggerWordInsertionRequest,
) -> tuple[int, int, str] | None:
    """Return a safe replacement range and text for trigger-word insertion."""

    if request.replace_selection and request.selection_end > request.selection_start:
        if request.selection_end > len(source_text):
            return None
        return (
            request.selection_start,
            request.selection_end,
            request.trigger_words.strip(),
        )
    position = request.insert_position
    if position is None:
        position = request.selection_end
    if position > len(source_text):
        return None
    insertion_position = _segment_end(source_text, position)
    insertion_text = _delimited_trigger_words(
        source_text=source_text,
        insertion_position=insertion_position,
        trigger_words=request.trigger_words.strip(),
    )
    return insertion_position, insertion_position, insertion_text


def _segment_end(source_text: str, position: int) -> int:
    """Return the end of the comma- or line-delimited segment at a position."""

    for index in range(position, len(source_text)):
        if source_text[index] in {",", "\n"}:
            return index
    return len(source_text)


def _delimited_trigger_words(
    *,
    source_text: str,
    insertion_position: int,
    trigger_words: str,
) -> str:
    """Add only the separators needed at one prompt segment boundary."""

    left_text = source_text[:insertion_position]
    right_text = source_text[insertion_position:]
    left_trimmed = left_text.rstrip()
    prefix = ""
    suffix = ""
    if left_trimmed:
        prefix = " " if left_trimmed.endswith(",") else ", "
    if right_text and not right_text.startswith((",", "\n")):
        suffix = ", "
    return f"{prefix}{trigger_words}{suffix}"


__all__ = [
    "PromptInsertTriggerWordsCommand",
    "PromptTriggerWordInsertionRequest",
    "build_trigger_word_insertion_command",
    "prepare_trigger_word_insertion",
]
