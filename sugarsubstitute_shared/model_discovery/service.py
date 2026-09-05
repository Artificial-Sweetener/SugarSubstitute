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

"""Coordinate discovery and checked acquisition for an empty model picker."""

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
    ModelArtifactKind,
    ModelDiscoveryCard,
    ModelDiscoveryPlan,
)
from sugarsubstitute_shared.model_discovery.planner import (
    EmptyPickerModelDiscoveryPlanner,
)


class EmptyPickerModelDiscoveryService:
    """Coordinate empty-picker recommendations and verified acquisitions."""

    def __init__(
        self,
        *,
        planner: EmptyPickerModelDiscoveryPlanner,
        acquisition: ModelAcquisitionService,
    ) -> None:
        """Store the planning and verified-acquisition owners."""

        self._planner = planner
        self._acquisition = acquisition

    def plan_empty_picker(self, artifact_kind: ModelArtifactKind) -> ModelDiscoveryPlan:
        """Return safe provider cards for one empty artifact picker."""

        return self._planner.plan_empty_picker(artifact_kind)

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
    return f"{model.artifact_kind.value}:{model.model_id}:{model.version_id}:{model.sha256}"


__all__ = ["EmptyPickerModelDiscoveryService", "model_card_identity"]
