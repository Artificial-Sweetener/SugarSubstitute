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

"""Adapt prompt spellcheck snapshots into generic prompt diagnostics."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text

from substitute.application.prompt_editor.prompt_diagnostics_models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDiagnosticSnapshot,
    PromptSpellingDiagnosticPayload,
)

from .prompt_diagnostics_service import PromptDiagnosticProviderResult
from .prompt_spellcheck_service import PromptSpellcheckService


class PromptSpellcheckDiagnosticProvider:
    """Convert prompt spellcheck service output into generic diagnostics."""

    def __init__(self, service: PromptSpellcheckService) -> None:
        """Store the existing spellcheck service adapter."""

        self._service = service

    @property
    def language_tag(self) -> str:
        """Return the active spellcheck language tag."""

        return self._service.language_tag

    def snapshot_for_text(self, text: str) -> PromptDiagnosticSnapshot:
        """Return generic diagnostics for spelling issues in source text."""

        snapshot = self._service.snapshot_for_text(text)
        return PromptDiagnosticSnapshot(
            source_text=snapshot.source_text,
            diagnostics=tuple(
                PromptDiagnostic(
                    diagnostic_id=_spelling_diagnostic_id(
                        source_start=issue.source_start,
                        source_end=issue.source_end,
                        word=issue.word,
                    ),
                    kind=PromptDiagnosticKind.SPELLING,
                    severity=PromptDiagnosticSeverity.ERROR,
                    source_start=issue.source_start,
                    source_end=issue.source_end,
                    message=app_text("Possible spelling issue: %1", issue.word),
                    payload=PromptSpellingDiagnosticPayload(word=issue.word),
                )
                for issue in snapshot.issues
            ),
            unavailable_reason=snapshot.unavailable_reason,
        )

    def diagnostics_for_text(self, text: str) -> PromptDiagnosticProviderResult:
        """Return spelling diagnostics for service composition."""

        snapshot = self.snapshot_for_text(text)
        return PromptDiagnosticProviderResult(
            diagnostics=snapshot.diagnostics,
            unavailable_reason=snapshot.unavailable_reason,
        )

    def suggestions_for_word(self, word: str, *, limit: int = 8) -> object:
        """Return lazy spelling suggestions for one word."""

        return self._service.suggestions_for_word(word, limit=limit)

    def ignore_word_for_session(self, word: str) -> None:
        """Suppress one spelling word for the active session."""

        self._service.ignore_word_for_session(word)

    def add_word_to_dictionary(self, word: str) -> bool:
        """Persist one spelling word when the backend supports it."""

        return self._service.add_word_to_dictionary(word)

    def dictionary_add_supported(self) -> bool:
        """Return whether persistent dictionary additions are supported."""

        return self._service.dictionary_add_supported()


def _spelling_diagnostic_id(
    *,
    source_start: int,
    source_end: int,
    word: str,
) -> str:
    """Return the deterministic spelling diagnostic identity."""

    return f"spelling:{source_start}:{source_end}:{word.casefold()}"


__all__ = ["PromptSpellcheckDiagnosticProvider"]
