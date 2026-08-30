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

"""Provide spellcheck doubles for diagnostics context-menu tests."""

from __future__ import annotations

from substitute.application.prompt_editor.diagnostics.spellcheck_models import (
    PromptSpellingSuggestionSet,
)


class _FakeSpellcheckService:
    """Provide prepared spelling suggestions and dictionary actions."""

    def __init__(self) -> None:
        """Initialize suggestion and dictionary call recording."""

        self.suggestion_words: list[str] = []
        self.ignored_words: list[str] = []
        self.added_words: list[str] = []

    def suggestions_for_word(
        self,
        word: str,
        *,
        limit: int = 8,
    ) -> PromptSpellingSuggestionSet:
        """Return one deterministic spelling suggestion."""

        _ = limit
        self.suggestion_words.append(word)
        return PromptSpellingSuggestionSet(word=word, suggestions=("type",))

    def ignore_word_for_session(self, word: str) -> None:
        """Record ignored spelling words."""

        self.ignored_words.append(word)

    def add_word_to_dictionary(self, word: str) -> bool:
        """Record persistent dictionary additions."""

        self.added_words.append(word)
        return True

    def dictionary_add_supported(self) -> bool:
        """Return dictionary add support for menu actions."""

        return True
