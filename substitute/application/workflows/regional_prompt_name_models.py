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

"""Describe canonical regional prompt name synchronization results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegionalPromptSourceReplacement:
    """Describe one exact source edit used to synchronize a prompt value."""

    source_start: int
    source_end: int
    replacement_text: str


@dataclass(frozen=True, slots=True)
class RegionalPromptSourceUpdate:
    """Describe one canonical prompt value changed by regional-name synchronization."""

    node_name: str
    field_key: str
    source_text: str
    replacements: tuple[RegionalPromptSourceReplacement, ...]


@dataclass(frozen=True, slots=True)
class RegionalPromptNameSynchronization:
    """Describe canonical prompt values changed by one synchronization pass."""

    section_key: str
    updates: tuple[RegionalPromptSourceUpdate, ...] = ()


__all__ = [
    "RegionalPromptNameSynchronization",
    "RegionalPromptSourceReplacement",
    "RegionalPromptSourceUpdate",
]
