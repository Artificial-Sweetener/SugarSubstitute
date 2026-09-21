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

"""Execute prepared prompt-diagnostic actions and their provider side effects."""

from __future__ import annotations

from typing import Protocol

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
from substitute.presentation.editor.prompt_editor.commands.diagnostic_commands import (
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptDuplicateEmphasisDiagnosticAction,
    PromptDuplicateIgnoreDiagnosticAction,
    PromptDuplicateRemovalDiagnosticAction,
    PromptSpellingDictionaryAddDiagnosticAction,
    PromptSpellingIgnoreDiagnosticAction,
    PromptSpellingReplacementDiagnosticAction,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)


class PromptDiagnosticActionHost(Protocol):
    """Describe the editor command boundary used by diagnostic actions."""

    def setFocus(self) -> None:
        """Focus the prompt editor after an accepted source mutation."""

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return the current source identity for prepared commands."""

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]:
        """Execute one prepared diagnostic action through editor commands."""


class PromptDiagnosticSpellcheckProvider(Protocol):
    """Describe spellcheck side effects owned outside editor commands."""

    def ignore_word_for_session(self, word: str) -> None:
        """Ignore one spelling word for the current provider session."""

    def add_word_to_dictionary(self, word: str) -> bool:
        """Persist one spelling word and report whether state changed."""

    def dictionary_add_supported(self) -> bool:
        """Return whether persistent dictionary additions are supported."""


class PromptDiagnosticActionProviders(Protocol):
    """Expose providers required by diagnostic action side effects."""

    @property
    def spellcheck_provider(self) -> PromptDiagnosticSpellcheckProvider | None:
        """Return the active spellcheck provider when available."""


class PromptDiagnosticsRefreshRequester(Protocol):
    """Describe diagnostics refresh after provider state changes."""

    def refresh_now(self) -> None:
        """Request a current diagnostics refresh."""


class PromptDiagnosticActionDispatcher:
    """Own diagnostic command dispatch, focus, and provider follow-up."""

    def __init__(
        self,
        *,
        host: PromptDiagnosticActionHost,
        providers: PromptDiagnosticActionProviders,
        refresh_requester: PromptDiagnosticsRefreshRequester,
    ) -> None:
        """Store the command host and diagnostic side-effect collaborators."""

        self._host = host
        self._providers = providers
        self._refresh_requester = refresh_requester

    def source_identity_for_action(self) -> PromptSourceIdentity | None:
        """Return the current source identity for menu-built actions."""

        return self._host.prompt_command_source_identity()

    def replace_spelling_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        replacement: str,
        *,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Replace one spelling diagnostic and restore editor focus."""

        result = self._host.execute_diagnostic_action(
            PromptSpellingReplacementDiagnosticAction(
                diagnostic=diagnostic,
                replacement_text=replacement,
                source_identity=self._action_identity(source_identity),
            )
        )
        if result.status != "rejected":
            self._host.setFocus()

    def ignore_spelling_diagnostic_for_session(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Validate and ignore one spelling word for the current session."""

        provider = self._providers.spellcheck_provider
        if provider is None:
            return
        result = self._host.execute_diagnostic_action(
            PromptSpellingIgnoreDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._action_identity(source_identity),
            )
        )
        if result.status == "rejected" or result.spelling_word is None:
            return
        provider.ignore_word_for_session(result.spelling_word)
        self._refresh_requester.refresh_now()

    def add_spelling_diagnostic_to_dictionary(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Validate and persist one spelling word when supported."""

        provider = self._providers.spellcheck_provider
        if provider is None:
            return
        result = self._host.execute_diagnostic_action(
            PromptSpellingDictionaryAddDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._action_identity(source_identity),
            )
        )
        if result.status == "rejected" or result.spelling_word is None:
            return
        if provider.add_word_to_dictionary(result.spelling_word):
            self._refresh_requester.refresh_now()

    def dictionary_add_supported(self) -> bool:
        """Return whether the active provider supports dictionary additions."""

        provider = self._providers.spellcheck_provider
        return False if provider is None else provider.dictionary_add_supported()

    def remove_duplicate_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Remove one duplicate occurrence and restore editor focus."""

        result = self._host.execute_diagnostic_action(
            PromptDuplicateRemovalDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._action_identity(source_identity),
            )
        )
        if result.status != "rejected":
            self._host.setFocus()

    def emphasize_first_duplicate_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Emphasize the first duplicate occurrence and restore focus."""

        result = self._host.execute_diagnostic_action(
            PromptDuplicateEmphasisDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._action_identity(source_identity),
            )
        )
        if result.status != "rejected":
            self._host.setFocus()

    def ignore_duplicate_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
        *,
        source_identity: PromptSourceIdentity | None = None,
    ) -> str | None:
        """Validate one session ignore and return its diagnostic identifier."""

        result = self._host.execute_diagnostic_action(
            PromptDuplicateIgnoreDiagnosticAction(
                diagnostic=diagnostic,
                source_identity=self._action_identity(source_identity),
            )
        )
        if result.status == "rejected":
            return None
        return result.ignored_diagnostic_id

    def _action_identity(
        self,
        source_identity: PromptSourceIdentity | None,
    ) -> PromptSourceIdentity | None:
        """Return the supplied or current source identity for an action."""

        return source_identity or self._host.prompt_command_source_identity()


__all__ = [
    "PromptDiagnosticActionDispatcher",
    "PromptDiagnosticActionHost",
    "PromptDiagnosticActionProviders",
    "PromptDiagnosticSpellcheckProvider",
    "PromptDiagnosticsRefreshRequester",
]
