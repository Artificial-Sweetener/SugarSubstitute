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

"""Define provider-neutral model inventory and onboarding discovery values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ModelCategory(str, Enum):
    """Identify model kinds supported by cube model-picker contracts."""

    CHECKPOINTS = "checkpoints"
    DIFFUSION_MODELS = "diffusion_models"
    LORAS = "loras"
    VAE = "vae"
    CONTROLNET = "controlnet"
    UPSCALE_MODELS = "upscale_models"


@dataclass(frozen=True, slots=True)
class CubeModelCapability:
    """Declare model categories exposed by one available cube."""

    cube_id: str
    categories: frozenset[ModelCategory]


@dataclass(frozen=True, slots=True)
class LocalModel:
    """Describe one locally available model visible to a supported cube."""

    category: ModelCategory
    path: Path
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredModel:
    """Describe one provider-validated downloadable model file."""

    category: ModelCategory
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
class ModelOnboardingEligibility:
    """Explain whether zero-compatible-model onboarding should be presented."""

    supported_categories: tuple[ModelCategory, ...]
    compatible_local_model_count: int

    @property
    def should_offer(self) -> bool:
        """Return whether at least one supported category has zero local models overall."""

        return (
            bool(self.supported_categories) and self.compatible_local_model_count == 0
        )


@dataclass(frozen=True, slots=True)
class ModelDiscoveryCard:
    """Present one candidate with explicit destination and unchecked selection."""

    model: DiscoveredModel
    destination: Path
    selected: bool = False


@dataclass(frozen=True, slots=True)
class ModelDiscoveryPlan:
    """Describe category interests and up to three cards for each selection."""

    eligibility: ModelOnboardingEligibility
    selected_categories: tuple[ModelCategory, ...]
    cards: tuple[ModelDiscoveryCard, ...]
    explore_url: str

    def cards_for(self, category: ModelCategory) -> tuple[ModelDiscoveryCard, ...]:
        """Return provider-ranked cards for one selected category."""

        return tuple(card for card in self.cards if card.model.category is category)


__all__ = [
    "CubeModelCapability",
    "DiscoveredModel",
    "LocalModel",
    "ModelCategory",
    "ModelDiscoveryCard",
    "ModelDiscoveryPlan",
    "ModelOnboardingEligibility",
]
