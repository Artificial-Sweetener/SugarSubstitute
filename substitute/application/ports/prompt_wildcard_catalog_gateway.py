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

"""Define wildcard catalog lookup contracts used by prompt syntax services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .prompt_autocomplete_gateway import PromptAutocompleteSuggestion


@dataclass(frozen=True, slots=True)
class PromptWildcardReference:
    """Describe one wildcard reference extracted from a prompt snapshot."""

    identifier: str
    wildcard_form: str
    csv_column: str | None = None
    tag: str | None = None


@dataclass(frozen=True, slots=True)
class PromptWildcardResolution:
    """Describe catalog resolution state for one prompt wildcard reference."""

    identifier: str
    wildcard_form: str
    exists: bool
    csv_column: str | None = None
    matched_csv_column: str | None = None
    available_csv_columns: tuple[str, ...] = ()


@runtime_checkable
class PromptWildcardCatalogGateway(Protocol):
    """Resolve and search wildcard metadata for prompt editor workflows."""

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return catalog resolution state aligned with the supplied reference order."""

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return wildcard file suggestions for one typed wildcard prefix."""


__all__ = [
    "PromptWildcardCatalogGateway",
    "PromptWildcardReference",
    "PromptWildcardResolution",
]
