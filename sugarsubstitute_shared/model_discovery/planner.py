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

"""Plan provider discovery for one empty ComfyUI artifact picker."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    LocalModel,
    ModelArtifactKind,
    ModelDiscoveryCard,
    ModelDiscoveryPlan,
)

_CARD_LIMIT = 3
_DISCOVERY_FETCH_LIMIT = 30


class ModelInventory(Protocol):
    """List artifacts across backend-configured ComfyUI model roots."""

    def list_models(
        self,
        artifact_kinds: Collection[ModelArtifactKind],
    ) -> tuple[LocalModel, ...]:
        """Return all visible local artifacts for the requested kinds."""


class ModelDiscoveryGateway(Protocol):
    """Return safe downloadable candidates in provider popularity order."""

    def discover_monthly_popular(
        self,
        artifact_kind: ModelArtifactKind,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Return eligible candidates ranked over the last month."""


class ModelDestinationPolicy(Protocol):
    """Resolve the concrete model folder for one artifact kind."""

    def destination_for(self, artifact_kind: ModelArtifactKind) -> Path:
        """Return the safe destination directory for the artifact kind."""


class EmptyPickerModelDiscoveryPlanner:
    """Plan an empty picker's provider cards without onboarding policy."""

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

    def plan_empty_picker(
        self,
        artifact_kind: ModelArtifactKind,
    ) -> ModelDiscoveryPlan:
        """Return unchecked popular cards only when the picker remains empty."""

        local_models = self._inventory.list_models((artifact_kind,))
        cards = self._cards(artifact_kind, local_models) if not local_models else ()
        return ModelDiscoveryPlan(
            cards=cards,
            explore_url=_explore_url(artifact_kind),
        )

    def _cards(
        self,
        artifact_kind: ModelArtifactKind,
        local_models: Collection[LocalModel],
    ) -> tuple[ModelDiscoveryCard, ...]:
        """Exclude owned identities and retain provider order without selection."""

        owned_hashes = {
            model.sha256.casefold()
            for model in local_models
            if model.sha256 is not None and model.sha256.strip()
        }
        cards: list[ModelDiscoveryCard] = []
        seen: set[tuple[int, int, str]] = set()
        for model in self._discovery.discover_monthly_popular(
            artifact_kind,
            limit=_DISCOVERY_FETCH_LIMIT,
        ):
            identity = (
                model.model_id,
                model.version_id,
                model.sha256.casefold(),
            )
            if (
                model.artifact_kind is not artifact_kind
                or model.sha256.casefold() in owned_hashes
                or identity in seen
            ):
                continue
            seen.add(identity)
            cards.append(
                ModelDiscoveryCard(
                    model=model,
                    destination=self._destinations.destination_for(artifact_kind),
                )
            )
            if len(cards) == _CARD_LIMIT:
                break
        return tuple(cards)


def _explore_url(artifact_kind: ModelArtifactKind) -> str:
    """Build a public CivitAI exploration URL with no authentication material."""

    query: Mapping[str, str] = {
        "sort": "Most Downloaded",
        "period": "Month",
        "types": _CIVITAI_TYPE_NAMES[artifact_kind],
    }
    return "https://civitai.com/models?" + urlencode(query)


_CIVITAI_TYPE_NAMES = {
    ModelArtifactKind.CHECKPOINTS: "Checkpoint",
    ModelArtifactKind.DIFFUSION_MODELS: "Checkpoint",
    ModelArtifactKind.LORAS: "LORA",
    ModelArtifactKind.VAE: "VAE",
    ModelArtifactKind.CONTROLNET: "Controlnet",
    ModelArtifactKind.UPSCALE_MODELS: "Upscaler",
}


__all__ = [
    "EmptyPickerModelDiscoveryPlanner",
    "ModelDestinationPolicy",
    "ModelDiscoveryGateway",
    "ModelInventory",
]
