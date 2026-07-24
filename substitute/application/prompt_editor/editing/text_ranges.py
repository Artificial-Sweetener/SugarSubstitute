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

"""Compute bounded text ranges used by prompt-editor caret services."""

from __future__ import annotations


def trim_horizontal_start(text: str, start: int, end: int) -> int:
    """Return the first non-horizontal-whitespace offset inside a range."""

    index = start
    while index < end and text[index] in " \t":
        index += 1
    return index


def trim_horizontal_end(text: str, start: int, end: int) -> int:
    """Return the exclusive end before trailing horizontal whitespace."""

    index = end
    while index > start and text[index - 1] in " \t":
        index -= 1
    return index


def line_start_within_bounds(text: str, *, lower_bound: int, position: int) -> int:
    """Return the start of the current physical line inside one bounded range."""

    line_feed_index = text.rfind("\n", lower_bound, position)
    carriage_return_index = text.rfind("\r", lower_bound, position)
    line_break_index = max(line_feed_index, carriage_return_index)
    if line_break_index < 0:
        return lower_bound
    return line_break_index + 1


def line_end_within_bounds(text: str, *, position: int, upper_bound: int) -> int:
    """Return the end of the current physical line inside one bounded range."""

    line_feed_index = text.find("\n", position, upper_bound)
    carriage_return_index = text.find("\r", position, upper_bound)
    line_break_indexes = [
        index for index in (line_feed_index, carriage_return_index) if index >= 0
    ]
    if not line_break_indexes:
        return upper_bound
    return min(line_break_indexes)


def line_visible_start(text: str, *, line_start: int, position: int) -> int:
    """Return the first non-horizontal-whitespace position before the caret."""

    index = line_start
    while index < position and text[index] in " \t":
        index += 1
    return index


__all__ = [
    "line_end_within_bounds",
    "line_start_within_bounds",
    "line_visible_start",
    "trim_horizontal_end",
    "trim_horizontal_start",
]
