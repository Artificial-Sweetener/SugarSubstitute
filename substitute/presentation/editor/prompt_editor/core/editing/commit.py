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

"""Define the sole immutable result of a prompt editing transaction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Generic, TypeVar

from substitute.application.prompt_editor.editing.literal_parentheses import (
    PromptParenthesisTransition,
)

from .cursor_state import PromptCursorState
from .source_buffer import PromptSourceSnapshot
from .source_commands import PromptSourceEditOrigin, PromptSourceTextEdit
from .transactions import PromptUndoAvailabilityChange, PromptUndoSnapshot

TPayload = TypeVar("TPayload")


class PromptEditScope(Enum):
    """Identify the lifecycle semantics of one committed source transaction."""

    RANGE = "range"
    DOCUMENT = "document"
    HISTORY = "history"


@dataclass(frozen=True, slots=True)
class PromptEditCommit(Generic[TPayload]):
    """Carry one authoritative source transaction into downstream projection."""

    previous_snapshot: PromptSourceSnapshot
    next_snapshot: PromptSourceSnapshot
    previous_cursor_state: PromptCursorState
    cursor_state: PromptCursorState
    origin: PromptSourceEditOrigin
    scope: PromptEditScope
    source_edit: PromptSourceTextEdit | None
    requested_start: int
    requested_end: int
    requested_replacement_text: str
    transitions: tuple[PromptParenthesisTransition, ...] = ()
    undo_availability_change: PromptUndoAvailabilityChange | None = None
    restored_undo_snapshot: PromptUndoSnapshot[TPayload] | None = None
    prepared_state: object | None = None

    def __post_init__(self) -> None:
        """Reject commits whose bounded edit or identity lineage is inconsistent."""

        if self.previous_snapshot.identity.source_revision > (
            self.next_snapshot.identity.source_revision
        ):
            raise ValueError("An edit commit cannot move source revision backwards.")
        previous_length = self.previous_snapshot.source_length
        if not 0 <= self.requested_start <= self.requested_end <= previous_length:
            raise ValueError("Requested edit range is outside the previous source.")
        if self.source_changed and self.source_edit is None:
            raise ValueError("A changed edit commit requires one bounded source edit.")
        if not self.source_changed and self.source_edit is not None:
            raise ValueError("An unchanged edit commit cannot carry a source edit.")
        if (
            self.source_changed
            and self.next_snapshot.identity.source_revision
            <= self.previous_snapshot.identity.source_revision
        ):
            raise ValueError("A changed edit commit must advance source revision.")

    @property
    def source_changed(self) -> bool:
        """Return whether this commit changed source text."""

        return (
            self.previous_snapshot.source_revision != self.next_snapshot.source_revision
        )

    @property
    def cursor_changed(self) -> bool:
        """Return whether this commit changed cursor or selection state."""

        return self.previous_cursor_state != self.cursor_state

    def with_prepared_state(
        self, prepared_state: object
    ) -> "PromptEditCommit[TPayload]":
        """Attach an already-built semantic value outside the ordinary edit path."""

        return replace(self, prepared_state=prepared_state)


__all__ = ["PromptEditCommit", "PromptEditScope"]
