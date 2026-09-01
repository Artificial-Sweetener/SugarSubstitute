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

"""Coordinate reusable model onboarding planning and checked acquisition."""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sugarsubstitute_shared.model_acquisition import (
        AcquisitionResult,
        CancellationProbe,
        ModelAcquisitionService,
    )
from sugarsubstitute_shared.model_discovery.models import (
    CubeModelCapability,
    ModelCategory,
    ModelDiscoveryCard,
    ModelDiscoveryPlan,
    ModelOnboardingEligibility,
)
from sugarsubstitute_shared.model_discovery.planner import ModelDiscoveryPlanner


class ModelOnboardingService:
    """Coordinate gating, popular cards, picker reuse, and checked acquisitions."""

    def __init__(
        self,
        *,
        planner: ModelDiscoveryPlanner,
        acquisition: ModelAcquisitionService,
    ) -> None:
        """Store shared planning and verified acquisition owners."""

        self._planner = planner
        self._acquisition = acquisition

    def assess(
        self,
        capabilities: Collection[CubeModelCapability],
    ) -> ModelOnboardingEligibility:
        """Return whether installer onboarding should be offered."""

        return self._planner.assess_installer(capabilities)

    def plan(
        self,
        capabilities: Collection[CubeModelCapability],
        *,
        selected_categories: Collection[ModelCategory],
    ) -> ModelDiscoveryPlan:
        """Return unchecked safe cards for explicitly selected interests."""

        return self._planner.plan_installer(
            capabilities,
            selected_categories=selected_categories,
        )

    def plan_empty_picker(self, category: ModelCategory) -> ModelDiscoveryPlan:
        """Return the same safe cards when one picker has no local choices."""

        return self._planner.plan_empty_picker(category)

    def download_selected(
        self,
        plan: ModelDiscoveryPlan,
        *,
        selected_identities: Collection[str],
        cancellation: CancellationProbe | None = None,
        on_completed: Callable[[ModelDiscoveryCard, AcquisitionResult], None]
        | None = None,
    ) -> tuple[AcquisitionResult, ...]:
        """Acquire only checked cards and preserve existing models side-by-side."""

        selected = set(selected_identities)
        results: list[AcquisitionResult] = []
        for card in plan.cards:
            if model_card_identity(card) not in selected:
                continue
            result = self._acquisition.acquire(
                card.model,
                destination_dir=card.destination,
                cancellation=cancellation,
            )
            results.append(result)
            if on_completed is not None:
                on_completed(card, result)
        return tuple(results)


def model_card_identity(card: ModelDiscoveryCard) -> str:
    """Return a collision-resistant identity for one exact provider version."""

    model = card.model
    return f"{model.category.value}:{model.model_id}:{model.version_id}:{model.sha256}"


__all__ = ["ModelOnboardingService", "model_card_identity"]
