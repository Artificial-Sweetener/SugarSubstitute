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

"""Scan prompt delimiters with shared quote and escape semantics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptParenthesisPair:
    """Describe one balanced, unescaped parenthesis pair."""

    opening_index: int
    closing_index: int
    depth: int


def is_escaped_prompt_character(text: str, index: int) -> bool:
    """Return whether an odd backslash run escapes one source character."""

    slash_count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        slash_count += 1
        cursor -= 1
    return slash_count % 2 == 1


def is_structural_quote(text: str, index: int, quote: str) -> bool:
    """Return whether a quote mark is structural rather than an apostrophe."""

    if quote != "'":
        return True
    previous_character = text[index - 1] if index > 0 else ""
    next_character = text[index + 1] if index + 1 < len(text) else ""
    return not (previous_character.isalnum() and next_character.isalnum())


def balanced_parenthesis_pairs(text: str) -> tuple[PromptParenthesisPair, ...]:
    """Return balanced parentheses outside quotes and escaped source regions."""

    stack: list[int] = []
    pairs: list[PromptParenthesisPair] = []
    quote: str | None = None
    angle_depth = 0
    for index, character in enumerate(text):
        if is_escaped_prompt_character(text, index):
            continue
        if quote is not None:
            if character == quote and is_structural_quote(text, index, quote):
                quote = None
            continue
        if character == "<":
            angle_depth += 1
            continue
        if character == ">" and angle_depth:
            angle_depth -= 1
            continue
        if (
            character in "\"'"
            and angle_depth == 0
            and is_structural_quote(text, index, character)
        ):
            quote = character
            continue
        if angle_depth:
            continue
        if character == "(":
            stack.append(index)
            continue
        if character == ")" and stack:
            opening_index = stack.pop()
            pairs.append(
                PromptParenthesisPair(
                    opening_index=opening_index,
                    closing_index=index,
                    depth=len(stack) + 1,
                )
            )
    return tuple(sorted(pairs, key=lambda pair: pair.opening_index))


__all__ = [
    "PromptParenthesisPair",
    "balanced_parenthesis_pairs",
    "is_escaped_prompt_character",
    "is_structural_quote",
]
