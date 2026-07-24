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

"""Define shared prompt-syntax constants and span kinds."""

from __future__ import annotations

from enum import Enum


class SyntaxKind(str, Enum):
    """Enumerate prompt syntax span categories."""

    EMPHASIS = "emphasis"
    LORA = "lora"
    WILDCARD = "wildcard"


class WildcardForm(str, Enum):
    """Enumerate supported wildcard placeholder forms."""

    SIMPLE = "simple"
    CSV = "csv"


BRACKET_PAIRS: dict[str, str] = {
    "(": ")",
    "[": "]",
    "{": "}",
    "<": ">",
}
QUOTE_CHARACTERS: frozenset[str] = frozenset({"'", '"'})
TOP_LEVEL_SEPARATOR_WHITESPACE = " \t\r\n"

__all__ = [
    "BRACKET_PAIRS",
    "QUOTE_CHARACTERS",
    "SyntaxKind",
    "TOP_LEVEL_SEPARATOR_WHITESPACE",
    "WildcardForm",
]
