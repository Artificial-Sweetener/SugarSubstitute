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

"""Define pure autocomplete text matching helpers."""

from __future__ import annotations


def autocomplete_completion_suffix(suggestion: str, prefix: str) -> str:
    """Return the suffix a suggestion would append after one typed prefix."""

    if len(prefix) > len(suggestion):
        return ""

    for typed_character, suggestion_character in zip(prefix, suggestion):
        if not autocomplete_characters_match(typed_character, suggestion_character):
            return ""
    return suggestion[len(prefix) :]


def autocomplete_characters_match(
    typed_character: str,
    suggestion_character: str,
) -> bool:
    """Return whether two autocomplete characters match inline."""

    if typed_character == suggestion_character:
        return True
    return {typed_character, suggestion_character} == {"_", " "}


def autocomplete_suffix_without_existing_right_text(
    completion_suffix: str,
    right_text: str,
) -> str:
    """Return the suffix excluding compatible text already right of the caret."""

    if not completion_suffix or not right_text:
        return completion_suffix
    trimmed_right_text = right_text.rstrip(" \t")
    if not trimmed_right_text:
        return completion_suffix
    if len(trimmed_right_text) > len(completion_suffix):
        return completion_suffix
    suffix_tail = completion_suffix[-len(trimmed_right_text) :]
    if all(
        autocomplete_characters_match(typed_character, suggestion_character)
        for typed_character, suggestion_character in zip(
            trimmed_right_text,
            suffix_tail,
        )
    ):
        return completion_suffix[: -len(trimmed_right_text)]
    return completion_suffix


__all__ = [
    "autocomplete_characters_match",
    "autocomplete_completion_suffix",
    "autocomplete_suffix_without_existing_right_text",
]
