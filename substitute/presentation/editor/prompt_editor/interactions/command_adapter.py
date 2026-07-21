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

"""Route host-facing prompt commands through one typed adapter boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptMutationService,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.application.prompt_editor.prompt_structured_text_mutation_service import (
    PromptStructuredTextMutationService,
)
from substitute.domain.prompt import SourceRange

from ..commands import (
    PromptAutocompleteAcceptance,
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    PromptTriggerWordInsertionRequest,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
)
from ..editing_session import PromptSourceEditOrigin


class PromptCommandCursor(Protocol):
    """Describe source-backed cursor reads needed for text insertion commands."""

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether source text is currently selected."""

    def selectionStart(self) -> int:  # noqa: N802
        """Return one selected source endpoint."""

    def selectionEnd(self) -> int:  # noqa: N802
        """Return one selected source endpoint."""

    def position(self) -> int:
        """Return the current source cursor position."""


class PromptCommandContextInsertState(Protocol):
    """Describe the active context-menu insertion target."""

    @property
    def insert_position(self) -> int | None:
        """Return the source position captured at context-menu opening."""

    @property
    def should_replace_selection(self) -> bool | None:
        """Return whether insertion should replace the live selection."""


class PromptCommandExecutionPort(Protocol):
    """Describe the current executor behind host-facing prompt commands."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the current source identity for prepared commands."""

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[Any]:
        """Execute one prepared autocomplete acceptance."""

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[Any]:
        """Execute one prepared diagnostic action."""

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[Any]:
        """Execute one prepared weight action."""

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[Any]:
        """Execute one prepared reorder commit."""

    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[Any]:
        """Execute one prepared source replacement."""

    def execute_trigger_word_insertion(
        self,
        request: PromptTriggerWordInsertionRequest,
    ) -> PromptCommandResult[Any]:
        """Execute one identity-safe trigger-word insertion."""

    def set_plain_text(self, text: str) -> None:
        """Replace the full source text through the command executor."""

    def set_source_text(self, text: str) -> None:
        """Replace the full exact source text through the command executor."""

    def replace_baseline_text(self, text: str, *, exact_source: bool = False) -> None:
        """Replace the undo baseline source text through the command executor."""

    def replace_document_text(self, text: str) -> None:
        """Replace document text through the command executor."""

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Replace document text with prepared prompt state."""


class PromptContextMenuTextInsertionExecutor(Protocol):
    """Describe context-menu text insertion owned by the command adapter."""

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[object]:
        """Insert text at the active context-menu target."""


class PromptTriggerWordInsertionExecutor(Protocol):
    """Describe identity-safe trigger-word insertion command execution."""

    def execute_trigger_word_insertion(
        self,
        *,
        trigger_words: str,
        source_identity: PromptCommandSourceIdentity,
    ) -> PromptCommandResult[object]:
        """Insert trigger words through the identity-safe command boundary."""


class PromptEditorCommandAdapter:
    """Own host command adaptation while the router executes mutations."""

    def __init__(
        self,
        *,
        executor: PromptCommandExecutionPort,
        source_identity_provider: Callable[[], PromptCommandSourceIdentity]
        | None = None,
        cursor_provider: Callable[[], PromptCommandCursor],
        context_insert_state_provider: Callable[[], PromptCommandContextInsertState],
        focus_restorer: Callable[[], None],
        source_text_provider: Callable[[], str] | None = None,
        structured_text_mutations: PromptStructuredTextMutationService | None = None,
    ) -> None:
        """Store command collaborators without taking over command construction."""

        self._executor = executor
        self._source_identity_provider = source_identity_provider
        self._cursor_provider = cursor_provider
        self._context_insert_state_provider = context_insert_state_provider
        self._focus_restorer = focus_restorer
        self._source_text_provider = source_text_provider
        self._structured_text_mutations = structured_text_mutations

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the current source identity for prepared prompt commands."""

        if self._source_identity_provider is not None:
            return self._source_identity_provider()
        return self._executor.prompt_command_source_identity()

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[object]:
        """Execute one prepared autocomplete acceptance through the executor."""

        return cast(
            PromptCommandResult[object],
            self._executor.execute_autocomplete_acceptance(acceptance),
        )

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]:
        """Execute one prepared diagnostic action through the executor."""

        return cast(
            PromptDiagnosticCommandResult[object],
            self._executor.execute_diagnostic_action(action),
        )

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]:
        """Execute one prepared weight action through the executor."""

        return cast(
            PromptWeightCommandResult[object],
            self._executor.execute_weight_action(
                request,
                mutation_service=mutation_service,
                syntax_service=syntax_service,
                syntax_profile=syntax_profile,
            ),
        )

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[object]:
        """Execute one prepared reorder commit through the executor."""

        return cast(
            PromptReorderCommandResult[object],
            self._executor.execute_reorder_action(
                request,
                mutation_service=mutation_service,
                syntax_service=syntax_service,
                syntax_profile=syntax_profile,
            ),
        )

    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[object]:
        """Execute one prepared source replacement through the executor."""

        return cast(
            PromptCommandResult[object],
            self._executor.execute_source_replacement(
                replacement,
                command_name=command_name,
            ),
        )

    def execute_trigger_word_insertion(
        self,
        *,
        trigger_words: str,
        source_identity: PromptCommandSourceIdentity,
    ) -> PromptCommandResult[object]:
        """Insert trigger words at a prompt-safe context-menu boundary."""

        cursor = self._cursor_provider()
        insert_state = self._context_insert_state_provider()
        request = PromptTriggerWordInsertionRequest(
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
        result = cast(
            PromptCommandResult[object],
            self._executor.execute_trigger_word_insertion(request),
        )
        self._focus_restorer()
        return result

    def set_plain_text(self, text: str) -> None:
        """Replace the full source text through the executor."""

        self._executor.set_plain_text(text)

    def set_source_text(self, text: str) -> None:
        """Replace the full exact source text through the executor."""

        self._executor.set_source_text(text)

    def replace_baseline_text(self, text: str, *, exact_source: bool = False) -> None:
        """Replace the undo baseline source text through the executor."""

        self._executor.replace_baseline_text(text, exact_source=exact_source)

    def replace_document_text(self, text: str) -> None:
        """Replace document text through the executor."""

        self._executor.replace_document_text(text)

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Replace document text with prepared prompt state through the executor."""

        self._executor.replace_document_text_with_prompt_state(
            text,
            document_view=document_view,
            render_plan=render_plan,
        )

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[object]:
        """Insert text at the active context-menu target and restore focus."""

        cursor = self._cursor_provider()
        insert_state = self._context_insert_state_provider()
        source_range = self._context_menu_insertion_range(cursor, insert_state)
        replacement_text = insertion_text
        exact_source = False
        cursor_position: int | None = None
        if (
            self._source_text_provider is not None
            and self._structured_text_mutations is not None
        ):
            structured_replacement = (
                self._structured_text_mutations.replacement_for_range(
                    self._source_text_provider(),
                    SourceRange(source_range.start, source_range.end),
                    insertion_text,
                )
            )
            if structured_replacement is None:
                self._focus_restorer()
                return PromptCommandResult.rejected(
                    command_name,
                    reason="prompt_value_unavailable",
                )
            source_range = PromptCommandSourceRange(
                structured_replacement.source_range.start,
                structured_replacement.source_range.end,
            )
            replacement_text = structured_replacement.replacement_text
            exact_source = structured_replacement.exact_source
            cursor_position = structured_replacement.cursor_position
        result = self.execute_source_replacement(
            PromptCommandTextReplacement(
                source_range=source_range,
                replacement_text=replacement_text,
                origin=PromptSourceEditOrigin.PROGRAMMATIC,
                exact_source=exact_source,
                record_undo=True,
                cursor_position=cursor_position,
            ),
            command_name=command_name,
        )
        self._focus_restorer()
        return result

    def _context_menu_insertion_range(
        self,
        cursor: PromptCommandCursor,
        insert_state: PromptCommandContextInsertState,
    ) -> PromptCommandSourceRange:
        """Return the source range targeted by one context-menu insertion."""

        insert_position = insert_state.insert_position
        should_replace_selection = insert_state.should_replace_selection
        if cursor.hasSelection() and should_replace_selection is not False:
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
        elif insert_position is not None:
            start = insert_position
            end = insert_position
        else:
            start = cursor.position()
            end = cursor.position()
        return PromptCommandSourceRange(start=start, end=end)


__all__ = [
    "PromptCommandContextInsertState",
    "PromptCommandCursor",
    "PromptCommandExecutionPort",
    "PromptContextMenuTextInsertionExecutor",
    "PromptEditorCommandAdapter",
]
