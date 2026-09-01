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

"""Plan reusable zero-inventory and empty-picker model discovery."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from sugarsubstitute_shared.model_discovery.models import (
    CubeModelCapability,
    DiscoveredModel,
    LocalModel,
    ModelCategory,
    ModelDiscoveryCard,
    ModelDiscoveryPlan,
    ModelOnboardingEligibility,
)

_CARD_LIMIT = 3
_DISCOVERY_FETCH_LIMIT = 30
_CATEGORY_ORDER = tuple(ModelCategory)


class ModelInventory(Protocol):
    """List models across managed, attached, and configured external roots."""

    def list_models(
        self,
        categories: Collection[ModelCategory],
    ) -> tuple[LocalModel, ...]:
        """Return all visible local models for the requested categories."""


class ModelDiscoveryGateway(Protocol):
    """Return safe downloadable candidates in provider popularity order."""

    def discover_monthly_popular(
        self,
        category: ModelCategory,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Return eligible candidates ranked over the last month."""


class ModelDestinationPolicy(Protocol):
    """Resolve the concrete model folder for one inventory category."""

    def destination_for(self, category: ModelCategory) -> Path:
        """Return the safe destination directory for the category."""


class ModelDiscoveryPlanner:
    """Own installer gating and model-picker reuse over shared discovery ports."""

    def __init__(
        self,
        *,
        inventory: ModelInventory,
        discovery: ModelDiscoveryGateway,
        destinations: ModelDestinationPolicy,
    ) -> None:
        """Store local, provider, and destination boundaries."""

        self._inventory = inventory
        self._discovery = discovery
        self._destinations = destinations

    def assess_installer(
        self,
        capabilities: Collection[CubeModelCapability],
    ) -> ModelOnboardingEligibility:
        """Offer onboarding only when supported cubes have no compatible local model."""

        categories = _supported_categories(capabilities)
        local_models = self._inventory.list_models(categories)
        compatible = tuple(
            model for model in local_models if model.category in categories
        )
        return ModelOnboardingEligibility(categories, len(compatible))

    def plan_installer(
        self,
        capabilities: Collection[CubeModelCapability],
        *,
        selected_categories: Collection[ModelCategory],
    ) -> ModelDiscoveryPlan:
        """Return unchecked top-three cards only for selected supported interests."""

        eligibility = self.assess_installer(capabilities)
        selected = _selected_supported_categories(
            selected_categories,
            eligibility.supported_categories,
        )
        if not eligibility.should_offer:
            return ModelDiscoveryPlan(
                eligibility=eligibility,
                selected_categories=(),
                cards=(),
                explore_url=_explore_url(()),
            )
        local_models = self._inventory.list_models(selected)
        cards = self._cards(selected, local_models)
        return ModelDiscoveryPlan(
            eligibility=eligibility,
            selected_categories=selected,
            cards=cards,
            explore_url=_explore_url(selected),
        )

    def plan_empty_picker(self, category: ModelCategory) -> ModelDiscoveryPlan:
        """Reuse the same cards when one in-app picker has no local choices."""

        local_models = self._inventory.list_models((category,))
        eligibility = ModelOnboardingEligibility(
            supported_categories=(category,),
            compatible_local_model_count=len(local_models),
        )
        cards = self._cards((category,), local_models) if not local_models else ()
        return ModelDiscoveryPlan(
            eligibility=eligibility,
            selected_categories=(category,) if not local_models else (),
            cards=cards,
            explore_url=_explore_url((category,)),
        )

    def _cards(
        self,
        categories: Sequence[ModelCategory],
        local_models: Collection[LocalModel],
    ) -> tuple[ModelDiscoveryCard, ...]:
        """Filter owned identities and retain provider order without preselection."""

        owned_hashes = {
            model.sha256.casefold()
            for model in local_models
            if model.sha256 is not None and model.sha256.strip()
        }
        cards: list[ModelDiscoveryCard] = []
        for category in categories:
            seen: set[tuple[int, int, str]] = set()
            accepted = 0
            for model in self._discovery.discover_monthly_popular(
                category,
                limit=_DISCOVERY_FETCH_LIMIT,
            ):
                identity = (
                    model.model_id,
                    model.version_id,
                    model.sha256.casefold(),
                )
                if (
                    model.category is not category
                    or model.sha256.casefold() in owned_hashes
                    or identity in seen
                ):
                    continue
                seen.add(identity)
                cards.append(
                    ModelDiscoveryCard(
                        model=model,
                        destination=self._destinations.destination_for(category),
                    )
                )
                accepted += 1
                if accepted == _CARD_LIMIT:
                    break
        return tuple(cards)


def _supported_categories(
    capabilities: Collection[CubeModelCapability],
) -> tuple[ModelCategory, ...]:
    """Return a deterministic union of categories exposed by available cubes."""

    supported = {
        category for capability in capabilities for category in capability.categories
    }
    return tuple(category for category in _CATEGORY_ORDER if category in supported)


def _selected_supported_categories(
    selected: Collection[ModelCategory],
    supported: Collection[ModelCategory],
) -> tuple[ModelCategory, ...]:
    """Normalize interests against cube-supported categories."""

    selected_set = set(selected)
    supported_set = set(supported)
    return tuple(
        category
        for category in _CATEGORY_ORDER
        if category in selected_set and category in supported_set
    )


def _explore_url(categories: Collection[ModelCategory]) -> str:
    """Build a public CivitAI exploration URL with no authentication material."""

    type_names = tuple(_CIVITAI_TYPE_NAMES[category] for category in categories)
    query: Mapping[str, str] = {
        "sort": "Most Downloaded",
        "period": "Month",
        **({"types": ",".join(type_names)} if type_names else {}),
    }
    return "https://civitai.com/models?" + urlencode(query)


_CIVITAI_TYPE_NAMES = {
    ModelCategory.CHECKPOINTS: "Checkpoint",
    ModelCategory.DIFFUSION_MODELS: "Checkpoint",
    ModelCategory.LORAS: "LORA",
    ModelCategory.VAE: "VAE",
    ModelCategory.CONTROLNET: "Controlnet",
    ModelCategory.UPSCALE_MODELS: "Upscaler",
}


__all__ = [
    "ModelDestinationPolicy",
    "ModelDiscoveryGateway",
    "ModelDiscoveryPlanner",
    "ModelInventory",
]
