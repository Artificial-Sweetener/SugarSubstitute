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

"""Define provider-neutral discovery values for model-picker recovery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from substitute.domain.model_recommendations import ModelFamilyId
from sugarsubstitute_shared.model_discovery import ModelArtifactKind


class ModelSuggestionAccessPolicy(StrEnum):
    """Describe which provider access states a suggestion surface accepts."""

    PUBLIC_ONLY = "public_only"
    CURRENT_USER = "current_user"


class ModelSuggestionAccess(StrEnum):
    """Describe authentication required to acquire one exact suggestion."""

    PUBLIC = "public"
    API_KEY_REQUIRED = "api_key_required"


@dataclass(frozen=True, slots=True)
class ModelSuggestionReference:
    """Identify one provider artifact without imposing provider ID shapes."""

    provider_id: str
    provider_name: str
    model_id: str
    version_id: str
    thumbnail_id: str | None = None

    @property
    def identity(self) -> str:
        """Return a stable provider-scoped version identity."""

        return f"{self.provider_id}:{self.model_id}:{self.version_id}"


@dataclass(frozen=True, slots=True)
class ModelSuggestionContext:
    """Describe the compatibility requirements of one model picker."""

    artifact_kind: ModelArtifactKind
    family_id: ModelFamilyId


@dataclass(frozen=True, slots=True)
class ModelSuggestion:
    """Describe one exact provider model using application-owned semantics."""

    reference: ModelSuggestionReference
    context: ModelSuggestionContext
    model_name: str
    version_name: str
    creator: str | None
    file_name: str
    size_bytes: int
    sha256: str
    download_url: str
    model_page_url: str
    thumbnail_url: str | None
    provider_rank: int
    access: ModelSuggestionAccess

    @property
    def identity(self) -> str:
        """Return an exact identity suitable for UI selection."""

        return f"{self.reference.identity}:{self.sha256.casefold()}"


@dataclass(frozen=True, slots=True)
class ModelSuggestionPlan:
    """Carry provider-ranked suggestions and their acquisition destination."""

    context: ModelSuggestionContext
    suggestions: tuple[ModelSuggestion, ...]
    destination: Path
    browse_urls: tuple[tuple[str, str], ...]


__all__ = [
    "ModelSuggestion",
    "ModelSuggestionAccess",
    "ModelSuggestionAccessPolicy",
    "ModelSuggestionContext",
    "ModelSuggestionPlan",
    "ModelSuggestionReference",
]
