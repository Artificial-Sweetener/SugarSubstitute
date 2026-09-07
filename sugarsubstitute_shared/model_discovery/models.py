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

"""Define provider-neutral artifact discovery values for empty model pickers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ModelArtifactKind(str, Enum):
    """Identify a ComfyUI artifact role and its storage destination."""

    CHECKPOINTS = "checkpoints"
    DIFFUSION_MODELS = "diffusion_models"
    TEXT_ENCODERS = "text_encoders"
    LORAS = "loras"
    VAE = "vae"
    CONTROLNET = "controlnet"
    UPSCALE_MODELS = "upscale_models"


@dataclass(frozen=True, slots=True)
class LocalModel:
    """Describe one locally available artifact visible to a model picker."""

    artifact_kind: ModelArtifactKind
    path: Path
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredModel:
    """Describe one provider-validated downloadable model file."""

    artifact_kind: ModelArtifactKind
    model_id: int
    version_id: int
    model_name: str
    version_name: str
    creator: str | None
    base_model: str | None
    file_name: str
    size_bytes: int
    sha256: str
    download_url: str
    model_page_url: str
    thumbnail_url: str | None
    provider_rank: int


@dataclass(frozen=True, slots=True)
class ModelDiscoveryCard:
    """Present one candidate with explicit destination and unchecked selection."""

    model: DiscoveredModel
    destination: Path
    selected: bool = False


@dataclass(frozen=True, slots=True)
class ModelDiscoveryPlan:
    """Describe provider-ranked cards for one empty artifact picker."""

    cards: tuple[ModelDiscoveryCard, ...]
    explore_url: str

    def cards_for(
        self,
        artifact_kind: ModelArtifactKind,
    ) -> tuple[ModelDiscoveryCard, ...]:
        """Return provider-ranked cards for one artifact kind."""

        return tuple(
            card for card in self.cards if card.model.artifact_kind is artifact_kind
        )


__all__ = [
    "DiscoveredModel",
    "LocalModel",
    "ModelArtifactKind",
    "ModelDiscoveryCard",
    "ModelDiscoveryPlan",
]
