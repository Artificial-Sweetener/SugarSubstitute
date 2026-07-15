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

"""Coordinate prompt-aware spellcheck snapshots and lazy suggestions."""

from __future__ import annotations

from dataclasses import dataclass
import sys

from substitute.application.ports import SpellCheckGateway
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_warning,
)

from .prompt_spellcheck_candidates import PromptSpellcheckCandidateService
from .prompt_spellcheck_models import (
    PromptSpellcheckSnapshot,
    PromptSpellingIssue,
    PromptSpellingSuggestionSet,
)

_LOGGER = get_logger("application.prompt_editor.spellcheck")


@dataclass(frozen=True, slots=True)
class _SuggestionCacheKey:
    """Identify one lazy suggestion lookup."""

    normalized_word: str
    language_tag: str
    backend_identity: str
    session_revision: int


class PromptSpellcheckService:
    """Build prompt spellcheck snapshots from prompt-filtered word candidates."""

    def __init__(
        self,
        *,
        gateway: SpellCheckGateway,
        candidate_service: PromptSpellcheckCandidateService,
        language_tag: str = "en_US",
        backend_name: str = "spellcheck",
    ) -> None:
        """Store backend and prompt-aware filtering collaborators."""

        self._gateway = gateway
        self._candidate_service = candidate_service
        self._language_tag = language_tag
        self._backend_name = backend_name
        self._ignored_words: set[str] = set()
        self._suggestion_cache: dict[
            _SuggestionCacheKey, PromptSpellingSuggestionSet
        ] = {}
        self._session_revision = 0

    @property
    def language_tag(self) -> str:
        """Return the active spellcheck language tag."""

        return self._language_tag

    def dictionary_add_supported(self) -> bool:
        """Return whether persistent dictionary additions are supported."""

        try:
            return (
                self._gateway.is_available() and self._gateway.supports_persistent_add()
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Failed to query spellcheck dictionary-add support",
                platform=sys.platform,
                language_tag=self._language_tag,
                backend=self._backend_name,
            )
            return False

    def snapshot_for_text(self, text: str) -> PromptSpellcheckSnapshot:
        """Return spelling issues for one prompt source snapshot."""

        gateway_available = self._gateway.is_available()
        if not gateway_available:
            reason = self._gateway.availability_reason()
            log_warning(
                _LOGGER,
                "Prompt spellcheck backend unavailable",
                platform=sys.platform,
                language_tag=self._language_tag,
                backend=self._backend_name,
                reason=reason or "",
            )
            return PromptSpellcheckSnapshot(
                source_text=text,
                language_tag=self._language_tag,
                issues=(),
                unavailable_reason=reason,
            )
        try:
            candidates = self._candidate_service.candidates_for_text(text)
            unique_words = {
                _normalize_word(candidate.text)
                for candidate in candidates
                if _normalize_word(candidate.text) not in self._ignored_words
            }
            rejected_words = {
                word for word in unique_words if not self._gateway.check_word(word)
            }
            issues = tuple(
                PromptSpellingIssue(
                    source_start=candidate.source_start,
                    source_end=candidate.source_end,
                    word=candidate.text,
                )
                for candidate in candidates
                if _normalize_word(candidate.text) in rejected_words
            )
            return PromptSpellcheckSnapshot(
                source_text=text,
                language_tag=self._language_tag,
                issues=issues,
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Prompt spellcheck snapshot failed",
                platform=sys.platform,
                language_tag=self._language_tag,
                backend=self._backend_name,
            )
            return PromptSpellcheckSnapshot(
                source_text=text,
                language_tag=self._language_tag,
                issues=(),
                unavailable_reason="Spellcheck failed for this prompt refresh.",
            )

    def suggestions_for_word(
        self,
        word: str,
        *,
        limit: int = 8,
    ) -> PromptSpellingSuggestionSet:
        """Return cached or freshly loaded suggestions for one rejected word."""

        normalized_word = _normalize_word(word)
        cache_key = _SuggestionCacheKey(
            normalized_word=normalized_word,
            language_tag=self._language_tag,
            backend_identity=self._backend_name,
            session_revision=self._session_revision,
        )
        cached = self._suggestion_cache.get(cache_key)
        if cached is not None:
            return cached
        if not self._gateway.is_available():
            result = PromptSpellingSuggestionSet(
                word=word,
                suggestions=(),
                unavailable_reason=self._gateway.availability_reason(),
            )
            self._suggestion_cache[cache_key] = result
            return result
        try:
            result = PromptSpellingSuggestionSet(
                word=word,
                suggestions=tuple(self._gateway.suggest(word, limit=limit)[:limit]),
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Prompt spellcheck suggestion lookup failed",
                platform=sys.platform,
                language_tag=self._language_tag,
                backend=self._backend_name,
                word=word,
            )
            result = PromptSpellingSuggestionSet(
                word=word,
                suggestions=(),
                unavailable_reason="Suggestions are unavailable.",
            )
        self._suggestion_cache[cache_key] = result
        return result

    def ignore_word_for_session(self, word: str) -> None:
        """Suppress one word for the current application spellcheck session."""

        normalized_word = _normalize_word(word)
        self._ignored_words.add(normalized_word)
        self._session_revision += 1
        if (
            not self._gateway.is_available()
            or not self._gateway.supports_session_ignore()
        ):
            return
        try:
            self._gateway.ignore_for_session(word)
        except Exception:
            log_exception(
                _LOGGER,
                "Prompt spellcheck session ignore failed",
                platform=sys.platform,
                language_tag=self._language_tag,
                backend=self._backend_name,
                word=word,
            )

    def add_word_to_dictionary(self, word: str) -> bool:
        """Persist one accepted word when the backend supports it."""

        if (
            not self._gateway.is_available()
            or not self._gateway.supports_persistent_add()
        ):
            return False
        try:
            accepted = self._gateway.add_to_dictionary(word)
        except Exception:
            log_exception(
                _LOGGER,
                "Prompt spellcheck dictionary add failed",
                platform=sys.platform,
                language_tag=self._language_tag,
                backend=self._backend_name,
                word=word,
            )
            return False
        if accepted:
            self.ignore_word_for_session(word)
        return accepted


def _normalize_word(word: str) -> str:
    """Return a case-insensitive dictionary key for one prompt word."""

    return word.casefold()


__all__ = ["PromptSpellcheckService"]
