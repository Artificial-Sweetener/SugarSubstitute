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

"""Define feature-command requests and deterministic editing outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar

from ..core.editing.commit import PromptEditCommit
from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.session import PromptEditingSession
from ..core.editing.source_commands import PromptSourceEditOrigin
from ..core.editing.transactions import PromptUndoAvailabilityChange

TPayload = TypeVar("TPayload")

PromptCommandStatus = Literal["applied", "completed", "noop", "rejected"]


@dataclass(frozen=True, slots=True)
class PromptCommandSourceRange:
    """Describe a half-open source range used by prepared command requests."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Reject invalid ranges before command execution mutates source."""

        if self.start < 0:
            raise ValueError("Source range start must be non-negative.")
        if self.end < self.start:
            raise ValueError("Source range end must not precede start.")

    @property
    def length(self) -> int:
        """Return the number of source characters covered by this range."""

        return self.end - self.start

    @property
    def is_empty(self) -> bool:
        """Return whether this range covers no source characters."""

        return self.start == self.end

    def is_within(self, source_length: int) -> bool:
        """Return whether this range is valid for one source length."""

        if source_length < 0:
            raise ValueError("Source length must be non-negative.")
        return self.end <= source_length


@dataclass(frozen=True, slots=True)
class PromptCommandTextReplacement:
    """Describe one prepared replacement that a command can commit."""

    source_range: PromptCommandSourceRange
    replacement_text: str
    origin: PromptSourceEditOrigin
    exact_source: bool = False
    record_undo: bool = True
    cursor_position: int | None = None
    anchor_position: int | None = None


@dataclass(frozen=True, slots=True)
class PromptEditApplicationState:
    """Carry prepared semantic and bounded viewport follow-up for one commit."""

    document_view: object | None = None
    render_plan: object | None = None
    reset_scroll_to_top: bool = False
    schedule_geometry_reuse_warm_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptCommandResult(Generic[TPayload]):
    """Report the deterministic outcome of one feature command."""

    command_name: str
    status: PromptCommandStatus
    edit_commit: PromptEditCommit[TPayload] | None = None
    cursor_state: PromptCursorState | None = None
    undo_availability_change: PromptUndoAvailabilityChange | None = None
    reason: str | None = None

    @classmethod
    def applied(
        cls,
        command_name: str,
        edit_commit: PromptEditCommit[TPayload],
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for a command that committed one source transaction."""

        return cls(
            command_name=command_name,
            status="applied",
            edit_commit=edit_commit,
            cursor_state=edit_commit.cursor_state,
            undo_availability_change=edit_commit.undo_availability_change,
        )

    @classmethod
    def from_edit_commit(
        cls,
        command_name: str,
        edit_commit: PromptEditCommit[TPayload],
        *,
        noop_reason: str = "same_source",
    ) -> "PromptCommandResult[TPayload]":
        """Build an applied or no-op result from one editing commit."""

        return cls(
            command_name=command_name,
            status="applied" if edit_commit.source_changed else "noop",
            edit_commit=edit_commit,
            cursor_state=edit_commit.cursor_state,
            undo_availability_change=edit_commit.undo_availability_change,
            reason=None if edit_commit.source_changed else noop_reason,
        )

    @classmethod
    def completed(
        cls,
        command_name: str,
        *,
        cursor_state: PromptCursorState | None = None,
        reason: str | None = None,
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for a non-source command that completed."""

        return cls(
            command_name=command_name,
            status="completed",
            cursor_state=cursor_state,
            reason=reason,
        )

    @classmethod
    def noop(
        cls,
        command_name: str,
        *,
        cursor_state: PromptCursorState | None = None,
        reason: str | None = None,
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for an intentional no-op."""

        return cls(
            command_name=command_name,
            status="noop",
            cursor_state=cursor_state,
            reason=reason,
        )

    @classmethod
    def rejected(
        cls,
        command_name: str,
        *,
        reason: str,
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for a stale or invalid prepared command."""

        return cls(command_name=command_name, status="rejected", reason=reason)


class PromptEditorCommand(Protocol[TPayload]):
    """Prepare and commit one feature mutation through an editing session."""

    @property
    def name(self) -> str:
        """Return the stable command name used by diagnostics."""

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Commit this feature command through the editing-session owner."""


__all__ = [
    "PromptCommandResult",
    "PromptCommandSourceRange",
    "PromptCommandStatus",
    "PromptCommandTextReplacement",
    "PromptEditApplicationState",
    "PromptEditorCommand",
]
