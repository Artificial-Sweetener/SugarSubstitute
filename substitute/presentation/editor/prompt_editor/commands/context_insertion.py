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

"""Own context-targeted prompt insertion command preparation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, Protocol, TypeVar

from substitute.application.prompt_editor.editing.structured_text import (
    PromptStructuredTextMutationService,
)
from substitute.domain.prompt.document.ranges import SourceRange

from ..core.editing.source_commands import PromptSourceEditOrigin
from ..core.state.revisions import PromptSourceIdentity
from .contracts import (
    PromptCommandResult,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
)
from .source_service import PromptSourceCommandService
from .trigger_word_commands import (
    PromptTriggerWordCommandService,
    PromptTriggerWordInsertionRequest,
)

TPayload = TypeVar("TPayload")


class PromptCommandCursor(Protocol):
    """Expose source-backed cursor reads for context insertion."""

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether source text is selected."""

    def selectionStart(self) -> int:  # noqa: N802
        """Return the selected source start."""

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the selected source end."""

    def position(self) -> int:
        """Return the live source cursor position."""


class PromptCommandContextInsertState(Protocol):
    """Expose a context-menu insertion target captured at menu opening."""

    @property
    def insert_position(self) -> int | None:
        """Return the captured source position."""

    @property
    def should_replace_selection(self) -> bool | None:
        """Return whether a live selection should be replaced."""


class PromptContextMenuTextInsertionExecutor(Protocol):
    """Insert prompt text at a prepared context-menu target."""

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> object:
        """Commit one prompt-aware context insertion."""


class PromptTriggerWordInsertionExecutor(Protocol):
    """Insert trigger words through an identity-safe command boundary."""

    def execute_trigger_word_insertion(
        self,
        *,
        trigger_words: str,
        source_identity: PromptSourceIdentity,
    ) -> object:
        """Commit one trigger-word insertion."""


class PromptContextInsertionService(Generic[TPayload]):
    """Prepare context insertion and commit through focused command services."""

    def __init__(
        self,
        *,
        source_commands: PromptSourceCommandService[TPayload],
        trigger_word_commands: PromptTriggerWordCommandService[TPayload],
        cursor_provider: Callable[[], PromptCommandCursor],
        context_insert_state_provider: Callable[[], PromptCommandContextInsertState],
        source_text_provider: Callable[[], str],
        structured_text_mutations: PromptStructuredTextMutationService,
        focus_restorer: Callable[[], None],
    ) -> None:
        """Store context target, structured text, and command collaborators."""

        self._source_commands = source_commands
        self._trigger_word_commands = trigger_word_commands
        self._cursor_provider = cursor_provider
        self._context_insert_state_provider = context_insert_state_provider
        self._source_text_provider = source_text_provider
        self._structured_text_mutations = structured_text_mutations
        self._focus_restorer = focus_restorer

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[TPayload]:
        """Insert text at the captured context-menu target."""

        cursor = self._cursor_provider()
        insert_state = self._context_insert_state_provider()
        source_range = self._insertion_range(cursor, insert_state)
        structured_replacement = self._structured_text_mutations.replacement_for_range(
            self._source_text_provider(),
            SourceRange(source_range.start, source_range.end),
            insertion_text,
        )
        if structured_replacement is None:
            self._focus_restorer()
            return PromptCommandResult.rejected(
                command_name,
                reason="prompt_value_unavailable",
            )
        result = self._source_commands.execute_source_replacement(
            PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(
                    structured_replacement.source_range.start,
                    structured_replacement.source_range.end,
                ),
                replacement_text=structured_replacement.replacement_text,
                origin=PromptSourceEditOrigin.PROGRAMMATIC,
                exact_source=structured_replacement.exact_source,
                record_undo=True,
                cursor_position=structured_replacement.cursor_position,
            ),
            command_name=command_name,
            finish_pending_key_edits=True,
        )
        self._focus_restorer()
        return result

    def execute_trigger_word_insertion(
        self,
        *,
        trigger_words: str,
        source_identity: PromptSourceIdentity,
    ) -> PromptCommandResult[TPayload]:
        """Insert trigger words at the captured prompt-aware target."""

        cursor = self._cursor_provider()
        insert_state = self._context_insert_state_provider()
        result = self._trigger_word_commands.execute(
            PromptTriggerWordInsertionRequest(
                trigger_words=trigger_words,
                source_identity=source_identity,
                insert_position=insert_state.insert_position,
                selection_start=cursor.selectionStart(),
                selection_end=cursor.selectionEnd(),
                replace_selection=(
                    cursor.hasSelection()
                    and insert_state.should_replace_selection is not False
                ),
            )
        )
        self._focus_restorer()
        return result

    @staticmethod
    def _insertion_range(
        cursor: PromptCommandCursor,
        insert_state: PromptCommandContextInsertState,
    ) -> PromptCommandSourceRange:
        """Return the source range targeted by one context insertion."""

        if cursor.hasSelection() and insert_state.should_replace_selection is not False:
            return PromptCommandSourceRange(
                cursor.selectionStart(),
                cursor.selectionEnd(),
            )
        if insert_state.insert_position is not None:
            return PromptCommandSourceRange(
                insert_state.insert_position,
                insert_state.insert_position,
            )
        return PromptCommandSourceRange(cursor.position(), cursor.position())


__all__ = [
    "PromptCommandContextInsertState",
    "PromptCommandCursor",
    "PromptContextMenuTextInsertionExecutor",
    "PromptContextInsertionService",
    "PromptTriggerWordInsertionExecutor",
]
