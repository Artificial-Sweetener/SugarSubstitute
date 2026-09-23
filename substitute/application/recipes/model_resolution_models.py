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

"""Define portable recipe model-resolution outcomes and unresolved state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from substitute.application.recipes.model_download_candidate import (
    RecipeModelDownloadCandidate,
)
from substitute.domain.model_metadata import CivitaiLookupStatus
from substitute.domain.recipes import ParsedSugarScript


class RecipeModelCivitaiState(str, Enum):
    """Describe CivitAI missing-model lookup state for one recipe reference."""

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not-found"
    FOUND = "found"
    NO_SAFE_FILE = "no-safe-file"


@dataclass(frozen=True, slots=True)
class RecipeModelUnresolvedReference:
    """Describe one recipe model reference that needs user action."""

    alias: str
    node_name: str
    input_key: str
    kind: str
    value: str
    sha256: str
    civitai_state: RecipeModelCivitaiState
    civitai_status: CivitaiLookupStatus | None = None
    civitai_error: str | None = None
    candidate: RecipeModelDownloadCandidate | None = None


@dataclass(frozen=True, slots=True)
class RecipeModelResolutionSummary:
    """Summarize pre-materialization model resolution results."""

    literal_matches: int = 0
    hash_matches: int = 0
    unresolved_hashes: int = 0


@dataclass(frozen=True, slots=True)
class ResolvedRecipeModelScript:
    """Carry a parsed script plus model resolution summary."""

    parsed_script: ParsedSugarScript
    summary: RecipeModelResolutionSummary


class RecipeModelResolutionRequired(ValueError):
    """Raised when a recipe references missing hashes requiring user action."""

    def __init__(
        self,
        *,
        references: tuple[RecipeModelUnresolvedReference, ...],
        partial_script: ParsedSugarScript,
        summary: RecipeModelResolutionSummary,
    ) -> None:
        """Store the structured unresolved state used by the resolver wizard."""

        missing = ", ".join(
            f"{reference.alias}.{reference.node_name}.{reference.input_key} "
            f"({reference.sha256[:12]})"
            for reference in references
        )
        super().__init__(
            f"Recipe references model hashes that are not installed locally: {missing}"
        )
        self.references = references
        self.partial_script = partial_script
        self.summary = summary


__all__ = [
    "RecipeModelCivitaiState",
    "RecipeModelResolutionRequired",
    "RecipeModelResolutionSummary",
    "RecipeModelUnresolvedReference",
    "ResolvedRecipeModelScript",
]
