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

"""Resolve one bounded source edit between immutable prompt snapshots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceTextEdit:
    """Describe one contiguous edit between projection source snapshots."""

    start: int
    end: int
    replacement_text: str


def single_source_text_edit(
    previous_text: str,
    next_text: str,
) -> PromptProjectionSourceTextEdit | None:
    """Return the single contiguous edit between two projection source strings."""

    if previous_text == next_text:
        return None
    prefix_length = 0
    common_length = min(len(previous_text), len(next_text))
    while (
        prefix_length < common_length
        and previous_text[prefix_length] == next_text[prefix_length]
    ):
        prefix_length += 1

    previous_suffix = len(previous_text)
    next_suffix = len(next_text)
    while (
        previous_suffix > prefix_length
        and next_suffix > prefix_length
        and previous_text[previous_suffix - 1] == next_text[next_suffix - 1]
    ):
        previous_suffix -= 1
        next_suffix -= 1
    return PromptProjectionSourceTextEdit(
        start=prefix_length,
        end=previous_suffix,
        replacement_text=next_text[prefix_length:next_suffix],
    )


__all__ = ["PromptProjectionSourceTextEdit", "single_source_text_edit"]
