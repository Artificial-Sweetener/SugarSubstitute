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

"""Define typed commands accepted by the prompt editing-session owner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from .cursor_state import PromptCursorState
from .source_commands import PromptSourceEditOrigin, PromptSourceNormalizer
from .transactions import PromptUndoSnapshot

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptReplaceRangeEdit(Generic[TPayload]):
    """Request one normalized replacement in source coordinates."""

    start: int
    end: int
    replacement_text: str
    normalizer: PromptSourceNormalizer
    origin: PromptSourceEditOrigin
    exact_source: bool
    record_undo: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    cursor_position: int | None = None
    anchor_position: int | None = None


@dataclass(frozen=True, slots=True)
class PromptReplaceDocumentEdit(Generic[TPayload]):
    """Request one complete prompt-source replacement."""

    text: str
    cursor_position: int
    anchor_position: int
    normalizer: PromptSourceNormalizer
    exact_source: bool
    record_undo: bool
    clear_history: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]


@dataclass(frozen=True, slots=True)
class PromptUndoEdit(Generic[TPayload]):
    """Request restoration of the preceding undo snapshot."""

    current_snapshot: PromptUndoSnapshot[TPayload]


@dataclass(frozen=True, slots=True)
class PromptRedoEdit(Generic[TPayload]):
    """Request restoration of the succeeding redo snapshot."""

    current_snapshot: PromptUndoSnapshot[TPayload]


@dataclass(frozen=True, slots=True)
class PromptSetCursorEdit:
    """Request one source-backed cursor and anchor state."""

    cursor_state: PromptCursorState


PromptSourceEditCommand: TypeAlias = (
    PromptReplaceRangeEdit[TPayload]
    | PromptReplaceDocumentEdit[TPayload]
    | PromptUndoEdit[TPayload]
    | PromptRedoEdit[TPayload]
)


__all__ = [
    "PromptRedoEdit",
    "PromptReplaceDocumentEdit",
    "PromptReplaceRangeEdit",
    "PromptSetCursorEdit",
    "PromptSourceEditCommand",
    "PromptUndoEdit",
]
