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

"""Define prompt wildcard resolution value objects."""

from __future__ import annotations

from dataclasses import dataclass

from .syntax import WildcardForm


@dataclass(frozen=True, slots=True)
class PromptWildcardPlaceholder:
    """Represent one parsed wildcard placeholder in source text."""

    outer_start: int
    outer_end: int
    content_start: int
    content_end: int
    full_content: str
    wildcard_form: WildcardForm
    identifier: str
    csv_column: str | None = None
    tag: str | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardTextSource:
    """Describe line candidates loaded for one simple wildcard file."""

    source_id: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptWildcardCsvSource:
    """Describe row candidates loaded for one CSV wildcard file."""

    source_id: str
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class PromptWildcardReplacementDetail:
    """Describe source provenance for one wildcard replacement."""

    outer_text: str
    value: str
    wildcard_form: str
    identifier: str
    source_id: str
    selected_index: int
    line_number: int
    item_count: int
    tag: str | None = None
    csv_column: str | None = None
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardResolution:
    """Capture the output of resolving one prompt text snapshot."""

    source_text: str
    resolved_text: str
    replacements: tuple[tuple[str, str], ...]
    replacement_details: tuple[PromptWildcardReplacementDetail, ...] = ()


__all__ = [
    "PromptWildcardCsvSource",
    "PromptWildcardPlaceholder",
    "PromptWildcardReplacementDetail",
    "PromptWildcardResolution",
    "PromptWildcardTextSource",
]
