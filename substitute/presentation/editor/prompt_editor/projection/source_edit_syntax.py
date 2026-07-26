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

"""Classify incomplete syntax prefixes without mutable editor dependencies."""

from __future__ import annotations

SYNTAX_SENSITIVE_CHARACTERS = frozenset(("(", ")", "{", "}", "<", ">", ":", "\\", "*"))


def is_deferred_syntax_autocomplete_prefix(
    *,
    start: int,
    end: int,
    replacement_text: str,
    normalized_text: str,
    focused_token_range: tuple[int, int] | None,
) -> bool:
    """Return whether one edit leaves an incomplete, deferrable LoRA prefix."""

    if start != end or len(replacement_text) != 1:
        return False
    if replacement_text not in SYNTAX_SENSITIVE_CHARACTERS:
        return False
    if (
        focused_token_range is not None
        and focused_token_range[0] < start < focused_token_range[1]
    ):
        return False

    next_position = start + 1
    if next_position < 0 or next_position > len(normalized_text):
        return False
    line_start = normalized_text.rfind("\n", 0, next_position) + 1
    delimiter_start = normalized_text.rfind(",", line_start, next_position) + 1
    prefix_start = max(line_start, delimiter_start)
    if focused_token_range is not None and start in focused_token_range:
        prefix_start = max(prefix_start, start)
    while prefix_start < next_position and normalized_text[prefix_start].isspace():
        prefix_start += 1
    prefix = normalized_text[prefix_start:next_position].casefold()
    return prefix == "<" or (prefix.startswith("<lora:") and ">" not in prefix)


__all__ = ["SYNTAX_SENSITIVE_CHARACTERS", "is_deferred_syntax_autocomplete_prefix"]
