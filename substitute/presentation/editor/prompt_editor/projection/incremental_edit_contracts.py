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

"""Define immutable contracts for source-local projection edits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)

from ..layout.contracts import PromptLayoutDamage


@dataclass(frozen=True, slots=True)
class PromptProjectionIncrementalEdit:
    """Describe one source edit considered for incremental projection."""

    start: int
    end: int
    replacement_text: str
    previous_source_text: str
    next_source_text: str


@dataclass(frozen=True, slots=True)
class PromptProjectionIncrementalDocumentResult:
    """Carry the updated projection document and its dirty boundaries."""

    projection_document: PromptProjectionDocument
    first_dirty_source_position: int
    first_dirty_projection_position: int
    reason: str
    edited_token_id: str | None = None
    projection_edit_start: int | None = None
    projection_edit_end: int | None = None
    projection_replacement_text: str | None = None


class PromptProjectionPlainTextApplyStatus(Enum):
    """Describe how one plain-text projection fast path handled an edit."""

    APPLIED = "applied"
    APPLIED_REFLOW = "applied_reflow"
    DEFERRED_WRAP_REFLOW = "deferred_wrap_reflow"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class PromptProjectionPlainTextApplyResult:
    """Carry the result of applying one plain-text projection edit to layout."""

    status: PromptProjectionPlainTextApplyStatus
    projection_document: PromptProjectionDocument | None = None
    layout_result: PromptLayoutDamage | None = None
    rejection_reason: str = ""


__all__ = [
    "PromptProjectionIncrementalDocumentResult",
    "PromptProjectionIncrementalEdit",
    "PromptProjectionPlainTextApplyResult",
    "PromptProjectionPlainTextApplyStatus",
]
