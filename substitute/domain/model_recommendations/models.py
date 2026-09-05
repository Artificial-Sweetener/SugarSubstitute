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

"""Define model-family, style, detection, and installation recommendation values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sugarsubstitute_shared.model_discovery import ModelArtifactKind


class ModelFamilyId(str, Enum):
    """Identify a supported generation-model family independently of storage."""

    SDXL = "sdxl"
    ANIMA = "anima"
    FLUX_2 = "flux.2"


class ModelStylePreference(str, Enum):
    """Identify an optional creative-style facet independently of family."""

    REALISM = "realism"
    ILLUSTRATION = "illustration"
    ANIME_STYLE = "anime_style"


class ModelRecipeRole(str, Enum):
    """Identify the role of one file in a runnable family recipe."""

    PRIMARY_MODEL = "primary_model"
    TEXT_ENCODER = "text_encoder"
    VAE = "vae"


@dataclass(frozen=True, slots=True)
class CivitaiFamilyMapping:
    """Define the preferred provider lineage recommended for a family."""

    recommendation_base_model: str
    model_type: str


@dataclass(frozen=True, slots=True)
class TensorShapeSignature:
    """Match one architecture tensor by suffix and bounded dimensions."""

    key_suffix: str
    shape: tuple[int | None, ...]


@dataclass(frozen=True, slots=True)
class FamilyDetectionPolicy:
    """Define trusted metadata evidence and allowed primary artifact kinds."""

    artifact_kind: ModelArtifactKind
    metadata_values: frozenset[str]
    tensor_key_prefixes: tuple[str, ...]
    tensor_shape_signatures: tuple[TensorShapeSignature, ...] = ()


@dataclass(frozen=True, slots=True)
class TrustedRecipeAsset:
    """Define one checksum-pinned auxiliary required by a family loader."""

    role: ModelRecipeRole
    artifact_kind: ModelArtifactKind
    filename: str
    subfolder: str
    source_url: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ModelFamilyDefinition:
    """Define provider, detection, and runnable-install policy for one family."""

    family_id: ModelFamilyId
    catalog_order: int
    civitai: CivitaiFamilyMapping
    detection: FamilyDetectionPolicy
    primary_artifact_kind: ModelArtifactKind
    auxiliaries: tuple[TrustedRecipeAsset, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelRecommendationQuery:
    """Request recommendations for one family and independent style facets."""

    family_id: ModelFamilyId
    styles: frozenset[ModelStylePreference] = frozenset()


@dataclass(frozen=True, slots=True)
class ModelRecommendation:
    """Describe one safe exact-family CivitAI model file in provider order."""

    family_id: ModelFamilyId
    model_id: int
    version_id: int
    model_name: str
    version_name: str
    creator: str | None
    file_name: str
    size_bytes: int
    sha256: str
    download_url: str
    model_page_url: str
    thumbnail_url: str
    popularity_rank: int


__all__ = [
    "CivitaiFamilyMapping",
    "FamilyDetectionPolicy",
    "ModelFamilyDefinition",
    "ModelFamilyId",
    "ModelRecipeRole",
    "ModelRecommendation",
    "ModelRecommendationQuery",
    "ModelStylePreference",
    "TensorShapeSignature",
    "TrustedRecipeAsset",
]
