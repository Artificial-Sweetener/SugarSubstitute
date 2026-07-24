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

"""Define prompt spellcheck models in raw prompt source coordinates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptSpellcheckCandidate:
    """Describe one prompt source range eligible for spellchecking."""

    source_start: int
    source_end: int
    text: str


@dataclass(frozen=True, slots=True)
class PromptSpellingIssue:
    """Describe one misspelled prompt word in raw source coordinates."""

    source_start: int
    source_end: int
    word: str


@dataclass(frozen=True, slots=True)
class PromptSpellcheckSnapshot:
    """Store spellcheck results for one prompt source revision."""

    source_text: str
    language_tag: str
    issues: tuple[PromptSpellingIssue, ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptSpellingSuggestionSet:
    """Store lazily loaded suggestions for one misspelled prompt word."""

    word: str
    suggestions: tuple[str, ...]
    unavailable_reason: str | None = None


__all__ = [
    "PromptSpellcheckCandidate",
    "PromptSpellcheckSnapshot",
    "PromptSpellingIssue",
    "PromptSpellingSuggestionSet",
]
