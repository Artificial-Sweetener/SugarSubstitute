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

"""Dispatch committed source edits to their scope-specific application owners."""

from __future__ import annotations

from typing import Generic, TypeVar

from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
    PromptEditScope,
)

from .source_document_commit_application import PromptSourceDocumentCommitApplication
from .source_history_commit_application import PromptSourceHistoryCommitApplication
from .source_range_commit_application import PromptSourceRangeCommitApplication

TProjectionPayload = TypeVar("TProjectionPayload")


class PromptProjectionSourceCommitApplication(Generic[TProjectionPayload]):
    """Own the exhaustive mapping from commit scope to application owner."""

    def __init__(
        self,
        *,
        document: PromptSourceDocumentCommitApplication[TProjectionPayload],
        history: PromptSourceHistoryCommitApplication[TProjectionPayload],
        range_edit: PromptSourceRangeCommitApplication[TProjectionPayload],
    ) -> None:
        """Store the three complete scope-specific application owners."""

        self._document = document
        self._history = history
        self._range_edit = range_edit

    def apply_edit_commit(
        self,
        commit: PromptEditCommit[TProjectionPayload],
    ) -> None:
        """Apply one commit through the sole owner for its declared scope."""

        if commit.scope is PromptEditScope.HISTORY:
            self._history.apply(commit)
            return
        if commit.scope is PromptEditScope.RANGE:
            self._range_edit.apply(commit)
            return
        if commit.scope is PromptEditScope.DOCUMENT:
            self._document.apply(commit)
            return
        raise ValueError(f"Unsupported prompt edit scope: {commit.scope!r}")


__all__ = ["PromptProjectionSourceCommitApplication"]
