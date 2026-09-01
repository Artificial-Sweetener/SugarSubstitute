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

"""Verify reusable installer and empty-picker model discovery policy."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from sugarsubstitute_shared.model_discovery import (
    CubeModelCapability,
    DiscoveredModel,
    LocalModel,
    ModelCategory,
    ModelDiscoveryPlanner,
)


class _Inventory:
    """Expose deterministic local models across requested categories."""

    def __init__(self, models: tuple[LocalModel, ...]) -> None:
        """Store local inventory records."""

        self._models = models

    def list_models(
        self,
        categories: Collection[ModelCategory],
    ) -> tuple[LocalModel, ...]:
        """Return only requested model kinds."""

        selected = set(categories)
        return tuple(model for model in self._models if model.category in selected)


class _Discovery:
    """Expose deliberately duplicated and owned provider results."""

    def __init__(
        self, models: dict[ModelCategory, tuple[DiscoveredModel, ...]]
    ) -> None:
        """Store provider-ranked category results."""

        self._models = models

    def discover_monthly_popular(
        self,
        category: ModelCategory,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Return provider order up to the requested acquisition limit."""

        assert limit == 30
        return self._models.get(category, ())[:limit]


class _Destinations:
    """Map each category to a representative Comfy model root."""

    def __init__(self, root: Path) -> None:
        """Store the Comfy models root."""

        self._root = root

    def destination_for(self, category: ModelCategory) -> Path:
        """Return the category folder."""

        return self._root / category.value


def _model(
    category: ModelCategory,
    rank: int,
    *,
    sha256: str | None = None,
) -> DiscoveredModel:
    """Build one provider-ranked candidate."""

    digest = sha256 or f"{rank:064x}"
    return DiscoveredModel(
        category=category,
        model_id=rank,
        version_id=rank * 10,
        model_name=f"Model {rank}",
        version_name="v1",
        creator="Creator",
        base_model="SDXL 1.0",
        file_name=f"model-{rank}.safetensors",
        size_bytes=rank * 1024,
        sha256=digest,
        download_url=f"https://civitai.com/api/download/models/{rank * 10}",
        model_page_url=f"https://civitai.com/models/{rank}",
        thumbnail_url=None,
        provider_rank=rank,
    )


def test_installer_is_suppressed_when_any_supported_local_model_exists(
    tmp_path: Path,
) -> None:
    """Installer onboarding is a zero-compatible-inventory experience only."""

    capability = CubeModelCapability(
        "supported-cube",
        frozenset({ModelCategory.CHECKPOINTS, ModelCategory.LORAS}),
    )
    planner = ModelDiscoveryPlanner(
        inventory=_Inventory(
            (LocalModel(ModelCategory.CHECKPOINTS, tmp_path / "existing.safetensors"),)
        ),
        discovery=_Discovery({}),
        destinations=_Destinations(tmp_path),
    )

    plan = planner.plan_installer(
        (capability,), selected_categories=(ModelCategory.LORAS,)
    )

    assert not plan.eligibility.should_offer
    assert plan.selected_categories == ()
    assert plan.cards == ()


def test_installer_returns_three_unchecked_monthly_cards_per_selected_category(
    tmp_path: Path,
) -> None:
    """Cards should preserve provider popularity order and show destinations."""

    categories = frozenset({ModelCategory.CHECKPOINTS, ModelCategory.LORAS})
    candidates = {
        category: tuple(_model(category, rank) for rank in range(1, 6))
        for category in categories
    }
    planner = ModelDiscoveryPlanner(
        inventory=_Inventory(()),
        discovery=_Discovery(candidates),
        destinations=_Destinations(tmp_path / "models"),
    )

    plan = planner.plan_installer(
        (CubeModelCapability("cube", categories),),
        selected_categories=categories,
    )

    assert plan.eligibility.should_offer
    assert len(plan.cards_for(ModelCategory.CHECKPOINTS)) == 3
    assert len(plan.cards_for(ModelCategory.LORAS)) == 3
    assert [
        card.model.provider_rank for card in plan.cards_for(ModelCategory.CHECKPOINTS)
    ] == [1, 2, 3]
    assert all(not card.selected for card in plan.cards)
    assert all(card.destination.parent == tmp_path / "models" for card in plan.cards)
    assert "period=Month" in plan.explore_url


def test_empty_picker_reuses_cards_and_filters_owned_or_duplicate_identities(
    tmp_path: Path,
) -> None:
    """Picker recovery should share discovery while never offering an owned file."""

    owned = "a" * 64
    provider = (
        _model(ModelCategory.LORAS, 1, sha256=owned),
        _model(ModelCategory.LORAS, 2),
        _model(ModelCategory.LORAS, 2),
        _model(ModelCategory.LORAS, 3),
        _model(ModelCategory.LORAS, 4),
        _model(ModelCategory.LORAS, 5),
    )
    discovery = _Discovery({ModelCategory.LORAS: provider})
    destinations = _Destinations(tmp_path)
    empty_planner = ModelDiscoveryPlanner(
        inventory=_Inventory(()),
        discovery=discovery,
        destinations=destinations,
    )

    empty_plan = empty_planner.plan_empty_picker(ModelCategory.LORAS)

    assert [card.model.provider_rank for card in empty_plan.cards] == [1, 2, 3]
    owned_planner = ModelDiscoveryPlanner(
        inventory=_Inventory(
            (LocalModel(ModelCategory.LORAS, tmp_path / "owned", owned),)
        ),
        discovery=discovery,
        destinations=destinations,
    )
    assert owned_planner.plan_empty_picker(ModelCategory.LORAS).cards == ()
