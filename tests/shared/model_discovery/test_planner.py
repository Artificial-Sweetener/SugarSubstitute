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

"""Verify the focused empty-picker model discovery policy."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from sugarsubstitute_shared.model_discovery import (
    DiscoveredModel,
    EmptyPickerModelDiscoveryPlanner,
    LocalModel,
    ModelArtifactKind,
)


class _Inventory:
    """Expose deterministic local models across requested artifact kinds."""

    def __init__(self, models: tuple[LocalModel, ...]) -> None:
        """Store local inventory records."""

        self._models = models

    def list_models(
        self,
        artifact_kinds: Collection[ModelArtifactKind],
    ) -> tuple[LocalModel, ...]:
        """Return only requested model kinds."""

        selected = set(artifact_kinds)
        return tuple(model for model in self._models if model.artifact_kind in selected)


class _Discovery:
    """Expose deliberately duplicated provider results."""

    def __init__(self, models: tuple[DiscoveredModel, ...]) -> None:
        """Store provider-ranked results."""

        self._models = models

    def discover_monthly_popular(
        self,
        artifact_kind: ModelArtifactKind,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Return matching provider results up to the acquisition limit."""

        assert limit == 30
        return tuple(
            model for model in self._models if model.artifact_kind is artifact_kind
        )[:limit]


class _Destinations:
    """Map each artifact kind to a representative Comfy model root."""

    def __init__(self, root: Path) -> None:
        """Store the Comfy models root."""

        self._root = root

    def destination_for(self, artifact_kind: ModelArtifactKind) -> Path:
        """Return the artifact-kind folder."""

        return self._root / artifact_kind.value


def _model(
    rank: int,
    *,
    artifact_kind: ModelArtifactKind = ModelArtifactKind.LORAS,
    sha256: str | None = None,
) -> DiscoveredModel:
    """Build one provider-ranked candidate."""

    return DiscoveredModel(
        artifact_kind=artifact_kind,
        model_id=rank,
        version_id=rank * 10,
        model_name=f"Model {rank}",
        version_name="v1",
        creator="Creator",
        base_model="SDXL 1.0",
        file_name=f"model-{rank}.safetensors",
        size_bytes=rank * 1024,
        sha256=sha256 or f"{rank:064x}",
        download_url=f"https://civitai.com/api/download/models/{rank * 10}",
        model_page_url=f"https://civitai.com/models/{rank}",
        thumbnail_url=None,
        provider_rank=rank,
    )


def test_empty_picker_returns_three_unchecked_monthly_cards(tmp_path: Path) -> None:
    """Cards preserve provider popularity order and use the artifact destination."""

    planner = EmptyPickerModelDiscoveryPlanner(
        inventory=_Inventory(()),
        discovery=_Discovery(tuple(_model(rank) for rank in range(1, 6))),
        destinations=_Destinations(tmp_path / "models"),
    )

    plan = planner.plan_empty_picker(ModelArtifactKind.LORAS)

    assert [card.model.provider_rank for card in plan.cards] == [1, 2, 3]
    assert all(card.destination == tmp_path / "models" / "loras" for card in plan.cards)
    assert "period=Month" in plan.explore_url


def test_empty_picker_filters_duplicates_and_wrong_artifact_kinds(
    tmp_path: Path,
) -> None:
    """Only unique candidates for the requested technical kind are eligible."""

    duplicate = _model(2)
    planner = EmptyPickerModelDiscoveryPlanner(
        inventory=_Inventory(()),
        discovery=_Discovery(
            (
                _model(1, artifact_kind=ModelArtifactKind.CHECKPOINTS),
                duplicate,
                duplicate,
                _model(3),
                _model(4),
                _model(5),
            )
        ),
        destinations=_Destinations(tmp_path),
    )

    plan = planner.plan_empty_picker(ModelArtifactKind.LORAS)

    assert [card.model.provider_rank for card in plan.cards] == [2, 3, 4]


def test_nonempty_picker_does_not_offer_provider_cards(tmp_path: Path) -> None:
    """Existing local content keeps the empty-picker recovery dormant."""

    owned = LocalModel(ModelArtifactKind.LORAS, tmp_path / "owned.safetensors")
    planner = EmptyPickerModelDiscoveryPlanner(
        inventory=_Inventory((owned,)),
        discovery=_Discovery((_model(1),)),
        destinations=_Destinations(tmp_path),
    )

    assert planner.plan_empty_picker(ModelArtifactKind.LORAS).cards == ()
