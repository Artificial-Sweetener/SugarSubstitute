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

"""Define undoable prompt edit transaction value types."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
    PromptGeneratedEmphasis,
)

from .cursor_state import PromptCursorState
from .parenthesis_intent import PromptParenthesisIntent

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptUndoSnapshot(Generic[TPayload]):
    """Capture source and cursor state with passive restoration payload data."""

    source_text: str
    cursor_state: PromptCursorState
    source_revision: int | None = field(default=None, compare=False)
    comparison_payload: Hashable | None = None
    restoration_payload: TPayload | None = field(default=None, compare=False)
    parenthesis_intents: tuple[PromptParenthesisIntent, ...] = ()
    generated_emphases: tuple[PromptGeneratedEmphasis, ...] = ()

    def __post_init__(self) -> None:
        """Reject invalid revision identities before stack owners store them."""

        if self.source_revision is not None and self.source_revision < 0:
            raise ValueError("Source revision must be non-negative.")


@dataclass(frozen=True, slots=True)
class PromptEditTransaction(Generic[TPayload]):
    """Describe one undoable edit as a before and after snapshot pair."""

    before_snapshot: PromptUndoSnapshot[TPayload]
    after_snapshot: PromptUndoSnapshot[TPayload]

    @property
    def has_changes(self) -> bool:
        """Return whether the transaction changes undo-relevant state."""

        return self.before_snapshot != self.after_snapshot


@dataclass(frozen=True, slots=True)
class PromptUndoAvailability:
    """Report whether undo and redo actions are currently available."""

    can_undo: bool
    can_redo: bool


@dataclass(frozen=True, slots=True)
class PromptUndoAvailabilityChange:
    """Report undo and redo availability before and after a stack mutation."""

    previous: PromptUndoAvailability
    current: PromptUndoAvailability

    @property
    def changed(self) -> bool:
        """Return whether either availability flag changed."""

        return self.previous != self.current

    @property
    def undo_changed(self) -> bool:
        """Return whether undo availability changed."""

        return self.previous.can_undo != self.current.can_undo

    @property
    def redo_changed(self) -> bool:
        """Return whether redo availability changed."""

        return self.previous.can_redo != self.current.can_redo


@dataclass(frozen=True, slots=True)
class PromptUndoRestoreResult(Generic[TPayload]):
    """Return the snapshot to restore and any availability transition it caused."""

    snapshot: PromptUndoSnapshot[TPayload]
    availability_change: PromptUndoAvailabilityChange


__all__ = [
    "PromptEditTransaction",
    "PromptUndoAvailability",
    "PromptUndoAvailabilityChange",
    "PromptUndoRestoreResult",
    "PromptUndoSnapshot",
]
