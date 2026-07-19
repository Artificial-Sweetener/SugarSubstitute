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

"""Define user-managed prompt autocomplete list values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PromptAutocompleteListKind(StrEnum):
    """Classify a user tag list by its autocomplete effect."""

    CUSTOM = "custom"
    CENSORED = "censored"


@dataclass(frozen=True, slots=True)
class PromptAutocompleteList:
    """Describe one named, independently enabled line-based tag list."""

    id: str
    name: str
    kind: PromptAutocompleteListKind
    enabled: bool
    text: str


@dataclass(frozen=True, slots=True)
class PromptAutocompleteListSnapshot:
    """Carry normalized enabled-list content to autocomplete consumers."""

    custom_tags: tuple[str, ...] = ()
    censored_tags: frozenset[str] = frozenset()
    revision: int = 0


__all__ = [
    "PromptAutocompleteList",
    "PromptAutocompleteListKind",
    "PromptAutocompleteListSnapshot",
]
