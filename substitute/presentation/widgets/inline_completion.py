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

"""Compute reusable display-only inline-completion suffixes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

InlineCompletionChannel = Literal["filename", "path", "friendly_name"]


@dataclass(frozen=True, slots=True)
class InlineCompletion:
    """Describe one display-only inline completion candidate."""

    channel: InlineCompletionChannel
    completed_text: str
    suffix_text: str


def inline_completion_suffix(
    *,
    typed_text: str,
    candidate_text: str,
    equivalent_characters: tuple[frozenset[str], ...] = (),
) -> str:
    """Return the candidate suffix when typed text matches the candidate prefix."""

    typed = str(typed_text)
    candidate = str(candidate_text)
    if not inline_completion_matches(
        typed_text=typed,
        candidate_text=candidate,
        equivalent_characters=equivalent_characters,
    ):
        return ""
    return candidate[len(typed) :]


def inline_completion_matches(
    *,
    typed_text: str,
    candidate_text: str,
    equivalent_characters: tuple[frozenset[str], ...] = (),
) -> bool:
    """Return whether typed text is a non-empty prefix-like candidate match."""

    typed = str(typed_text)
    candidate = str(candidate_text)
    if not typed or len(typed) > len(candidate):
        return False
    return all(
        _characters_match(
            typed_character,
            candidate_character,
            equivalent_characters,
        )
        for typed_character, candidate_character in zip(typed, candidate)
    )


def _characters_match(
    typed_character: str,
    candidate_character: str,
    equivalent_characters: tuple[frozenset[str], ...],
) -> bool:
    """Return whether two characters match by casefold or configured equivalence."""

    if typed_character.casefold() == candidate_character.casefold():
        return True
    typed_casefold = typed_character.casefold()
    candidate_casefold = candidate_character.casefold()
    return any(
        typed_casefold in equivalence and candidate_casefold in equivalence
        for equivalence in equivalent_characters
    )


__all__ = [
    "InlineCompletion",
    "InlineCompletionChannel",
    "inline_completion_matches",
    "inline_completion_suffix",
]
