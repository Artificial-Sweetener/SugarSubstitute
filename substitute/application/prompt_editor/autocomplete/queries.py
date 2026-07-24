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

"""Define prompt autocomplete query view models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptAutocompleteFallbackQuery:
    """Describe one fallback autocomplete request inside a larger active range."""

    prefix: str
    word_start: int
    word_end: int
    active_tag_end: int


@dataclass(frozen=True, slots=True)
class PromptAutocompleteQuery:
    """Describe one prompt-aware autocomplete replacement request."""

    prefix: str
    word_start: int
    word_end: int
    active_tag_end: int
    fallback_query: PromptAutocompleteFallbackQuery | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteQuery:
    """Describe one active curly wildcard autocomplete replacement request."""

    prefix: str
    opener_start: int
    content_start: int
    cursor_position: int
    replacement_end: int


@dataclass(frozen=True, slots=True)
class PromptSceneAutocompleteQuery:
    """Describe one active line-start scene autocomplete replacement request."""

    prefix: str
    marker_start: int
    title_start: int
    cursor_position: int
    replacement_end: int


__all__ = [
    "PromptAutocompleteFallbackQuery",
    "PromptAutocompleteQuery",
    "PromptSceneAutocompleteQuery",
    "PromptWildcardAutocompleteQuery",
]
